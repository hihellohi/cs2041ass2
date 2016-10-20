#!/usr/bin/env python3.5 
from wsgiref.handlers import CGIHandler
from matelook import app

app.debug = True;

CGIHandler().run(app)
