from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import requests
import json
from datetime import datetime
from db_utils import (
    get_urls_to_crawl,
    crawled_url_exists,
    save_crawled_url,
    update_url_to_crawl
)
from bot import send_telegram_message
from config import config, willhaben_prefix
import logging


# Crawl the configured URLs and check for new items
def crawl_and_notify():
    urls_to_crawl = get_urls_to_crawl()
    for url_id, url, name, created_date, last_checked, last_update in urls_to_crawl:
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            script = soup.find('script', type='application/ld+json')

            new_links_found = False
            send_notifications = last_checked is not None

            if script:
                json_data = json.loads(script.string)
                urls = [item["url"] for item in json_data.get('itemListElement', [])]

                for found_url in urls:
                    found_url = willhaben_prefix + found_url
                    if not crawled_url_exists(found_url, url_id):
                        save_crawled_url(found_url, url_id)
                        if send_notifications:
                            send_telegram_message(f"New Product found for product {name}:\n{found_url}")
                        new_links_found = True

                current_time = datetime.now()
                if new_links_found:
                    update_url_to_crawl(url_id, last_checked=current_time, last_update=current_time)
                else:
                    update_url_to_crawl(url_id, last_checked=current_time)
        except Exception as e:
            logging.error(f"Error crawling {url}: {e}")


# Schedule the crawler
scheduler = BackgroundScheduler()
scheduler.start()


def schedule_crawler():
    scheduler.remove_all_jobs()
    scheduler.add_job(crawl_and_notify, 'interval', seconds=config['check_frequency'], id='crawl_and_notify')
