#!/usr/bin/env python3
"""
Database initialization script for Heroku deployment
"""
import sqlite3
import os

def init_database():
    """Initialize the SQLite database with required tables"""
    db_path = os.environ.get('DATABASE_URL', 'manga.db')
    
    # Remove 'sqlite:///' prefix if present (Heroku sometimes adds this)
    if db_path.startswith('sqlite:///'):
        db_path = db_path[10:]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create chapters table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            chapter_number INTEGER,
            title TEXT,
            url TEXT,
            new INTEGER DEFAULT 1,
            PRIMARY KEY (chapter_number, title)
        )
    ''')
    
    # Create mangas table (if needed for future use)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mangas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            url_scheme TEXT,
            latest_chapter INTEGER,
            new INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at: {db_path}")

if __name__ == "__main__":
    init_database()
