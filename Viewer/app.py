import sys
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, jsonify
import sqlite3
import os
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Scrapper.SearchChapterUpdates import check_for_updates

app = Flask(__name__, static_folder='../images', static_url_path='/images')

MANGA_ROOT = "images"
scraping_in_progress = False
scraping_completed_this_session = False

def background_scraping():
    """Run chapter updates in background"""
    global scraping_in_progress, scraping_completed_this_session
    scraping_in_progress = True
    print("Starting background scraping...")
    try:
        check_for_updates()
        print("Background scraping completed!")
        scraping_completed_this_session = True
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        scraping_in_progress = False

@app.route('/')
def index():
    # Start background scraping only if it hasn't been done this session and isn't currently running
    global scraping_in_progress, scraping_completed_this_session
    if not scraping_in_progress and not scraping_completed_this_session:
        threading.Thread(target=background_scraping, daemon=True).start()
    
    print(f"Static Folder Path: {app.static_folder}")
    print(f"Static url Path: {app.static_url_path}")
    
    # Load current data immediately
    conn = sqlite3.connect('manga.db')
    cursor = conn.cursor()
    cursor.execute("SELECT title, last_chapter FROM mangas WHERE new = 1 ORDER BY title")
    seriesNew = cursor.fetchall()
    cursor.execute("SELECT title, last_chapter FROM mangas WHERE new = 0 ORDER BY title")
    seriesOld = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', seriesNew=seriesNew, seriesOld=seriesOld, scraping_in_progress=scraping_in_progress)

@app.route('/api/scraping-status')
def scraping_status():
    """API endpoint to check if scraping is still in progress"""
    return jsonify({'scraping_in_progress': scraping_in_progress})

@app.route('/api/refresh-data')
def refresh_data():
    """API endpoint to get updated manga data"""
    conn = sqlite3.connect('manga.db')
    cursor = conn.cursor()
    cursor.execute("SELECT title, last_chapter FROM mangas WHERE new = 1 ORDER BY title")
    seriesNew = cursor.fetchall()
    cursor.execute("SELECT title, last_chapter FROM mangas WHERE new = 0 ORDER BY title")
    seriesOld = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'seriesNew': seriesNew,
        'seriesOld': seriesOld,
        'scraping_in_progress': scraping_in_progress
    })

@app.route('/series/<title>')
def chapters(title):
    conn = sqlite3.connect('manga.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, folder FROM chapters WHERE title = ?", (title,))
    chapters = cursor.fetchall()
    conn.close()
    
    # Check if the series has any chapters
    if not chapters:
        return render_template('no_chapters.html', title=title)

    return render_template('chapters.html', series=title, chapters=chapters)

@app.route('/series/<title>/<int:chapter>')
def chapter_images(title, chapter):
    conn = sqlite3.connect('manga.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE chapters SET new = 0 WHERE title = ? AND id = ?", (title, chapter))
    cursor.execute("UPDATE mangas SET new = 0 WHERE title = ?", (title,))
    conn.commit()
    conn.close()

    folder_name = f"{MANGA_ROOT}/{title.replace(' ', '_').lower()}/chapter-{chapter}"
    print(f"Looking for images in: {folder_name}")
    if not os.path.exists(folder_name):
        return render_template('no_images.html', title=title, chapter=chapter)

    # Get all images from the folder
    images = [f for f in os.listdir(folder_name) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if not images:
        return render_template('no_images.html', title=title, chapter=chapter)
    
    # Sort images numerically (1.jpg, 2.jpg, ..., 10.jpg, 11.jpg)
    import re
    def natural_sort_key(filename):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', filename)]
    
    images.sort(key=natural_sort_key)
    return render_template('chapter_images.html', title=title, chapter=chapter, images=images)
    

@app.route('/image/<title>/<int:chapter>/<filename>')
def serve_chapter_image(title, chapter, filename):
    """Serve individual chapter images with security checks"""
    # Sanitize inputs
    safe_title = title.replace(' ', '_').lower()
    safe_filename = os.path.basename(filename)  # Prevent directory traversal
    
    # Construct file path
    image_path = os.path.join(MANGA_ROOT, safe_title, f"chapter-{chapter}", safe_filename)
    print(f"Serving image from: {image_path}")
    
    # Security check: ensure file exists and is within expected directory
    if not os.path.exists(image_path):
        abort(404)
    
    # Additional security: verify file is actually an image
    if not safe_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        abort(404)
    
    return send_file(image_path)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)