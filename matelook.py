#!/usr/bin/env python3.5 
import sqlite3;
import os;
import re;
from flask import Flask, session, redirect, render_template, request, g;
import datetime;
import smtplib
from email.mime.text import MIMEText;

app = Flask(__name__);
app.secret_key = "thisistext";

database = "dataset.db";

studentid = re.compile(r'z(\d{7})');
innocenttag = re.compile(r'&lt;(/?[bui])&gt;');

#src: http://flask.pocoo.org/docs/0.11/patterns/sqlite3/
#sqlite code
def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value)
                for idx, value in enumerate(row))

def get_db():
	db = getattr(g, '_database', None);
	if db is None:
		db = sqlite3.connect(database);
		db.row_factory = make_dicts;
		g._database = db;
	return db;

def query_db(query, args=(), one=False):
	cur = get_db().execute(query, args);
	rv = cur.fetchall();
	cur.close();
	return (rv[0] if rv else None) if one else rv;

@app.teardown_appcontext
def close_connection(exception):
	db = getattr(g, '_database', None);
	if db:
		db.close();
#endsrc

#wrapper for render_template, pass login cookie
def get_template(f, **args):
	args['login'] = int(session['login']) if 'login' in session else None;
	return render_template(f, **args);

#get comments and replies for a list of posts
def get_comments(posts):
	for post in posts:
		post['children'] = query_db(
		"""SELECT comments.id, comments.zid, comments.message, comments.date, comments.time, users.name, users.dp
		FROM comments INNER JOIN users ON comments.zid = users.zid WHERE comments.parent = ?
		ORDER BY comments.date, comments.time""", [post['id']]);

		for comment in post['children']:
			comment['children'] = query_db(
			"""SELECT replies.zid, replies.message, replies.date, replies.time, users.name, users.dp
			FROM replies INNER JOIN users ON replies.zid = users.zid WHERE replies.parent = ?
			ORDER BY replies.date, replies.time""", [comment['id']]);

#get all mantions in a string
def get_mentions(string):
	out = [];
	for i in set(studentid.findall(string)):
		if query_db("SELECT * FROM users WHERE zid = ?", [i]):
			out.append(i);

	return out;


# inserts posts/comments/replies
def insert_comments():
	if request.method != 'POST':
		return True;

	if not 'login' in session:
		return False;

	c = get_db().cursor();
	now = datetime.datetime.now();
	date = now.date().isoformat();
	time = now.time().isoformat().split('.')[0];
	query = 'INSERT INTO %s (zid, parent, message, date, time) VALUES (?, ?, ?, ?, ?)';
	mentionsquery = "INSERT INTO mentions (zid, post) VALUES (?, ?)";

	if 'newpost' in request.form:
		c.execute("INSERT INTO posts (zid, message, date, time) VALUES (?, ?, ?, ?)",
				(session['login'], request.form['post'], date, time));

		cur = c.execute('SELECT last_insert_rowid() AS n');
		postid = cur.fetchall()[0]['n'];

		for i in get_mentions(request.form['post']):
			c.execute(mentionsquery, (i, postid));

	elif "newcomment" in request.form:
		c.execute(query % 'comments', 
				(session['login'], request.form['newcomment'], request.form['post'], date, time));

		for i in get_mentions(request.form['post']):
			a = query_db("SELECT * FROM mentions WHERE zid = ? AND post = ?", 
					(i, request.form['newcomment']), one = True);
			if not a:
				c.execute(mentionsquery, (i, request.form['newcomment']));

	elif "newreply" in request.form:
		parent = query_db("SELECT parent FROM comments WHERE id = ?", 
				[request.form['newreply']], one=True)['parent'];

		c.execute(query % 'replies', (session['login'], request.form['newreply'], request.form['post'], 
			date, time));

		for i in get_mentions(request.form['post']):
			a = query_db("SELECT * FROM mentions WHERE zid = ? AND post = ?", 
					(i, parent), one = True);
			if not a:
				c.execute(mentionsquery, (i, parent));
	
	get_db().commit();
	return True;

def send_email(subject, to, body):
	user = "noreply@matelook.com";

	with smtplib.SMTP('smtp.cse.unsw.edu.au') as s:
		s.sendmail(user, to, "From: %s\nTo: %s\nSubject: %s\n\n%s\n" % (user, ', '.join(to), subject, body));

@app.errorhandler(404)
def not_found(error):
	if request.path == '/':
		return redirect(request.base_url);
	return "404 Page Not Found!", 404;

@app.route('/')
def root():
	if 'login' in session:
		return redirect("newsfeed/");
	return get_template("main.html", level='.');

