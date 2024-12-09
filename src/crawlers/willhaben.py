from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import requests
import json
from datetime import datetime

from config import config
from db_utils import (
    get_urls_to_crawl,
    crawled_url_exists,
    save_crawled_url,
    update_url_to_crawl
)
from bot import send_telegram_message
import logging

willhaben_prefix = "https://www.willhaben.at"

# Initialize index to keep track of which URL to crawl next
current_index = 0


# Crawl a single URL from the list in a round-robin fashion
def crawl_and_notify():
    global current_index
    urls_to_crawl = get_urls_to_crawl()

    # Filter URLs to include only those that start with willhaben_prefix
    urls_to_crawl = [url_data for url_data in urls_to_crawl if url_data[1].startswith(willhaben_prefix)]

    # Check if there are URLs to crawl
    if not urls_to_crawl:
        logging.warning("No willhaben URLs to crawl.")
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
        response = requests.get(url, timeout=10)  # Set a timeout to avoid hanging
        response.raise_for_status()  # Raise an error if the response is not 200
    except requests.RequestException as e:
        logging.error(f"Network error while crawling {url}: {e}")
        return

    try:
        soup = BeautifulSoup(response.content, 'html.parser')
        script = soup.find('script', type='application/ld+json')

        new_links_found = False
        send_notifications = last_checked is not None

        if script:
            json_data = json.loads(script.string)
            urls = [item["url"] for item in json_data.get('itemListElement', [])]

            for found_url in urls:
                full_url = willhaben_prefix + found_url
                if not crawled_url_exists(full_url, url_id):
                    save_crawled_url(full_url, url_id)
                    if send_notifications:
                        send_telegram_message(f"🆕{name}:\n{full_url}")
                    new_links_found = True

            current_time = datetime.now()
            if new_links_found:
                update_url_to_crawl(url_id, last_checked=current_time, last_update=current_time)
            else:
                update_url_to_crawl(url_id, last_checked=current_time)

    except (json.JSONDecodeError, AttributeError) as e:
        logging.error(f"Error parsing data for URL {url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while processing URL {url}: {e}")

    # Move to the next URL in the list for the next interval
    current_index = (current_index + 1) % len(urls_to_crawl)


# Schedule the crawler
scheduler = BackgroundScheduler()


def schedule_crawler():
    if not scheduler.running:
        logging.error("Scheduler is not running. Cannot schedule jobs.")
        scheduler.start()

    scheduler.remove_all_jobs()
    scheduler.add_job(crawl_and_notify, 'interval', seconds=config['check_frequency'], id='crawl_and_notify')
