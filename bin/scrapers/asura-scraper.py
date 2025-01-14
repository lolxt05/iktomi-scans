import requests
import re
from bs4 import BeautifulSoup
from pymongo import MongoClient
import os



"""

    differnt vars 
    asura_init_urls = get_cache("asura_init_urls")
    




"""

def get_initial_urls_from_page(page_count):
    base_url = f"https://asuracomic.net/series?page={page_count}&name="

    html_content = requests.get(base_url).text
    soup = BeautifulSoup(html_content, 'html.parser')

    links = [a.get('href') for a in soup.find_all('a', href=True)]
    
    pattern = re.compile(r"^series/[a-zA-Z0-9-]+$")
    filtered_links = {link for link in links if pattern.match(link)}
    return filtered_links


def get_initial_urls():
    consecutive_empty_count = 0
    page_count = 0
    all_links = {}
    domain_url = f"https://asuracomic.net/"

    while consecutive_empty_count < 5:
        page_count += 1
        links = get_initial_urls_from_page(page_count)
        print(f"https://asuracomic.net/series?page={page_count}&name=")
        print(links)
        if not bool(links):
            consecutive_empty_count += 1

        else:
            consecutive_empty_count = 0

            for link in links:
                all_links["-".join(link.rstrip("/").split("/")[-1].split("-")[:-1])] = domain_url + link
    asura_cache = get_cache("asura_init_urls")
    asura_cache.delete_one({})
    asura_cache.insert_one(all_links)
    return

def connect_to_db():
    client = MongoClient(os.environ.get("MONGO-DB-URL"))
    print(client.server_info)
    return client

def get_cache(cache_to_acsess):
    client = connect_to_db()
    cache = client.cache
    specific_cache = cache[cache_to_acsess]
    return specific_cache

def get_asura_main_urls_db():
    client = connect_to_db()
    db = client.asura_main_urls_db
    return db

def fetch_urls_from_page():
    return "leck eier"


def fetch_manhwa_all_chapters(name , url):
        asura_main_urls_db = get_asura_main_urls_db()
        manhwa_db = asura_main_urls_db[name]
        try:
            chapter_num = max(
                int(name1.split('_')[1]) 
                for name1 in manhwa_db.list_collection_names() 
                if name1.startswith('chapter_') and name1.split('_')[1].isdigit()
            )
        except ValueError:
            chapter_num = 0

        print(f"current chapter num is ${chapter_num}")
        consecutive_empty_chapters = 0
        while consecutive_empty_chapters < 5:

            urls = fetch_urls_from_page(url + f"/chapter/${chapter_num}")
            if urls is None:
                chapter_num += 1
                consecutive_empty_chapters += 1
            else:
                chapter_db = manhwa_db["chapter_" + str(chapter_num)]
                chapter_num += 1
                index = 0
                for url in urls:
                    chapter_db[str(index)] = url
                    index += 1
        



def get_main_urls():
    asura_init_urls = get_cache("asura_init_urls")
    for name , url in asura_init_urls:
        fetch_manhwa_all_chapters(name , url)








if __name__ == "__main__":
    print("Hello, World")

    

