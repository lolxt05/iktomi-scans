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
import collections

client = AsyncIOMotorClient(os.environ.get("MONGO-DB-URL"))
semaphore = asyncio.Semaphore(30)

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
    asura_init_urls = get_asura_cache("asura_init_urls")
"""

async def get_initial_urls_from_page(page_count):
    logging.info(f"get initai urls from page called for page ${page_count}")
    base_url = f"https://asuracomic.net/series?page={page_count}&name="

    async with aiohttp.ClientSession() as session:
        async with session.get(base_url) as response:
            html_content = await response.text()

    soup = BeautifulSoup(html_content, 'html.parser')
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    pattern = re.compile(r"^series/[a-zA-Z0-9-]+$")
    filtered_links = {link for link in links if pattern.match(link)}
    return filtered_links

async def get_initial_urls():
    logging.info("get initai urls called")
    consecutive_empty_count = 0
    page_count = 0
    all_links = {}
    domain_url = f"https://asuracomic.net/"

    while consecutive_empty_count < 5:
        page_count += 1
        links = await get_initial_urls_from_page(page_count)
        if not bool(links):
            consecutive_empty_count += 1
        else:
            consecutive_empty_count = 0
            for link in links:
                all_links["-".join(link.rstrip("/").split("/")[-1].split("-")[:-1])] = domain_url + link

    asura_cache = await get_asura_cache("asura_init_urls")
    asura_cache.delete_one({})
    asura_cache.insert_one(all_links)
    end_page_num = int(page_count) - int(consecutive_empty_count)
    total_link_count = len(all_links)
    logging.info(f"get initai urls ended total pages ${end_page_num} and total individual urls = ${total_link_count}")
    return

async def get_asura_cache(cache_to_acsess):
    logging.info(f"get cache for ${cache_to_acsess} called")
    cache = client.cache
    specific_cache = cache[cache_to_acsess]
    return specific_cache

async def read_cache_json(cache_to_access):
    logging.info(f"get cache for {cache_to_access} called")
    db = client.cache
    doc = await db[cache_to_access].find_one()  # Use await here
    if doc and "_id" in doc:
        doc.pop("_id")
    return doc

async def get_asura_main_urls_db():
    logging.info("get asura main url db called")
    db = client.asura_main_urls_db
    return db


async def get_asura_main_db():
    logging.info("get asura main url db called")
    db = client.asura_main_db
    return db

def get_asura_main_data():
    logging.info("get asura main data db called")
    db = client.asura_main_data
    return db

async def fetch_urls_from_page(url):
    logging.info(f"fetch urls from page called {url}")
    webp_pattern = r"https://gg\.asuracomic\.net/storage/media/\d{3,6}/conversions/[0-9a-zA-Z\-_]+-optimized\.webp"
    jpg_pattern = r"https://gg\.asuracomic\.net/storage/media/\d{3,6}/[0-9a-zA-Z\-_]+\.jpg"
    png_pattern = r"https://gg\.asuracomic\.net/storage/media/\d{3,6}/[0-9a-zA-Z\-_]+\.png"
    result_webp_pattern = r"https://gg\.asuracomic\.net/storage/media/\d{3,6}/conversions/[0-9a-zA-Z\-_]+_result-optimized\.webp"
    kopya_webp_pattern = r"https://gg\.asuracomic\.net/storage/media/\d{3,6}/conversions/[0-9a-zA-Z\-_]+-kopya_result-optimized\.webp"
    end_webp_pattern = r"https://gg\.asuracomic\.net/storage/media/\d{3,6}/conversions/end-optimized\.webp"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                text = await response.text()

        all_matches = []
        for pattern in [
            webp_pattern, jpg_pattern, png_pattern, result_webp_pattern,
            kopya_webp_pattern, end_webp_pattern
        ]:
            all_matches.extend(re.findall(pattern, text))

        if not all_matches:
            return None

        combined_links = list(dict.fromkeys(all_matches))

        def sort_key(link):
            match_page = re.search(r'/conversions/(\d{2}|end)[\-_a-z]*[-_]optimized\.webp', link)
            if match_page:
                page = match_page.group(1)
                return (1, float('inf') if page == 'end' else int(page))
            match_media = re.search(r'/storage/media/(\d{3,6})/', link)
            if match_media:
                return (2, int(match_media.group(1)))
            return (float('inf'), link)

        sorted_combined_links = sorted(combined_links, key=sort_key)
        return sorted_combined_links

    except Exception as e:
        logging.error(f"An error occurred while fetching chapter images with the function fetch_urls_from_page. Error: {e}")
        return None

async def fetch_manhwa_all_chapters(name, initial_url):
    t_fetch_manhwa_all_chapters = time.time()
    logging.info(f"fetch manhwa all chapters called for {name}")
    
    chapter_num = 0
    manhwa_db = (await get_asura_main_urls_db())[name]
    
    try:
        existing_chapters = await manhwa_db.distinct("chapter")
        if not existing_chapters:
            raise ValueError("No existing chapters found.")
        chapters_nums = [int(chap.split("_")[-1]) for chap in existing_chapters]
        chapter_num = max(chapters_nums)
        logging.info(f"Existing chapters found in db starting fetch at chapter {chapter_num}")
    except Exception as e:
        logging.error(f"No existing chapters found in db. Starting fetch at chapter 0. \n Error: \n {e}")
        chapter_num = -1
    chapter_num += 1
    logging.info(f"current manhwa is {name}, starting at chapter {chapter_num}")
    consecutive_empty_pages = 0
    total_urls = 0
    items_to_insert = []

    blacklist_cache = await get_asura_cache("asura_blacklist")
    for doc in await do_find(blacklist_cache.find({})):
        blacklist_urls_dict = doc
    blacklist_urls_dict.pop('_id')
    blacklist_urls = []
    for value in blacklist_urls_dict.values():
        blacklist_urls.append(value)
    while consecutive_empty_pages < 5:
        urls = await fetch_urls_from_page(initial_url + f"/chapter/{chapter_num}")
        if urls is None:
            consecutive_empty_pages += 1
        else:
            index = 0
            for url in urls:
                if url not in blacklist_urls:
                    items_to_insert.append({"index": index, "url": url, "chapter": f"chapter_{chapter_num}"})
                    index += 1
                    total_urls += 1
            consecutive_empty_pages = 0
        chapter_num += 1
    if items_to_insert != []:
        manhwa_db.insert_many(items_to_insert)

    logging.info(
        f"Manhwa {name} fully fetched. Max chapter: {chapter_num - 6}, total URLs: {total_urls}. "
        f"Time taken: {time.time() - t_fetch_manhwa_all_chapters}s "
        f"Time / chapter = {(time.time() - t_fetch_manhwa_all_chapters)/(chapter_num - 6)}"
    )

async def get_main_urls():
    t_get_main_urls = time.process_time()
    logging.info("get main url called")
    asura_init_urls = None
    while asura_init_urls == None:
        asura_init_urls = await read_cache_json("asura_init_urls")
    logging.info(f"asurascans all manhwas number = ${len(asura_init_urls)}")
    for name, url in asura_init_urls.items():
        await fetch_manhwa_all_chapters(name, url)
    logging.info(f"fetching asura scans finnished in ${time.process_time() - t_get_main_urls}s")

async def start_main_download():
    asura_main_urls_db = await get_asura_main_urls_db()
    manhwa_collection_names = set()
    index = 0
    
    for item in await asura_main_urls_db.list_collection_names():
        collection_name = item.split(".")[0]
        manhwa_collection_names.add(collection_name)
        index += 1
    
    for manhwa in manhwa_collection_names:
        #print(manhwa +": "+ str(await get_max_chapter_number(manhwa)))
        await full_comparing_and_fetching_of_a_manhwa(manhwa)

async def do_find(cursor):
    list = []
    for document in await cursor.to_list(length=1000000000):
        list.append(document)
    return list

async def download_a_chapter(db , collection_name, manhwa):
    docs = await do_find(db.find({"chapter" : collection_name}))
    if docs == []:
        logging.error("no docs found for " + manhwa + collection_name)
    try:
        tasks = []
        for doc in docs:
            tasks.append(download_a_chapter_sub(doc , manhwa))
        chapter_data = await asyncio.gather(*tasks)
        db = await get_asura_main_db()
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
    db = await get_asura_main_db()
    return await db[manhwa].distinct("chapter")

async def full_comparing_and_fetching_of_a_manhwa(manhwa):
    manhwa = "golden-mage"
    manhwa_to_download = (await get_asura_main_urls_db())[manhwa]
    
    chapter_number = 0
    try:
        consecutive_no_urls = 0
        logging.info("temp consecutive no urls" + str(consecutive_no_urls))
        while True:
            collection_name = f"chapter_{chapter_number}"
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
                    consecutive_no_urls += 1
                    chapter_number += 1
                else:
                    break
        return chapter_number - 1
    except Exception as e:
        logging.error("full_comparing_and_fetching_of_a_manhwa failed because: " + str(e))

async def update_asura_blacklist_urls_cache():
    main_urls = await get_asura_main_urls_db()
    all_collections = await main_urls.list_collection_names()
    all_urls = []
    for collection in all_collections:
        for doc in await do_find(main_urls[collection].find({})):
            all_urls.append(doc["url"])
    logging.info(len(all_urls))
    blacklist_cache = await get_asura_cache("asura_blacklist")
    await blacklist_cache.insert_one({str(index): value for index, value in enumerate([item for item, count in collections.Counter(all_urls).items() if count > 1])})



async def main():
    # manhwa = "taming-master"
    # exit(0)
    # await start_main_download()
    # exit(0)
    logging.info("Program started")
    await get_initial_urls()
    await get_main_urls()
    await update_asura_blacklist_urls_cache()
    exit(1)
    await start_main_download() # not finnished

if __name__ == "__main__":
    #asyncio.run(main())
    #exit(0)
    asyncio.run(main())
