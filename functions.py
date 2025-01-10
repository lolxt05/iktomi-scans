import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import json
import os
from urllib.parse import urljoin

# Regex patterns to detect series URLs:
PATTERNS = [
    r'https://asuracomic\.net/series/[^/\s"\']+',
    r'https://vortexscans\.org/series/[^/\s"\']+',
    r'https://reaper-scan\.net/manga/[^/\s"\']+',
    r'https://nightsup\.net/series/[^/\s"\']+'
]
COMBINED_PATTERN = '|'.join(PATTERNS)


async def get_initial_urls():
    """Gathers URLs from multiple manga sites concurrently."""
    print("Starting URL collection process...")
    results = {"asura": [], "reaper": [], "vortex": [], "night": []}

    tasks = [
        get_all_pages_asura(results),
        get_all_pages_reaper(results),
        get_all_pages_vortex(results),
        get_all_pages_night(results)
    ]
    await asyncio.gather(*tasks)

    # Deduplicate site by site
    for site_key, urls in results.items():
        results[site_key] = list(set(urls))

    total_urls = sum(len(urls) for urls in results.values())
    print(f"Collection complete. Total unique URLs found: {total_urls}")
    return results


async def get_all_pages_asura(results):
    """
    Asura URL pattern:
    https://asuracomic.net/series?page=1&name=
    Stops if we hit 3 consecutive 404s or 2 consecutive empty pages.
    """
    base_url = "https://asuracomic.net/series?page={}&name="
    await gather_pages(base_url, "asura", results)


async def get_all_pages_reaper(results):
    """
    Reaper URL pattern:
    https://reaper-scan.net/page/2/?s
    Stops if we hit 3 consecutive 404s or 2 consecutive empty pages.
    """
    base_url = "https://reaper-scan.net/page/{}/?s"
    await gather_pages(base_url, "reaper", results, start_page=2)


async def get_all_pages_vortex(results):
    """
    Vortex URL pattern:
    https://vortexscans.org/series?page=1
    Stops if we hit 3 consecutive 404s or 2 consecutive empty pages.
    """
    base_url = "https://vortexscans.org/series?page={}"
    await gather_pages(base_url, "vortex", results)


async def get_all_pages_night(results):
    """
    Night URL pattern:
    https://nightsup.net/page/2/?s
    Stops if we hit 3 consecutive 404s or 2 consecutive empty pages.
    """
    base_url = "https://nightsup.net/page/{}/?s"
    await gather_pages(base_url, "night", results, start_page=2)


async def gather_pages(base_url, site_key, results, start_page=1):
    """
    Fetches pages until 3 consecutive 404s or 2 consecutive empty pages (no new URLs).
    """
    print(f"[{site_key}] Starting page collection from page {start_page}")
    consecutive_404 = 0
    consecutive_empty = 0
    page_number = start_page
    all_urls = set()

    async with aiohttp.ClientSession() as session:
        while True:
            full_url = base_url.format(page_number)
            print(f"[{site_key}] Fetching page {page_number}: {full_url}")

            try:
                page_content = await fetch_html_and_js(session, full_url)
                consecutive_404 = 0  # Reset 404 count on success

                # Extract new URLs
                extracted = extract_urls(page_content)
                new_urls = set(extracted) - all_urls

                if not new_urls:
                    consecutive_empty += 1
                    print(f"[{site_key}] Empty or no new URLs. Consecutive empty pages: {consecutive_empty}")
                    if consecutive_empty >= 2:
                        print(f"[{site_key}] Stopping due to {consecutive_empty} consecutive empty pages.")
                        break
                else:
                    consecutive_empty = 0
                    all_urls.update(new_urls)
                    print(f"[{site_key}] Page {page_number}: Found {len(new_urls)} new URLs")

            except Exception as e:
                if "Status code: 404" in str(e):
                    consecutive_404 += 1
                    print(f"[{site_key}] 404 error. Consecutive 404s: {consecutive_404}")
                    if consecutive_404 >= 3:
                        print(f"[{site_key}] Stopping due to {consecutive_404} consecutive 404s.")
                        break
                else:
                    print(f"[{site_key}] Error on page {page_number}: {str(e)}")
                    raise e

            page_number += 1

    print(f"[{site_key}] Collection complete. Total URLs found: {len(all_urls)}")
    results[site_key].extend(all_urls)


async def fetch_html_and_js(session, url):
    """Fetches HTML, then attempts to retrieve and append inline/linked JS (excluding ad/tracker scripts)."""
    print(f"Fetching HTML from: {url}")
    async with session.get(url) as response:
        if response.status != 200:
            raise Exception(f"Failed to fetch HTML. Status code: {response.status}")

        html_content = await response.text()
        soup = BeautifulSoup(html_content, 'html.parser')

        # Collect inline JS
        js_contents = []
        script_elements = soup.find_all('script')
        print(f"Found {len(script_elements)} <script> tags")

        js_tasks = []
        for script in script_elements:
            src = script.get('src')
            if src:
                # Skip ad or tracker scripts
                if any(ad_domain in src.lower() for ad_domain in ['ads', 'analytics', 'tracking', 'bidgear']):
                    continue
                if not src.startswith(('http://', 'https://')):
                    src = urljoin(str(response.url), src)
                js_tasks.append(fetch_js(session, src))
            else:
                # Inline script
                if script.string:
                    js_contents.append(script.string)

        # Fetch external JS concurrently
        if js_tasks:
            js_results = await asyncio.gather(*js_tasks, return_exceptions=True)
            for r in js_results:
                if isinstance(r, str):
                    js_contents.append(r)

        combined_content = html_content + ' ' + ' '.join(js_contents)
        return combined_content


async def fetch_js(session, src):
    """Fetches external JS text, ignoring errors or 404s."""
    try:
        async with session.get(src) as js_response:
            if js_response.status == 200:
                return await js_response.text()
            return ""  # Return empty for non-200 responses
    except Exception:
        return ""  # Return empty if any request error occurs


def extract_urls(text):
    """Extracts site-specific series URLs based on pre-defined regex patterns."""
    matches = re.finditer(COMBINED_PATTERN, text)
    return [m.group(0) for m in matches]


def save_results_to_file(results, filepath="./cache/persistent/series_urls.json"):
    """Saves the final results as a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Results saved to: {filepath}")


if __name__ == "__main__":
    # Run the asynchronous tasks
    final_results = asyncio.run(get_initial_urls())
    # Save the results
    save_results_to_file(final_results)