@app.route('/signup/', methods=['GET', 'POST'])
def signup():
	if request.method == 'GET':
		return get_template("signup.html", level='..');

	num = request.form['zid'].lstrip('z');
	tmp = query_db('''
		SELECT T.zid, T.email FROM (
			SELECT zid, email FROM users
			UNION SELECT zid, email FROM pending
		) AS T 
		WHERE T.zid = ? OR T.email = ?''', [num, request.form['email']], one=True)
	if tmp:
		return get_template("signup.html", level='..',
				dupzid = tmp['zid'] == int(num), dupemail = tmp['email'] == request.form['email'],
				zid = request.form['zid'], email = request.form['email']);

	get_db().cursor().execute('INSERT INTO pending (zid, email, password) VALUES (?, ?, ?)', 
			[num, request.form['email'], request.form['password']]);
	get_db().commit();		
	send_email("account confirmation", [request.form['email']], 
			"follow this link to confirm your email: %s" % request.url_root + 'c' + str((int(num) + 3) * 7));
	return redirect('confirm/');

@app.route('/confirm/')
def preconfirm():
	return get_template("preconfirm.html", level="..");

@app.route('/recovery/', methods=['GET', 'POST'])
def recovery():
	if request.method == 'GET':
		return get_template("recovery.html", level="..");
	credentials= query_db("SELECT zid, password FROM users WHERE email = ?",[request.form['email']], one=True); 
	if credentials:
		send_email("password recovery", [request.form['email']], 
			"your zID is z%s\nyour password is %s\n" % (credentials['zid'], credentials['password']));
	return get_template("postrecov.html", level="..", email = request.form['email']);

@app.route('/c<int:stuid>/')
def postconfirm(stuid):
	stuid = int(stuid/7) - 3;
	new = query_db("SELECT * FROM pending WHERE zid = ?", [stuid], one=True);
	if not new:
		return "404 Page Not Found!", 404;

	cursor = get_db().cursor();
	cursor.execute("DELETE FROM pending WHERE zid = ?", [stuid]);
	cursor.execute("INSERT INTO users (zid, email, password) VALUES (?, ?, ?)", 
			[new['zid'], new['email'], new['password']]);
	get_db().commit();
	
	session['login'] = str(stuid);
	return redirect('newsfeed/');
	

@app.route('/login/', methods=['GET', 'POST'])
def login():
	if 'login' in session:
		return redirect(".");
	if request.method == 'GET':
		return get_template("login.html", level='..');
	else:
		num = request.form['zid'].lstrip('z');
		password = query_db("SELECT password FROM users WHERE zid = ?", [num], one=True);
		if password and password['password'] == request.form['password']:
			session['login'] = num;
			return redirect("newsfeed/");
		else:
			return get_template("login.html", level='..', zid=request.form['zid']);

@app.route('/logoff/')
def logoff():
	session.pop('login', None);
	return redirect('.');

