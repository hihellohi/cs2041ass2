#!/usr/bin/env python3.5 
import sqlite3;
from flask import Flask, render_template, request, g;

app = Flask(__name__);

database = "dataset.db";

#src: http://flask.pocoo.org/docs/0.11/patterns/sqlite3/
def get_db():
	db = getattr(g, '_database', None);
	if db is None:
		db = g._database = sqlite3.connect(database);
	return db;

def query_db(query, args=(), one=False):
	cur = get_db().execute(query, args)
	rv = cur.fetchall()
	cur.close()
	return (rv[0] if rv else None) if one else rv

@app.teardown_appcontext
def close_connection(exception):
	db = getattr(g, '_database', None);
	if db is None:
		db.close();
#endsrc

@app.route('/')
def hello_world():
	return render_template("main.html");

@app.route('/z<stuid>')
def profile_page(stuid):
	profile = query_db("SELECT * FROM users WHERE zid = ?", [stuid], one=True);
	if not profile is None:
		return render_template("profile.html", 
				name=profile['name'],
				zid=stuid);
	else:
		return stuid

@app.route('/static/<path:path>')
def send_static_file(path):
	return send_from_directory('static', path);

if __name__ == "__main__":
	app.run();
