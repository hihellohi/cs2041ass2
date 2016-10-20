#!/usr/bin/env python3.5 
from flask import Flask, render_template, request;

app = Flask(__name__);

@app.route('/')
def hello_world():
	return render_template("main.html", body="hello");
	
@app.route('/static/<path:path>')
def send_static_file(path):
	return send_from_directory('static', path);

if __name__ == "__main__":
	app.run();
