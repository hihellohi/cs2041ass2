#!/usr/bin/env python3.5

import glob, os, sys, sqlite3, shutil;#, re;

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

cursor.execute('''CREATE TABLE posts(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		longitude FLOAT,
		latitude FLOAT,
		zid INTEGER,
		parent INTEGER,
		message TEXT,
		date DATE,
		time TIME)''');

cursor.execute('''CREATE TABLE comments(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		zid INTEGER,
		parent INTEGER,
		message TEXT,
		date DATE,
		time TIME)''');

cursor.execute('''CREATE TABLE replies(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		zid INTEGER,
		parent INTEGER,
		message TEXT,
		date DATE,
		time TIME)''');


if os.path.exists('static/pics'):
	shutil.rmtree('static/pics');

os.makedirs('static/pics');

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
	else:
		dp = '/' + shutil.copyfile(dp, os.path.join('static', 'pics', person + '.jpg'));

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

	if os.path.exists(os.path.join(path, 'posts')):
		for post in glob.glob(os.path.join(path, 'posts', '*')):

			fields = {};
			with open(os.path.join(post, 'post.txt')) as fin:
				for line in fin:
					tmp = line.split('=');
					fields[tmp[0]] = '='.join(tmp[1:]);

			date, time = fields['time'].split('T');
			time = time.split('+')[0];

			cursor.execute('''INSERT INTO posts
			(longitude, latitude, zid, parent, message, date, time) VALUES (?, ?, ?, ?, ?, ?, ?)''',
			(fields.get("longitude", ""), fields.get("latitude", ""), 
				fields["from"], person, fields["message"].replace('\\n','\n'), date, time));
			
			cur = cursor.execute('SELECT last_insert_rowid() FROM posts');
			postid = cur.fetchall()[0][0];

			if os.path.exists(os.path.join(post, 'comments')):
				for comment in glob.glob(os.path.join(post, 'comments', '*')):

					fields = {};
					with open(os.path.join(comment, 'comment.txt')) as fin:
						for line in fin:
							tmp = line.split('=');
							fields[tmp[0]] = '='.join(tmp[1:]);

					date, time = fields['time'].split('T');
					time = time.split('+')[0];

					cursor.execute('''INSERT INTO comments
					(zid, parent, message, date, time) VALUES (?, ?, ?, ?, ?)''',
					(fields["from"], postid, fields["message"].replace('\\n','\n'), date, time));
					
					cur = cursor.execute('SELECT last_insert_rowid() FROM comments');
					commentid = cur.fetchall()[0][0];

					if os.path.exists(os.path.join(comment, 'replies')):
						for reply in glob.glob(os.path.join(comment, 'replies', '*')):

							fields = {};
							with open(os.path.join(reply, 'reply.txt')) as fin:
								for line in fin:
									tmp = line.split('=');
									fields[tmp[0]] = '='.join(tmp[1:]);

							date, time = fields['time'].split('T');
							time = time.split('+')[0];

							cursor.execute('''INSERT INTO replies
							(zid, parent, message, date, time) VALUES (?, ?, ?, ?, ?)''',
							(fields["from"], commentid, fields.get("message", "").replace('\\n','\n'), date, time));

db.commit();
db.close();
