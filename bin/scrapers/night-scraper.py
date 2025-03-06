import requests
import re
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import os
import logging
import time
import json
from bson.json_util import dumps
from sys import exit
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import aiohttp
import mmh3
import random

client = AsyncIOMotorClient(os.environ.get("MONGO-DB-URL"))
semaphore = asyncio.Semaphore(1)

python_name = os.path.basename(__file__)

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

formatter = logging.Formatter(f'{python_name}:%(levelname)s:%(message)s')

file_handler = logging.FileHandler('test.log', encoding='utf-8')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

"""
    differnt vars 
    asura_init_urls = get_cache("asura_init_urls")
"""

async def get_initial_urls_from_page(page_count):
    logging.info(f"get initai urls from page called for page ${page_count}")
    base_url = f"https://nightsup.net/page/{page_count}/?s"

    async with aiohttp.ClientSession() as session:
        async with session.get(base_url) as response:
            html_content = await response.text()

    soup = BeautifulSoup(html_content, 'html.parser')
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    pattern = re.compile(r"^https:\/\/nightsup\.net\/(series\/[a-zA-Z0-9-]+)\/?$")
    filtered_links = {link for link in links if pattern.match(link)}
    return filtered_links

async def get_initial_urls():
    logging.info("get initai urls called")
    consecutive_empty_count = 0
    page_count = 0
    all_links = {}
    domain_url = f"https://nightsup.net/"

    while consecutive_empty_count < 5:
        page_count += 1
        links = await get_initial_urls_from_page(page_count)
        if not bool(links):
            consecutive_empty_count += 1
        else:
            consecutive_empty_count = 0
            for link in links:
                if link.split("/")[-2][1].isdigit():
                    logging.info(link)
                    all_links["-".join(link.split("/")[-2].split("-")[1:])] = link
                else:
                    all_links[link.split("/")[-2]] = link
    night_cache = await get_cache("night_init_urls")
    night_cache.delete_one({})
    night_cache.insert_one(all_links)
    end_page_num = int(page_count) - int(consecutive_empty_count)
    total_link_count = len(all_links)
    logging.info(f"get initai urls ended total pages ${end_page_num} and total individual urls = ${total_link_count}")
    return

async def get_cache(cache_to_acsess):
    logging.info(f"get cache for ${cache_to_acsess} called")
    cache = client.cache
    specific_cache = cache[cache_to_acsess]
    return specific_cache

async def read_cache_json(cache_to_access):
    logging.info(f"get cache for {cache_to_access} called")
    db = client.cache
    doc = await db[cache_to_access].find_one()
    if doc and "_id" in doc:
        doc.pop("_id")
    return doc

async def get_night_main_urls_db():
    logging.info("get asura main url db called")
    db = client.night_main_urls_db
    return db


async def get_night_main_db():
    logging.info("get asura main url db called")
    db = client.night_main_db
    return db

def get_night_main_data():
    logging.info("get asura main data db called")
    db = client.night_main_data
    return db

