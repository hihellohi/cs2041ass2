#!/usr/bin/env python3.5 
import sqlite3;
import os;
import re;
from flask import Flask, session, redirect, render_template, request, g;
import datetime;

app = Flask(__name__);
app.secret_key = "thisistext";

database = "dataset.db";

studentid = re.compile(r'z(\d{7})');

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
	args['login'] = session.get('login', None);
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

def get_mentions(string):
	out = [];
	for i in set(studentid.findall(string)):
		if query_db("SELECT * FROM users WHERE zid = ?", [i]):
			out.append(i);

	return out;


# inserts posts/comments/replies
def insert_comments():
	if not 'login' in session:
		return False;

	c = get_db().cursor();
	now = datetime.datetime.now();
	date = now.date().isoformat();
	time = now.time().isoformat().split('.')[0];
	query = 'INSERT INTO %s (zid, parent, message, date, time) VALUES (?, ?, ?, ?, ?)';
	mentionsquery =  "INSERT INTO mentions (zid, post) VALUES (?, ?)";

	if 'newpost' in request.form:
		c.execute("INSERT INTO posts (zid, message, date, time) VALUES (?, ?, ?, ?)",
				(session['login'], request.form['post'], date, time));

		cur = c.execute('SELECT last_insert_rowid() AS n FROM posts');
		postid = cur.fetchall()[0]['n'];

		for i in get_mentions(request.form['post']):
			c.execute(mentionsquery, (i, postid));

	elif "newcomment" in request.form:
		c.execute(query % 'comments', (session['login'], request.form['newcomment'], request.form['post'], 
			date, time));

		for i in get_mentions(request.form['post']):
			a = query_db("SELECT * FROM mentions WHERE zid = ? AND post = ?", 
					(i, request.form['newcomment']), one = True);
			if not a:
				c.execute(mentionsquery, (i, request.form['newcomment']));

	elif "newreply" in request.form:
		print(request.form['newreply'], flush=True);
		parent = query_db("SELECT parent FROM comments WHERE id = ?", [request.form['newreply']], one=True)['parent'];

		c.execute(query % 'replies', (session['login'], request.form['newreply'], request.form['post'], 
			date, time));

		for i in get_mentions(request.form['post']):
			a = query_db("SELECT * FROM mentions WHERE zid = ? AND post = ?", 
					(i, parent), one = True);
			if not a:
				c.execute(mentionsquery, (i, parent));
	
	get_db().commit();
	return True;

@app.errorhandler(404)
def not_found(error):
	if request.path == '/':
		return redirect(request.base_url);
	return "404 Page Not Found!";

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
	tmp = query_db('SELECT * FROM users WHERE zid = ? OR email = ?', [num, request.form['email']], one=True)
	if tmp:
		return get_template("signup.html", 
				dupzid = tmp['zid'] == int(num), dupemail = tmp['email'] == request.form['email']);

	get_db().cursor().execute('INSERT INTO users (zid, email, password) VALUES (?, ?, ?)', 
			[num, request.form['email'], request.form['password']]);
	get_db().commit();		
	session['login'] = num;
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
	if request.method == 'POST':
		if not insert_comments():
			return redirect('login/');

	profile = query_db("SELECT * FROM users WHERE zid = ?", [stuid], one=True);
	mates = query_db("""SELECT users.zid, users.dp, users.name FROM users JOIN mates 
			ON users.zid = mates.mate2 WHERE mates.mate1= ?""", [stuid]);
	posts = query_db(
	"""SELECT posts.id, posts.zid, posts.message, posts.date, posts.time, users.name, users.dp 
	FROM posts INNER JOIN users ON posts.zid = users.zid WHERE posts.zid = ? 
	ORDER BY posts.date DESC, posts.time DESC""", [stuid]);
	
	get_comments(posts);

	if not profile is None:
		return get_template("profile.html", level="..", profile=profile, mates=mates, posts=posts);
	return redirect(".");


@app.route('/newsfeed/', methods=['GET', 'POST'])
def newsfeed():
	if not 'login' in session:
		return redirect('login/');

	if request.method == 'POST':
		insert_comments();

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
			WHERE mates.mate1 = ?
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
	if request.method == 'POST':
		insert_comments();
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
