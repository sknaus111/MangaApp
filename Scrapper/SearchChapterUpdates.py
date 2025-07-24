## check all possible mangas for updates

## table mangas: title, url_scheme, last_chapter, new 
## table chapters: number, manga -> manga title, url, new
## store the chapters with information about it being new


# go through all the mangas in the database

# check if there is a new chapter, if yes set it to new and use ScrapeChapter to get the images

import sqlite3
from bs4 import BeautifulSoup
import requests
import os

def check_for_updates():
    
    conn = sqlite3.connect(os.environ.get('DATABASE_URL', 'manga.db'))
    cursor = conn.cursor()

    # Fetch all mangas
    # fix sql statement to use UNIQUE
    cursor.execute("SELECT DISTINCT title FROM chapters")
    mangas = cursor.fetchall()
    mangas = [manga[0] for manga in mangas]

    for manga in mangas:
        cursor.execute("SELECT MAX(chapter_number),url FROM chapters WHERE title = ?",(manga,))
        chapter, url = cursor.fetchall()[0]

        while True:
            chapter = chapter + 1
            url = url.replace(str(chapter-1), str(chapter))

            response = requests.get(url)

            if response.status_code != 200:
                break
            if response.url != url:
                break

            scrape(response,url,chapter,manga,cursor)

    conn.commit()
    conn.close()

def scrape(response: requests.Response, url: str, chapter: int, title: str, cursor: sqlite3.Cursor):
    """
    Scrape all images of a given response
    """    
    
    soup = BeautifulSoup(response.content, 'html.parser')

    # change images to find manga images of all possible image types but
    images = soup.find_all('img', src=lambda x: x and x.endswith(('.jpg', '.jpeg', '.png', '.gif')))

    print(f"Title: {title}, Chapter: {chapter}, URL: {url}")
    folder_name = f"images/{title.replace(' ', '_').lower()}/chapter-{chapter}"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    for img in images:
        img_url = img.get('src')
        save_image(img_url, folder_name)

    cursor.execute("INSERT INTO chapters (chapter_number, title, url ,new) VALUES (?, ?,?,?)", (chapter, title,url,True))

def save_image(img_url: str, folder: str):
    """
    Save the image to the local folder images.
    """
    response = requests.get(img_url)
    if response.status_code == 200:
        image_name = os.path.join(folder, img_url.split('/')[-1])
        with open(image_name, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Failed to retrieve image: {response.status_code}")

def delete_chapter(title: str, chapter: int, cursor: sqlite3.Cursor):
    """
    Delete a chapter from the database.
    """
    cursor.execute("DELETE FROM chapters WHERE title = ? AND chapter_number = ?", (title, chapter))

    folder_name = f"images/{title.replace(' ', '_').lower()}/chapter-{chapter}"
    if os.path.exists(folder_name):
        for filename in os.listdir(folder_name):
            file_path = os.path.join(folder_name, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(folder_name)


def delete_old_chapters():
    """
    Delete chapters that are not marked as new.
    """
    conn = sqlite3.connect(os.environ.get('DATABASE_URL', 'manga.db'))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM chapters WHERE new = 0")
    old_chapters = cursor.fetchall()

    for chapter in old_chapters:
        delete_chapter(chapter[1], chapter[0], cursor)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    #check_for_updates()
    delete_old_chapters()
    print("Update check completed.")


    