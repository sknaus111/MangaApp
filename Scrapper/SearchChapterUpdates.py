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
    
    conn = sqlite3.connect('manga.db')
    cursor = conn.cursor()

    # Fetch all mangas
    cursor.execute("SELECT title, url_scheme, last_chapter FROM mangas")
    mangas = cursor.fetchall()

    for manga in mangas:
        title, url_scheme, last_chapter = manga
        print(f"Checking updates for {title}...")

        new_chapter_number = last_chapter + 1
        new_chapter_url = url_scheme.replace("####", str(new_chapter_number))

        print(f"Checking URL: {new_chapter_url}")
        response = requests.get(new_chapter_url)

        # check if the link didnt redirecct to the start page "https://ww2.mangafreak.me/"
        print(f"Response URL: {response.url}")
        if response.url == "https://ww2.mangafreak.me":
            print(f"No new chapter found for {title}. Redirected to start page.")
            continue

        if response.status_code != 200:
            print(f"No new chapter found for {title}. Status code: {response.status_code}")
            continue

        scrape(new_chapter_url,new_chapter_number,title,cursor)

        cursor.execute("UPDATE mangas SET last_chapter = ?, new = 1 WHERE title = ?", (new_chapter_number, title))

    conn.commit()
    conn.close()

def scrape(url: str, chapter: int,title : str, cursor: sqlite3.Cursor):
    """
    Scrape the chapter page from the given url.
    """    
    session = requests.Session()
    response = session.get(url)

    if response.status_code != 200:
        print(f"Failed to retrieve chapter page: {response.status_code}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    images = soup.find_all('img', src=lambda x: x and x.endswith('.jpg'))
    
    folder_name = f"images/{title.replace(' ', '_').lower()}/chapter-{chapter}" 
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    for img in images:
        img_url = img.get('src')
        save_image(img_url, folder_name)

    cursor.execute("INSERT INTO chapters (id, title, folder ,new) VALUES (?, ?,?,?)", (chapter, title,folder_name,True))

def save_image(img_url: str, folder: str):
    """
    Save the image to the local folder images. First create a new folder for the respective chapter and then save the image there.
    """
    response = requests.get(img_url)
    if response.status_code == 200:
        image_name = os.path.join(folder, img_url.split('/')[-1])
        with open(image_name, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Failed to retrieve image: {response.status_code}")

if __name__ == "__main__":
    check_for_updates()
    print("Update check completed.")
    
    