#!/usr/bin/env python3
"""
cd chrome
echo *
trash *
wget https://storage.googleapis.com/chrome-for-testing-public/132.0.6834.110/linux64/chrome-linux64.zip
wget https://storage.googleapis.com/chrome-for-testing-public/132.0.6834.110/linux64/chromedriver-linux64.zip
unzip chrome-linux64.zip
unzip chromedriver-linux64.zip
trash -v *.zip
ls -lh
export PATH="$(pwd)/chrome-linux64:$PATH"
export PATH="$(pwd)/chromedriver-linux64:$PATH"
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
import concurrent.futures
from functools import partial
import os
pwd = os.path.dirname(os.path.abspath(__file__))
os.environ['PATH'] = f"{pwd}/chrome/chrome-linux64:{pwd}/chrome/chromedriver-linux64:" + os.environ['PATH']

save_dir = Path("~/Downloads/markdown-dl").expanduser()
save_dir.mkdir(parents=True, exist_ok=True)

def delay():
    time.sleep(random.random() * 1)
def setup_driver():
    # Set up Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')  # Run in headless mode

    # Initialize the driver
    here = os.path.dirname(os.path.abspath(__file__))
    service = Service(here + '/chrome/chromedriver-linux64/chromedriver')  # Replace with your chromedriver path
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_reader_mode_content(driver, url):
    delay()
    try:
        # Load the page
        driver.get(url)
        delay()
        time.sleep(3)  # Wait for page to load

        # Try to find the main content
        content_selectors = [
            "#content",
            "article",
            "main",
            ".article-content",
            ".post-content"
        ]

        content = ""
        for selector in content_selectors:
            try:
                element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                content = element.get_attribute('innerHTML')
                if content:
                    break
            except TimeoutException:
                continue

        if not content:
            # If no specific content area found, get the body
            content = driver.find_element(By.TAG_NAME, "body").get_attribute('innerHTML')

        # Convert HTML to Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        markdown_content = h.handle(content)

        return markdown_content

    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return None

def url_to_filename(url):
    # Convert URL to a valid filename
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace("?", "_").replace("&", "_")

def dl_url(driver, url):
    print(f"Processing: {url}")
    filename = save_dir / f"{url_to_filename(url)}.md"
    if filename.exists():
        print(f"File {filename} already exists. Skipping.")
        return
    content = get_reader_mode_content(driver, url)
    if not content:
        print(f"Failed to retrieve content for {url}")
        return
    with open(filename, 'w') as f:
        f.write(content)
    print(f"Saved\n\t{url}\nto\n\t{filename}\n.")

def process_url_batch(urls):
    driver = setup_driver()
    try:
        for url in urls:
            try:
                dl_url(driver, url)
            except Exception as e:
                print(f"Error processing {url}: {e}")
    finally:
        driver.quit()

def main():
    NUM_WORKERS = 4

    # Read URLs from file
    with open('urls.txt', 'r') as file:
        urls = [line.strip() for line in file if line.strip()]

    # Split URLs into batches
    url_batches = [urls[i::NUM_WORKERS] for i in range(NUM_WORKERS)]

    # Process URL batches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(process_url_batch, batch) for batch in url_batches]
        concurrent.futures.wait(futures)

if __name__ == "__main__":
    main()
