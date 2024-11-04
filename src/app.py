import os
import threading

from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from config import config, save_config, SECRET_KEY
from db_utils import (
    init_db,
    add_url_to_crawl,
    delete_url_to_crawl,
    get_urls_to_crawl,
    get_crawled_urls
)
from crawlers import schedule_crawler
from bot import run_bot, stop_bot, send_telegram_message
import asyncio
import math
from datetime import datetime

app = Flask(__name__)
app.secret_key = SECRET_KEY


# Flask route for setting configuration and starting the bot
@app.route('/set_config', methods=['POST'])
def set_config():
    config['check_frequency'] = int(request.form['check_frequency'])
    config['telegram_token'] = request.form['telegram_token']
    config['start_password'] = request.form['start_password']
    flash("Configuration updated!")

    # Save the updated config to the JSON file
    save_config()

    # Stop the bot if it's running
    asyncio.run(stop_bot())

    # Start the bot as a background thread without waiting
    threading.Thread(target=lambda: asyncio.run(run_bot())).start()

    # Reschedule the crawler
    schedule_crawler()
    return redirect(url_for('index'))


# Index route
@app.route('/')
def index():
    urls_to_crawl = get_urls_to_crawl()
    formatted_urls = []
    for id, url, name, created_date, last_checked, last_update in urls_to_crawl:

        # Helper function to parse dates with optional microseconds
        def parse_date(date_str):
            if date_str:
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f').strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
            return  date_str

        # Parse each date with the helper function
        created_date = parse_date(created_date)
        last_checked = parse_date(last_checked)
        last_update = parse_date(last_update)

        formatted_urls.append({
            'id': id,
            'url': url,
            'name': name,
            'created_date': created_date,
            'last_checked': last_checked,
            'last_update': last_update
        })

    return render_template('index.html', config=config, urls_to_crawl=formatted_urls)


# History route with pagination
@app.route('/history')
def history():
    page = int(request.args.get('page', 1))
    per_page = 10
    crawled_urls, total = get_crawled_urls(page, per_page)
    total_pages = math.ceil(total / per_page)
    return render_template('history.html', crawled_urls=crawled_urls, page=page, total_pages=total_pages)


# History data route for auto-update
@app.route('/history_data')
def history_data():
    page = int(request.args.get('page', 1))
    per_page = 10
    crawled_urls, total = get_crawled_urls(page, per_page)
    data = []
    for url, crawled_at, source_url in crawled_urls:
        # Convert crawled_at to datetime if it's a string
        if isinstance(crawled_at, str):
            try:
                crawled_at = datetime.strptime(crawled_at, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                crawled_at = datetime.strptime(crawled_at, '%Y-%m-%d %H:%M:%S')

        data.append({
            'url': url,
            'source_url': source_url,
            'crawled_at': crawled_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'data': data, 'total': total})


# Add URL route
@app.route('/add_url', methods=['POST'])
def add_url():
    url = request.form['url']
    name = request.form['name']
    if add_url_to_crawl(url, name):
        flash("URL added to crawl list!")
        send_telegram_message(f"Added URL to Crawl List: {name} ({url})\n")
    else:
        flash("URL already exists in the crawl list.")
    return redirect(url_for('index'))


# Delete URL route
@app.route('/delete_url/<int:url_id>', methods=['POST'])
def delete_url(url_id):
    delete_url_to_crawl(url_id)
    flash("URL removed from crawl list.")
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    schedule_crawler()
    threading.Thread(target=lambda: asyncio.run(run_bot())).start()

    if os.getenv('FLASK_ENV') == 'development':
        # For development, use Flask’s built-in server
        app.run(debug=False)
    else:
        # For production, serve with Waitress
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