@app.route('/z<int:stuid>/', methods=['GET', 'POST'])
def profile_page(stuid):
	if not insert_comments():
		return redirect('login/');

	profile = query_db("SELECT * FROM users WHERE zid = ?", [stuid], one=True);
	
	if profile is None:
		return "404 Page Not Found!", 404;

	ismate = False;
	if 'login' in session and session['login'] != str(stuid):
		ismate = query_db("""SELECT pending FROM mates WHERE mate1 = ? AND mate2 = ?""", 
					[session['login'], stuid], one=True);

		if 'matereq' in request.form:
			if request.form['matereq'] and not ismate:
				cursor = get_db().cursor();
				cursor.execute("INSERT INTO mates (mate1, mate2, pending) VALUES (?, ?, 1)",
						[stuid, session['login']]);
				cursor.execute("INSERT INTO mates (mate1, mate2, pending) VALUES (?, ?, 1)",
						[session['login'], stuid]);
				get_db().commit();

				mateid = query_db("SELECT last_insert_rowid() AS n", one=True)['n'];
				send_email("Mate request", [profile['email']], 
						"""z%s sent you a mate request
						To accept/decline, go to this link: %s""" 
						% (session['login'], request.url_root + 'm' + str((mateid + 3) * 7)));

				ismate = {"pending": True};
			elif not request.form['matereq']:
				get_db().cursor().execute("""DELETE FROM mates WHERE 
					(mate1 = ? AND mate2 = ?) OR (mate2 = ? AND mate1 = ?)""", 
					[session['login'], stuid, session['login'], stuid]);
				get_db().commit();
				ismate = None;


	mates = query_db("""SELECT users.zid, users.dp, users.name FROM users JOIN mates 
			ON users.zid = mates.mate2 WHERE mates.mate1 = ? AND NOT mates.pending""", [stuid]);

	posts = query_db(
	"""SELECT posts.id, posts.zid, posts.message, posts.date, posts.time, users.name, users.dp 
	FROM posts INNER JOIN users ON posts.zid = users.zid WHERE posts.zid = ? 
	ORDER BY posts.date DESC, posts.time DESC""", [stuid]);
	
	get_comments(posts);

	if profile['profile']:
		profile['profile'] = profile['profile'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;');
		profile['profile'] = innocenttag.sub('<\g<1>>', profile['profile']);

	return get_template("profile.html", level="..", 
			profile=profile, mates=mates, posts=posts, ismate = ismate);

@app.route('/m<int:mateid>/', methods=['GET', 'POST'])
def new_mate(mateid):
	mateid = int(mateid / 7) - 3;

	if request.method == "POST":
		cursor = get_db().cursor();
		if "confirm" in request.form:
			cursor.execute("UPDATE mates SET pending = 0 WHERE id = ? OR id = ?", [mateid, mateid - 1]);
			get_db().commit();
			return redirect('.');
		else:
			cursor.execute("DELETE FROM mates WHERE id = ? OR id = ?", [mateid, mateid - 1]);
			get_db().commit();
			return redirect('.');


	profile = query_db(
			"SELECT users.zid, users.name FROM mates JOIN users ON mates.mate1 = users.zid WHERE mates.id = ?", 
			[mateid], one=True);

	if not request:
		return "404 Page Not Found!", 404;

	return get_template("newmate.html", level="..", profile=profile);

@app.route('/eprofile/', methods=['GET', 'POST'])
def eprof():
	if not 'login' in session:
		return redirect('login/');
	if request.method == 'POST':
		get_db().cursor().execute("UPDATE users SET profile = ?, name = ? WHERE zid = ?", 
				[request.form['pt'], request.form['name'], session['login']]);
		get_db().commit();
		return redirect('z' + str(session['login']));
	return get_template("eprofile.html", level="..", profile=query_db("SELECT * FROM users WHERE zid = ?", [session['login']], one=True));

@app.route('/newsfeed/', methods=['GET', 'POST'])
def newsfeed():
	if not 'login' in session:
		return redirect('login/');

	if not insert_comments():
		return redirect('login/');

	posts = query_db(
	"""
	SELECT T.id, T.zid, T.message, T.date, T.time, T.name, T.dp FROM(
		SELECT posts.id, posts.zid, posts.message, posts.date, posts.time, users.name, users.dp 
			FROM posts 
				JOIN users ON posts.zid = users.zid 
			WHERE posts.zid = ? 
		UNION SELECT posts.id, posts.zid, posts.message, posts.date, posts.time, users.name, users.dp
			FROM posts
				JOIN mates ON posts.zid = mates.mate2
				JOIN users ON users.zid = mates.mate2
			WHERE mates.mate1 = ? AND NOT mates.pending 
		UNION SELECT posts.id, posts.zid, posts.message, posts.date, posts.time, users.name, users.dp
			FROM posts
				JOIN mentions ON posts.id = mentions.post
				JOIN users ON users.zid = posts.zid
			WHERE mentions.zid = ?
	) AS T
	ORDER BY date DESC, time DESC""", [session['login']] * 3);
	
	get_comments(posts);
	return get_template("home.html", level="..", posts=posts);

@app.route('/search/', methods=['GET', 'POST'])
def search():

	if not insert_comments():
		return redirect('login/');

	if 'search' in request.args:
		if request.args['criteria'] == 'users':
			results = query_db("SELECT zid, name, dp FROM users WHERE name LIKE ?", ['%' + request.args['terms'] + '%']);
			return get_template("suser.html", level="..", terms=request.args['terms'], users=results);
		else:
			results = query_db(
			"""SELECT posts.id, posts.zid, posts.message, posts.date, posts.time, users.name, users.dp 
			FROM posts JOIN users ON posts.zid = users.zid WHERE posts.message LIKE ? 
			ORDER BY posts.date DESC, posts.time DESC""", ['%' + request.args['terms'] + '%']);

			get_comments(results);

			return get_template("spost.html", level="..", terms=request.args['terms'], posts=results);
	else:
		return get_template("srequest.html", level="..");

@app.route('/static/<path:path>')
def send_static_file(path):
	return send_from_directory('static', path);

if __name__ == "__main__":
	app.run();
