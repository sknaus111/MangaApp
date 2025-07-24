import sys
import os
import sqlite3
import threading
import re
import requests
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, jsonify


# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Scrapper.SearchChapterUpdates import check_for_updates, scrape

# Initialize Flask app
app = Flask(__name__, static_folder='../images', static_url_path='/images')

# Configuration
MANGA_ROOT = "images"
DATABASE_PATH = os.environ.get('DATABASE_URL', 'manga.db')
# Handle Railway's potential PostgreSQL URL format
if DATABASE_PATH.startswith('postgresql://'):
    # If you want to use PostgreSQL instead of SQLite in the future
    # DATABASE_PATH would need additional configuration
    pass
elif DATABASE_PATH.startswith('sqlite:///'):
    DATABASE_PATH = DATABASE_PATH[10:]  # Remove sqlite:/// prefix

# Global variables for scraping status
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

# Routes
@app.route('/')
def index():
    """Main page displaying manga series"""
    # Start background scraping only if it hasn't been done this session and isn't currently running
    global scraping_in_progress, scraping_completed_this_session
    if not scraping_in_progress and not scraping_completed_this_session:
        threading.Thread(target=background_scraping, daemon=True).start()
    
    # Load current data from database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get new chapters (from chapters table)
    cursor.execute("""
        SELECT DISTINCT title, MIN(chapter_number) as latest_chapter 
        FROM chapters 
        WHERE new = 1 
        GROUP BY title 
        ORDER BY title
    """)
    seriesNew = cursor.fetchall()
    
    # Get old chapters (from chapters table)
    cursor.execute("""
        SELECT DISTINCT title, MAX(chapter_number) as latest_chapter 
        FROM chapters 
        WHERE new = 0 
        GROUP BY title 
        ORDER BY title
    """)
    seriesOld = cursor.fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                         seriesNew=seriesNew, 
                         seriesOld=seriesOld, 
                         scraping_in_progress=scraping_in_progress)

@app.route('/add-manga', methods=['POST'])
def add_manga():
    """Handle adding new manga from the form"""
    try:
        title = request.form.get('title', '').strip()
        chapter_url = request.form.get('url_scheme', '').strip()
        latest_chapter = request.form.get('latest_chapter', '').strip()
        
        # Validate input
        if not title or not chapter_url or not latest_chapter:
            return redirect(url_for('index'))
        
        # Validate chapter is a number
        try:
            latest_chapter = int(latest_chapter)
        except ValueError:
            return redirect(url_for('index'))
        
        # Check if manga already exists
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM chapters WHERE title = ?", (title,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return redirect(url_for('index'))
        
        # Also add the latest chapter to chapters table
        cursor.execute("INSERT INTO chapters (chapter_number, title, url, new) VALUES (?, ?, ?, ?)",
                      (latest_chapter, title, chapter_url, 1))
        
        conn.commit()
        
        # Scrape the chapter immediately after adding it
        try:
            print(f"Scraping chapter {latest_chapter} for {title}...")
            response = requests.get(chapter_url)
            
            if response.status_code == 200:
                scrape(response, chapter_url, latest_chapter, title, cursor)
                conn.commit()
                print(f"Successfully scraped chapter {latest_chapter} for {title}")
            else:
                print(f"Failed to fetch chapter {latest_chapter} for {title}: HTTP {response.status_code}")
                
        except Exception as scrape_error:
            print(f"Error scraping chapter {latest_chapter} for {title}: {scrape_error}")
        
        conn.close()
        
        return redirect(url_for('index'))
    
    except Exception as e:
        print(f"Error adding manga: {e}")
        return redirect(url_for('index'))

@app.route('/series/<title>/<int:chapter>')
def chapter_images(title, chapter):
    """Display images for a specific chapter"""
    # Mark chapter as read (new = 0)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE chapters SET new = 0 WHERE title = ? AND chapter_number = ?", (title, chapter))
    
    # Get previous and next chapter information
    cursor.execute("SELECT chapter_number FROM chapters WHERE title = ? AND chapter_number < ? ORDER BY chapter_number DESC LIMIT 1", (title, chapter))
    prev_chapter_result = cursor.fetchone()
    prev_chapter = prev_chapter_result[0] if prev_chapter_result else None
    
    cursor.execute("SELECT chapter_number FROM chapters WHERE title = ? AND chapter_number > ? ORDER BY chapter_number ASC LIMIT 1", (title, chapter))
    next_chapter_result = cursor.fetchone()
    next_chapter = next_chapter_result[0] if next_chapter_result else None
    
    conn.commit()
    conn.close()

    # Find chapter images
    folder_name = f"{MANGA_ROOT}/{title.replace(' ', '_').lower()}/chapter-{chapter}"
    print(f"Looking for images in: {folder_name}")
    
    if not os.path.exists(folder_name):
        return render_template('no_images.html', title=title, chapter=chapter)

    # Get all images from the folder
    images = [f for f in os.listdir(folder_name) if f.endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    if not images:
        return render_template('no_images.html', title=title, chapter=chapter)
    
    # Sort images numerically
    def natural_sort_key(filename):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', filename)]
    
    images.sort(key=natural_sort_key)
    return render_template('chapter_images.html', title=title, chapter=chapter, images=images, 
                         prev_chapter=prev_chapter, next_chapter=next_chapter)

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

# API Routes
@app.route('/api/scraping-status')
def scraping_status():
    """API endpoint to check if scraping is still in progress"""
    return jsonify({'scraping_in_progress': scraping_in_progress})

@app.route('/api/refresh-data')
def refresh_data():
    """API endpoint to get updated manga data"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get new chapters
    cursor.execute("""
        SELECT DISTINCT title, MAX(chapter_number) as latest_chapter 
        FROM chapters 
        WHERE new = 1 
        GROUP BY title 
        ORDER BY title
    """)
    seriesNew = cursor.fetchall()
    
    # Get old chapters
    cursor.execute("""
        SELECT DISTINCT title, MAX(chapter_number) as latest_chapter 
        FROM chapters 
        WHERE new = 0 
        GROUP BY title 
        ORDER BY title
    """)
    seriesOld = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'seriesNew': seriesNew,
        'seriesOld': seriesOld,
        'scraping_in_progress': scraping_in_progress
    })

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('no_images.html', title="Not Found", chapter="404"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('no_images.html', title="Server Error", chapter="500"), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)