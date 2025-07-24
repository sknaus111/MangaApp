#!/usr/bin/env python3
"""
PythonAnywhere deployment configuration
Place this in your app directory and run on PythonAnywhere
"""

import os
import sys

# Add your project directory to Python path
project_home = '/home/yourusername/MangaApp'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import your Flask app
from Viewer.app import app as application

# Set environment variables for production
os.environ['DATABASE_URL'] = '/home/yourusername/MangaApp/manga.db'
os.environ['FLASK_ENV'] = 'production'

if __name__ == "__main__":
    application.run()
