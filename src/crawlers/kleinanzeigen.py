import platform
import time
import logging
from datetime import datetime
import traceback
import urllib3
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from config import config
from db_utils import (
    get_urls_to_crawl,
    crawled_url_exists,
    save_crawled_url,
    update_url_to_crawl
)
from bot import send_telegram_message
from selenium.common.exceptions import TimeoutException, WebDriverException, SessionNotCreatedException

# Prefix for kleinanzeigen.de URLs
prefix = "https://www.kleinanzeigen.de"
current_index = 0

# Max retries and wait time on error
MAX_RETRIES = 3
ERROR_WAIT_TIME = 300  # 5 minutes in seconds

# Initialize logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Selenium driver
driver = None


def initialize_driver():
    global driver
    try:
        if platform.system() == "Windows":
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            chrome_options = Options()
            chrome_options.headless = True
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36")

            driver = webdriver.Chrome(options=chrome_options)
        else:
            import undetected_chromedriver as uc
            options = uc.ChromeOptions()
            options.headless = True
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/87.0.4280.88 Safari/537.36")

            driver = uc.Chrome(options=options)

        driver.set_page_load_timeout(30)
        logging.info("Driver initialized successfully.")
    except WebDriverException as e:
        logging.error(f"Failed to initialize WebDriver: {e}")
        raise


def restart_driver():
    global driver
    try:
        if driver:
            driver.quit()
    except Exception as ex:
        logging.error(f"Error during driver quit: {ex}")
    finally:
        initialize_driver()


# Initialize driver at the start
initialize_driver()


def crawl_and_notify():
    global current_index, driver
    urls_to_crawl = get_urls_to_crawl()
    urls_to_crawl = [url_data for url_data in urls_to_crawl if url_data[1].startswith(prefix)]

    if not urls_to_crawl:
        logging.warning("No kleinanzeigen.de URLs to crawl.")
        return

    try:
        url_data = urls_to_crawl[current_index]
    except IndexError:
        logging.warning("Current index out of bounds, resetting to 0.")
        current_index = 0
        return

    url_id, url, name, created_date, last_checked, last_update = url_data
    retries = 0

    while retries < MAX_RETRIES:
        try:
            driver.get(url)
            driver.implicitly_wait(10)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            article_links = soup.select('ul#srchrslt-adtable article.aditem[data-href]')

            new_links_found = False
            send_notifications = last_checked is not None

            for link in article_links:
                found_url = link['data-href']
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

            break  # Exit the retry loop on success

        except (TimeoutException, urllib3.exceptions.MaxRetryError, urllib3.exceptions.NewConnectionError,
                SessionNotCreatedException) as e:
            retries += 1
            logging.warning(
                f"Encountered exception while processing URL {url}, retry {retries}/{MAX_RETRIES}. Waiting for {ERROR_WAIT_TIME} seconds. Error: {e}")
            time.sleep(ERROR_WAIT_TIME)  # Wait before retrying
            if retries == MAX_RETRIES:
                logging.error(f"Failed to load {url} after {MAX_RETRIES} retries. Restarting Selenium driver.")
                restart_driver()
        except WebDriverException as e:
            logging.error(f"WebDriverException encountered: {e}. Restarting Selenium driver.")
            restart_driver()
            break
        except Exception as e:
            logging.error(f"Unexpected error while processing URL {url}: {e}\n{traceback.format_exc()}")
            restart_driver()
            break

    current_index = (current_index + 1) % len(urls_to_crawl)


# Schedule the crawler
scheduler = BackgroundScheduler()
scheduler.start()


def schedule_crawler():
    if not scheduler.running:
        logging.error("Scheduler is not running. Cannot schedule jobs.")
        scheduler.start()

    scheduler.remove_all_jobs()
    scheduler.add_job(crawl_and_notify,
                      'interval',
                      seconds=config['check_frequency'],
                      id='crawl_and_notify',
                      max_instances=1,  # Prevents overlapping jobs
                      replace_existing=True  # Ensures only one instance exists
                      )


schedule_crawler()


def scheduler_health_check():
    if not scheduler.get_job('crawl_and_notify'):
        logging.warning("Crawl job is missing. Rescheduling...")
        schedule_crawler()


scheduler.add_job(scheduler_health_check, 'interval', minutes=5, id='scheduler_health_check')

import atexit

atexit.register(lambda: driver.quit() if driver is not None else None)