async def fetch_urls_from_page(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
    except Exception as e:
        logging.error("fetch_urls_from_page " + url + " Error: " + str(e))
        return []

    match = re.search(r"ts_reader\.run\((\{.*?\})\);", html_content, re.DOTALL)
    if not match:
        logging.error("ts_reader.run() call not found " +  url)
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return []

    image_urls = []
    if "sources" in data and len(data["sources"]) > 0:
        source = data["sources"][0]
        if "images" in source:
            image_urls = source["images"]

    return image_urls




async def fetch_manhwa_all_chapters(name, initial_url):
    t_fetch_manhwa_all_chapters = time.time()

    async with aiohttp.ClientSession() as session:
        async with session.get(initial_url) as response:
            html_content = await response.text()

    pattern1 = re.compile(
        r"https:\/\/nightsup\.net\/(?:[a-zA-Z0-9-]+-)+?(chapter-?\d+)\/?"
    )
    pattern2 = re.compile(
        r"https:\/\/nightsup\.net\/(?:[a-zA-Z0-9-]+-)+?(\d+)\/?"
    )
    pattern3 = re.compile(
        r"https:\/\/nightsup\.net\/([a-zA-Z0-9-]+)-(chapter-?\d+)\/?"
    )

    async with aiohttp.ClientSession(headers={
        "User-Agent": random.choice([
            "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": initial_url,
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin"
    }) as session:
        async with session.get(initial_url) as response:
            html_content = await response.text()

    urls = []

    for pattern in (pattern1, pattern2, pattern3):
        for match in pattern.finditer(html_content):
                urls.append(match.group(0))


    sorted_chapters = sorted(urls, key=lambda s: int(re.findall(r'\d+', s)[-1]))
    chapter_urls = []
    for chapter in sorted_chapters:
        if chapter not in chapter_urls and name in chapter:
            chapter_urls.append(chapter)
        else:
            continue
    sorted_chapters = chapter_urls
    if sorted_chapters is []:
        return
    logging.info(f"current manhwa is {name}, starting at chapter {sorted_chapters[0]} and the manhwa goes to {sorted_chapters[-1]} max total urls = {len(sorted_chapters)}")    

    tasks = []
    for chapter_url in sorted_chapters:
        tasks.append(fetch_manhwa_all_chapters_sub(chapter_url))
    results = await asyncio.gather(*tasks)
    items_to_insert = [item for sublist in results for item in sublist]
    manhwa_db = await get_night_main_urls_db()
    manhwa_db[name].insert_many(items_to_insert , ordered=False)
    
    logging.info(
        f"Manhwa {name} fully fetched. Max chapter: {sorted_chapters[-1]}, total URLs: {str(len(items_to_insert))}. "
        f"Time taken: {time.time() - t_fetch_manhwa_all_chapters}s "
        f"Time / chapter = {(time.time() - t_fetch_manhwa_all_chapters)/(len(sorted_chapters))}"
    )



async def fetch_manhwa_all_chapters_sub(chapter_url):
    items_to_insert = []
    chapter_str = "chapter_" + chapter_url.split("-")[-1].replace("/" , "")
    urls = await fetch_urls_from_page(chapter_url)
    index = 0
    
    for url in urls:
        items_to_insert.append({"index": index, "url": url, "chapter": chapter_str})
        index += 1

    return items_to_insert
    



async def get_main_urls():
    t_get_main_urls = time.process_time()
    logging.info("get main url called")
    night_init_urls = await read_cache_json("night_init_urls")
    if night_init_urls == None:
        logging.error("no urls found in the cache / idk why thougth at function get main urls")
        return 
    logging.info(f"asurascans all manhwas number = ${len(night_init_urls)}")
    for name, url in night_init_urls.items():
        await fetch_manhwa_all_chapters(name, url)
    logging.info(f"fetching asura scans finnished in ${time.process_time() - t_get_main_urls}s")

async def start_main_download():
    night_main_urls_db = await get_night_main_urls_db()
    manhwa_collection_names = set()
    index = 0
    
    for item in await night_main_urls_db.list_collection_names():
        logging.info(item)
        collection_name = item.split(".")[0]
        manhwa_collection_names.add(collection_name)
        index += 1
    for manhwa in manhwa_collection_names:
        #print(manhwa +": "+ str(await get_max_chapter_number(manhwa)))
        await full_comparing_and_fetching_of_a_manhwa(manhwa)

async def do_find(cursor):
    list = []
    for document in await cursor.to_list(length=100):
        list.append(document)
    return list

async def download_a_chapter(db , collection_name, manhwa):
    docs = await do_find(db.find({"chapter" : collection_name}))
    if docs == []:
        logging.error("no docs found for " + manhwa + collection_name)
    try:
        tasks = []
        for doc in docs:
            logging.info(doc)
            exit(0)
            tasks.append(download_a_chapter_sub(doc , manhwa))
        chapter_data = await asyncio.gather(*tasks)
        db = await get_night_main_db()
        manhwa_db = db[manhwa]
        try:
            await manhwa_db.insert_many(chapter_data , ordered=False)
        except BulkWriteError as bwe:
            logging.error("BulkWriteError why did this happen pleas look for me if more than sometimes im at download_a_chapter in asura-scraper.py")      

    except Exception as e:
        logging.error("Error with semaphore / semaphore Error at asura-scraper.py at the : download_a_chapter function :"+ str(type(e)))

async def download_a_chapter_sub(doc, manhwa):
    async with aiohttp.ClientSession() as session:
        async with session.get(doc['url']) as response:
            if response.status == 200:
                content = await response.read()
                return_dict = {
                    "index": doc["index"],
                    "content": content,
                    "chapter": doc["chapter"],
                    "hash": mmh3.mmh3_x64_128_digest(content),
                    "content_type": str(response.headers.get('Content-Type', 'unknown')),
                    "_id": f"{doc['chapter']}_{doc['index']}"
                }
                return return_dict
            else:
                logging.error("http request failed with code " + str(response.status) + "url was " + doc["url"] + "in manhwa " + manhwa)
    

async def get_all_downloaded_chapters(manhwa):
    db = await get_night_main_db()
    return await db[manhwa].distinct("chapter")

async def full_comparing_and_fetching_of_a_manhwa(manhwa):
    manhwa = "eleceed"
    manhwa_to_download = (await get_night_main_urls_db())[manhwa]

    chapter_number = 0
    try:
        consecutive_no_urls = 0
        logging.info("temp consecutive no urls " + str(consecutive_no_urls))
        while True:
            collection_name = f"chapter_{chapter_number}"
            logging.info(await manhwa_to_download.distinct("chapter"))
            exit(0)
            if (
                collection_name in await manhwa_to_download.distinct("chapter")
                and
                collection_name not in await get_all_downloaded_chapters(manhwa)
                ):
                logging.info("download_a_chapter called in asura-scraper.py in full_comparing_and_fetching_of_a_manhwa with the params: " + str(manhwa) + " " + str(chapter_number))
                await download_a_chapter(manhwa_to_download , collection_name , manhwa)
                consecutive_no_urls = 0
                chapter_number += 1
            else:
                if consecutive_no_urls <= 10000:
                    consecutive_no_urls +=1
                    chapter_number += 1
                else:
                    break
        return chapter_number - 1
    except Exception as e:
        logging.error("full_comparing_and_fetching_of_a_manhwa failed because: " + str(e))

async def main():
    # manhwa = "taming-master"
    # exit(0)
    # await start_main_download()
    # exit(0)
    logging.info("Program started")
    await get_initial_urls()
    await get_main_urls()
    #await start_main_download()
    exit(0)

if __name__ == "__main__":
    #asyncio.run(main())
    #exit(0)
    asyncio.run(main())
    exit(0)
    asyncio.run(start_main_download())





