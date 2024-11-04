from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import logging

from config import config
from db_utils import (
    get_urls_to_crawl,
    crawled_url_exists,
    save_crawled_url,
    update_url_to_crawl
)
from bot import send_telegram_message

# Set the prefix for kleinanzeigen.de
prefix = "https://www.kleinanzeigen.de"

# Initialize index to keep track of which URL to crawl next
current_index = 0

# Set up Chrome options for headless browsing
chrome_options = Options()
chrome_options.headless = True
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36")

# Initialize the Chrome WebDriver
driver = webdriver.Chrome(options=chrome_options)


# Crawl a single URL from the list in a round-robin fashion
def crawl_and_notify():
    global current_index
    urls_to_crawl = get_urls_to_crawl()

    # Filter URLs to include only those that start with the specified prefix
    urls_to_crawl = [url_data for url_data in urls_to_crawl if url_data[1].startswith(prefix)]

    # Check if there are URLs to crawl
    if not urls_to_crawl:
        logging.warning("No kleinanzeigen.de URLs to crawl.")
        return

    # Attempt to get the URL at the current index
    try:
        url_data = urls_to_crawl[current_index]
    except IndexError:
        # Reset the index if it is out of bounds and log a warning
        logging.warning("Current index out of bounds, resetting to 0.")
        current_index = 0
        return

    url_id, url, name, created_date, last_checked, last_update = url_data

    try:
        # Use Selenium to load the page
        driver.get(url)
        driver.implicitly_wait(10)  # Wait for the page to fully load

        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        article_links = soup.select('article.aditem div.aditem-main a[href]')

        new_links_found = False
        send_notifications = last_checked is not None

        for link in article_links:
            found_url = link['href']
            full_url = prefix + found_url if not found_url.startswith("https://") else found_url
            if not crawled_url_exists(full_url, url_id):
                save_crawled_url(full_url, url_id)
                if send_notifications:
                    send_telegram_message(f"New kleinanzeigen Product found for {name}:\n{full_url}")
                new_links_found = True

        current_time = datetime.now()
        if new_links_found:
            update_url_to_crawl(url_id, last_checked=current_time, last_update=current_time)
        else:
            update_url_to_crawl(url_id, last_checked=current_time)

    except Exception as e:
        logging.error(f"Unexpected error while processing URL {url}: {e}")

    # Move to the next URL in the list for the next interval
    current_index = (current_index + 1) % len(urls_to_crawl)


# Schedule the crawler
scheduler = BackgroundScheduler()
scheduler.start()


def schedule_crawler():
    scheduler.remove_all_jobs()
    scheduler.add_job(crawl_and_notify, 'interval', seconds=config['check_frequency'], id='crawl_and_notify')


# Ensure to close the driver when done (e.g., at the end of the application or in a shutdown hook)
import atexit

atexit.register(lambda: driver.quit())
