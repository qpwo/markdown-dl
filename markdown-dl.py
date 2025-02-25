#!/usr/bin/env python3
"""
cd $(git rev-parse --show-toplevel)
mkdir -p chrome
cd chrome
echo *
trash *
echo '*' > .gitignore
wget https://storage.googleapis.com/chrome-for-testing-public/135.0.7023.0/linux64/chrome-linux64.zip
wget https://storage.googleapis.com/chrome-for-testing-public/135.0.7023.0/linux64/chromedriver-linux64.zip
unzip chrome-linux64.zip
unzip chromedriver-linux64.zip
trash -v *.zip
ls -lh

sudo apt-get install -y \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0

cd $(git rev-parse --show-toplevel)

export PATH="$(pwd)/chrome/chrome-linux64:$PATH"
export PATH="$(pwd)/chrome/chromedriver-linux64:$PATH"

which chrome
chrome --version

which chromedriver
chromedriver --version

cd $(git rev-parse --show-toplevel)
pip install selenium html2text
python markdown-dl.py urls.txt
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import html2text
import os
from pathlib import Path
import random
import multiprocessing
import argparse
from queue import Empty as EmptyException

# Set up environment and directories
pwd = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = f"{pwd}/chrome/chrome-linux64:{pwd}/chrome/chromedriver-linux64:" + os.environ["PATH"]

save_dir = Path("~/Downloads/markdown-dl").expanduser()
save_dir.mkdir(parents=True, exist_ok=True)

# Shared structures for workers
url_queue = multiprocessing.Queue()
queued_already = multiprocessing.Manager().list()
processed_urls = multiprocessing.Manager().list()


def delay():
    time.sleep(random.random() * 1)


def setup_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")

    here = os.path.dirname(os.path.abspath(__file__))
    service = Service(here + "/chrome/chromedriver-linux64/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def get_reader_mode_content(driver, url):
    delay()
    try:
        driver.get(url)
        time.sleep(3)  # Wait for page to load

        content_selectors = ["#content", "article", "main", ".article-content", ".post-content"]

        content = ""
        for selector in content_selectors:
            try:
                element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                content = element.get_attribute("innerHTML")
                if content:
                    break
            except TimeoutException:
                continue

        if not content:
            print(f"{url}: No content found with selectors")
            content = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        markdown_content = h.handle(content)
        markdown_content = markdown_content.replace("\n\ncopy\n\n", "\n\n")

        return markdown_content, driver.page_source

    except Exception as e:
        print(f"Error processing {url}: {e}")
        return None, None


def url_to_filename(url):
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace("?", "_").replace("&", "_")


def extract_links(driver, crawl_prefix):
    # Use the WebDriver to find all <a> elements with href attributes
    links = set()
    try:
        elements = driver.find_elements(By.TAG_NAME, "a")
        for element in elements:
            href = element.get_attribute("href")
            if href and href.startswith(crawl_prefix):
                href = href.split("#")[0]  # Remove fragment
                links.add(href)
        return links
    except Exception as e:
        print(f"Error extracting links: {e}")
        return []


def worker_process(crawl_prefix=None):
    driver = setup_driver()
    try:
        while True:
            try:
                # Non-blocking get with timeout
                url = url_queue.get(timeout=1)

            except EmptyException:
                print(f"queue is empty")
                # Queue is empty, exit the worker
                break

            # Skip if already processed
            if url in processed_urls:
                continue

            processed_urls.append(url)
            print(f"Processing: {url}")

            filename = save_dir / f"{url_to_filename(url)}.md"
            if filename.exists():
                print(f"File {filename} already exists. Skipping.")
                continue

            content, html_source = get_reader_mode_content(driver, url)
            if not content:
                print(f"Failed to retrieve content for {url}")
                continue

            with open(filename, "w") as f:
                f.write(content)
            print(f"Saved {url} to {filename}")

            # Add new links to the queue if crawling is enabled
            if crawl_prefix and driver:
                new_links = extract_links(driver, crawl_prefix)
                print(f"Found {len(new_links)} new links")
                for link in new_links:
                    if link not in processed_urls and link not in queued_already:
                        url_queue.put(link)
                        queued_already.append(link)
                        print(f"Added to queue: {link}")

    except Exception as e:
        print(f"Worker error: {e}")
    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("urls_file", nargs="?", default="urls.txt")
    parser.add_argument("--crawl-prefix", help="URL prefix to crawl for additional links")
    args = parser.parse_args()

    # Read URLs from file
    with open(args.urls_file, "r") as file:
        urls = [line.strip() for line in file if line.strip()]

    print(f"Loaded {len(urls)} URLs")

    # Add all initial URLs to the queue
    for url in urls:
        url_queue.put(url)
        queued_already.append(url)

    # Always start 4 workers
    workers = []
    for _ in range(4):
        p = multiprocessing.Process(target=worker_process, args=(args.crawl_prefix,))
        workers.append(p)
        p.start()

    # Wait for all workers to finish
    for p in workers:
        p.join()

    print("All workers completed")


if __name__ == "__main__":
    main()
