#!/usr/bin/env python3.5 
import sqlite3;
import os;
from flask import Flask, session, redirect, render_template, request, g;

app = Flask(__name__);
app.secret_key = os.urandom(420);

database = "dataset.db";

#src: http://flask.pocoo.org/docs/0.11/patterns/sqlite3/
def get_db():
	db = getattr(g, '_database', None);
	if db is None:
		db = sqlite3.connect(database);
		db.row_factory = sqlite3.Row;
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

def get_template(f, **args):
	args['login'] = session.get('login', None);
	return render_template(f, **args);

@app.route('/')
def root():
	return get_template("main.html", level='.');

@app.route('/login/', methods=['GET', 'POST'])
def login():
	if 'login' in session:
		return redirect("..");
	if request.method == 'GET':
		return get_template("login.html", level='..');
	else:
		num = request.form['zid'].lstrip('z');
		password = query_db("SELECT password FROM users WHERE zid = ?", [num], one=True);
		if password and password['password'] == request.form['password']:
			session['login'] = num;
			return redirect("..");
		else:
			return get_template("login.html", level='..', zid=request.form['zid']);

@app.route('/logoff/')
def logoff():
	session.pop('login', None);
	return redirect('..');

@app.route('/z<int:stuid>/')
def profile_page(stuid):
	profile = query_db("SELECT * FROM users WHERE zid = ?", [stuid], one=True);
	mates = query_db("""SELECT users.zid, users.dp, users.name FROM users JOIN mates 
			ON users.zid = mates.mate2 WHERE mates.mate1= ?""", [stuid]);
	posts = query_db(
	"""SELECT posts.zid, posts.message, posts.date, posts.time, users.name, users.dp 
	FROM posts INNER JOIN users ON posts.zid = users.zid WHERE posts.parent = ? 
	ORDER BY posts.date DESC, posts.time DESC""", [stuid]);

	if not profile is None:
		return get_template("profile.html", level="..", profile=profile, mates=mates, posts=posts);
	return redirect("..");

@app.route('/search/', methods=['GET'])
def search():
	if 'search' in request.args:
		if request.args['criteria'] == 'users':
			results = query_db("SELECT zid, name, dp FROM users WHERE name LIKE ?", ['%' + request.args['terms'] + '%']);
			return get_template("suser.html", level="..", terms=request.args['terms'], users=results);
		else:
			results = query_db(
			"""SELECT posts.zid, posts.message, posts.date, posts.time, users.name, users.dp 
			FROM posts INNER JOIN users ON posts.zid = users.zid WHERE posts.message LIKE ? 
			ORDER BY posts.date DESC, posts.time DESC""", ['%' + request.args['terms'] + '%']);
			return get_template("spost.html", level="..", terms=request.args['terms'], posts=results);
	else:
		return get_template("srequest.html", level="..");

@app.route('/static/<path:path>')
def send_static_file(path):
	return send_from_directory('static', path);

if __name__ == "__main__":
	app.run();
