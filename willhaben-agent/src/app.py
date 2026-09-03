import os
import threading

from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from config import config, save_config, SECRET_KEY
from db_utils import (
    init_db,
    add_url_to_crawl,
    delete_url_to_crawl,
    get_urls_to_crawl,
    get_crawled_urls,
    update_url_to_crawl,
    get_deals,
    get_deal_stats,
    get_price_history,
    set_listing_user_state,
)
from listings import human_age, spec_line, location_line, map_link, format_price, draft_inquiry
from crawlers import schedule_crawler
from bot import run_bot, stop_bot, send_telegram_message
import asyncio
import json
import math
from datetime import datetime

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Expose listing formatting helpers to templates
app.jinja_env.globals.update(
    human_age=human_age,
    spec_line=spec_line,
    location_line=location_line,
    map_link=map_link,
    format_price=format_price,
)

_DEAL_STATE_ACTIONS = {
    'save': 'saved',
    'contact': 'contacted',
    'bought': 'bought',
    'mute': 'muted',
    'clear': None,
}


# Flask route for setting configuration and starting the bot
@app.route('/set_config', methods=['POST'])
def set_config():
    config['check_frequency'] = int(request.form['check_frequency'])
    config['telegram_token'] = request.form['telegram_token']
    config['start_password'] = request.form['start_password']
    if request.form.get('offer_factor'):
        try:
            config['offer_factor'] = float(request.form['offer_factor'])
        except ValueError:
            pass
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
            return date_str

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


# Deal feed
@app.route('/deals')
def deals():
    page = int(request.args.get('page', 1))
    per_page = 20
    filters = {
        'q': request.args.get('q', '').strip(),
        'seller': request.args.get('seller', ''),
        'min_price': request.args.get('min_price', ''),
        'max_price': request.args.get('max_price', ''),
        'drops_only': request.args.get('drops_only', ''),
        'state': request.args.get('state', 'active'),
        'sort': request.args.get('sort', 'newest'),
        'source_url_id': request.args.get('source_url_id', ''),
    }
    rows, total = get_deals(filters, page, per_page)
    for row in rows:
        try:
            attrs = json.loads(row.get('attrs_json') or '{}')
        except (ValueError, TypeError):
            attrs = {}
        for key, value in attrs.items():
            row.setdefault(key, value)
        row['specs'] = spec_line(row)
        row['age'] = human_age(row.get('published'))
        row['loc'] = location_line(row)
        row['map'] = map_link(row.get('coordinates', ''), row.get('postcode', ''), row.get('location', ''))
        row['price_history'] = get_price_history(row['ad_id'])
        row['inquiry'] = draft_inquiry(row, float(config.get('offer_factor', 0.87)))
    total_pages = max(1, math.ceil(total / per_page))
    return render_template(
        'deals.html',
        deals=rows,
        total=total,
        page=page,
        total_pages=total_pages,
        filters=filters,
        stats=get_deal_stats(),
        searches=get_urls_to_crawl(),
    )


@app.route('/deals/action', methods=['POST'])
def deal_action():
    ad_id = int(request.form['ad_id'])
    action = request.form.get('action')
    if action not in _DEAL_STATE_ACTIONS:
        flash("Unknown action.")
    else:
        set_listing_user_state(ad_id, _DEAL_STATE_ACTIONS[action])
        flash("Deal updated.")
    return redirect(request.referrer or url_for('deals'))


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


@app.route('/edit_url/<int:url_id>', methods=['GET'])
def edit_url(url_id):
    # Fetch the URL details from the database
    urls_to_crawl = get_urls_to_crawl()
    url_data = None
    for id, url, name, _, _, _ in urls_to_crawl:
        if id == url_id:
            url_data = {'id': id, 'url': url, 'name': name}
            break
    if not url_data:
        flash("URL not found.")
        return redirect(url_for('index'))
    return render_template('edit_url.html', url_data=url_data, config=config)


@app.route('/update_url/<int:url_id>', methods=['POST'])
def update_url(url_id):
    new_url = request.form['url']
    new_name = request.form['name']
    if update_url_to_crawl(url_id, url=new_url, name=new_name):
        flash("URL updated successfully!")
        send_telegram_message(f"Updated URL: {new_name} ({new_url})\n")
    else:
        flash("Failed to update URL.")
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

        serve(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
