#!/usr/bin/env python3.5

import glob, os, sys, sqlite3;#, re;

if(len(sys.argv) != 3):
	print("usage: %s dbname directory" % sys.argv[0]); 
	exit(1);

if(os.path.exists(sys.argv[1])):
	os.remove(sys.argv[1]);

db = sqlite3.connect(sys.argv[1]);
cursor = db.cursor();

#studentid = re.compile(r'(\d{7})');

cursor.execute('''CREATE TABLE users(
		zid INTEGER PRIMARY KEY,
		name TEXT,
		program TEXT,
		latitude FLOAT,
		longitude FLOAT,
		suburb TEXT,
		email TEXT,
		password TEXT,
		birthday DATE,
		dp TEXT)''');

cursor.execute('''CREATE TABLE mates(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		mate1 INTEGER,
		mate2 INTEGER)''');

cursor.execute('''CREATE TABLE courses(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user INTEGER,
		course TEXT)''');

for path in glob.glob(os.path.join(sys.argv[2], "*")):
	person = path[-7:];

	fields = {};
	with open(os.path.join(path, "user.txt")) as fin:
		for line in fin:
			tmp = line.split('=');
			fields[tmp[0]] = '='.join(tmp[1:]);

	dp = os.path.join(path, "profile.jpg");
	if not os.path.exists(dp):
		dp = "";

	cursor.execute('''INSERT INTO users 
	(zid, name, program, latitude, longitude, suburb, email, password, birthday, dp) VALUES 
	(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''' , 
		(person,
		fields.get("full_name", ""),
		fields.get("program", ""),
		fields.get("home_latitude", 'NULL'),
		fields.get("home_longitude", "NULL"),
		fields.get("home_suburb", ""),
		fields.get("email", ""),
		fields.get("password", ""),
		fields.get("birthday", "NULL"),
		dp)
	);

	if "mates" in fields:
		tmp = fields["mates"].split(",");
		for mate in tmp:
			mate = mate.rstrip('] \n')[-7:];
			cursor.execute('INSERT INTO mates (mate1, mate2) VALUES (?, ?)', (person, mate));

	if "courses" in fields:
		tmp = fields["courses"].split(",");
		for course in tmp:
			course = course.rstrip('] \n').lstrip('[ ');
			cursor.execute('INSERT INTO courses (user, course) VALUES (?, ?)' , (person, course));

db.commit();
db.close();