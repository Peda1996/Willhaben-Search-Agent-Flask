import asyncio
import math
import os
import threading

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from bot import run_bot, send_telegram_message, stop_bot
from config import SECRET_KEY, config, save_config
from crawlers import schedule_crawler
from db_utils import (
    add_url_to_crawl,
    create_invitation,
    create_space,
    delete_space,
    delete_url_to_crawl,
    get_crawled_urls,
    get_default_space,
    get_space,
    get_space_members,
    get_spaces,
    get_url_to_crawl,
    get_urls_to_crawl,
    init_db,
    update_space,
    update_space_member,
    update_url_to_crawl,
)
from time_utils import TIMEZONE_NAME, format_local_datetime


app = Flask(__name__)
app.secret_key = SECRET_KEY


def _selected_space():
    """Resolve browser workspace input and always fall back to the migrated default."""
    raw_space_id = request.values.get("space") or request.values.get("space_id")
    try:
        space = get_space(int(raw_space_id)) if raw_space_id else None
    except (TypeError, ValueError):
        space = None
    return space or get_default_space()


def _format_datetime(value):
    return format_local_datetime(value)


@app.route('/set_config', methods=['POST'])
def set_config():
    config['check_frequency'] = int(request.form['check_frequency'])
    config['telegram_token'] = request.form['telegram_token']
    config['start_password'] = request.form['start_password']
    save_config()
    asyncio.run(stop_bot())
    threading.Thread(target=lambda: asyncio.run(run_bot()), daemon=True).start()
    schedule_crawler()
    flash("Konfiguration gespeichert.")
    return redirect(url_for('index', space=_selected_space()['id']))


@app.route('/')
def index():
    space = _selected_space()
    formatted_urls = []
    for row in get_urls_to_crawl(space['id']):
        formatted_urls.append({
            'id': row['id'], 'url': row['url'], 'name': row['name'],
            'created_date': _format_datetime(row['created_date']),
            'last_checked': _format_datetime(row['last_checked']),
            'last_update': _format_datetime(row['last_update']),
        })
    return render_template('index.html', config=config, timezone_name=TIMEZONE_NAME,
                           space=space, spaces=get_spaces(), urls_to_crawl=formatted_urls)


@app.route('/history')
def history():
    space = _selected_space()
    page = max(1, request.args.get('page', 1, type=int))
    crawled_urls, total = get_crawled_urls(space['id'], page, 10)
    formatted_history = [
        {'url': row['url'], 'source_url': row['source_url'], 'crawled_at': _format_datetime(row['crawled_at'])}
        for row in crawled_urls
    ]
    total_pages = max(1, math.ceil(total / 10))
    return render_template('history.html', space=space, spaces=get_spaces(), crawled_urls=formatted_history,
                           timezone_name=TIMEZONE_NAME, page=page, total_pages=total_pages)


@app.route('/history_data')
def history_data():
    space = _selected_space()
    page = max(1, request.args.get('page', 1, type=int))
    crawled_urls, total = get_crawled_urls(space['id'], page, 10)
    return jsonify({'data': [
        {'url': row['url'], 'source_url': row['source_url'], 'crawled_at': _format_datetime(row['crawled_at'])}
        for row in crawled_urls
    ], 'total': total})


@app.route('/add_url', methods=['POST'])
def add_url():
    space = _selected_space()
    url, name = request.form['url'].strip(), request.form['name'].strip()
    if add_url_to_crawl(url, name, space['id']):
        flash(f'„{name}“ wurde zu „{space["name"]}“ hinzugefügt.')
        send_telegram_message(f'➕ Suche hinzugefügt in „{space["name"]}“:\n{name}\n{url}', space['id'])
    else:
        flash("Diese URL existiert bereits in einer Suche.")
    return redirect(url_for('index', space=space['id']))


@app.route('/edit_url/<int:url_id>')
def edit_url(url_id):
    url_data = get_url_to_crawl(url_id)
    if not url_data:
        flash("Suche nicht gefunden.")
        return redirect(url_for('index'))
    return render_template('edit_url.html', url_data=url_data, space=get_space(url_data['space_id']))


@app.route('/update_url/<int:url_id>', methods=['POST'])
def update_url(url_id):
    url_data = get_url_to_crawl(url_id)
    if not url_data:
        flash("Suche nicht gefunden.")
        return redirect(url_for('index'))
    space = get_space(url_data['space_id'])
    if update_url_to_crawl(url_id, space['id'], url=request.form['url'].strip(), name=request.form['name'].strip()):
        flash("Suche aktualisiert.")
        send_telegram_message(f'✏️ Suche aktualisiert in „{space["name"]}“:\n{request.form["name"].strip()}\n{request.form["url"].strip()}', space['id'])
    else:
        flash("Die Suche konnte nicht aktualisiert werden. Möglicherweise existiert die URL bereits.")
    return redirect(url_for('index', space=space['id']))


@app.route('/delete_url/<int:url_id>', methods=['POST'])
def delete_url(url_id):
    url_data = get_url_to_crawl(url_id)
    if not url_data:
        flash("Suche nicht gefunden.")
        return redirect(url_for('index'))
    if delete_url_to_crawl(url_id, url_data['space_id']):
        flash("Suche entfernt.")
    return redirect(url_for('index', space=url_data['space_id']))


@app.route('/spaces/create', methods=['POST'])
def create_space_route():
    space_id = create_space(request.form.get('name', ''), request.form.get('description', ''))
    if space_id:
        flash("Neuer Suchraum erstellt. Du kannst jetzt Suchen hinzufügen oder Mitglieder einladen.")
        return redirect(url_for('index', space=space_id))
    flash("Der Raumname fehlt oder wird bereits verwendet.")
    return redirect(url_for('index'))


@app.route('/spaces/<int:space_id>')
def space_settings(space_id):
    space = get_space(space_id)
    if not space:
        flash("Suchraum nicht gefunden.")
        return redirect(url_for('index'))
    return render_template('space_settings.html', space=space, spaces=get_spaces(),
                           members=get_space_members(space_id), invite=request.args.get('invite'))


@app.route('/spaces/<int:space_id>/update', methods=['POST'])
def update_space_route(space_id):
    if update_space(space_id, request.form.get('name', ''), request.form.get('description', '')):
        flash("Suchraum gespeichert.")
    else:
        flash("Der Raumname fehlt oder wird bereits verwendet.")
    return redirect(url_for('space_settings', space_id=space_id))


@app.route('/spaces/<int:space_id>/invite', methods=['POST'])
def invite_space_member(space_id):
    if not get_space(space_id):
        flash("Suchraum nicht gefunden.")
        return redirect(url_for('index'))
    code = create_invitation(space_id, request.form.get('role', 'editor'))
    return redirect(url_for('space_settings', space_id=space_id, invite=code))


@app.route('/spaces/<int:space_id>/members/<int:chat_id>', methods=['POST'])
def update_member(space_id, chat_id):
    update_space_member(space_id, chat_id, request.form.get('role', 'viewer'), request.form.get('notifications_enabled') == 'on')
    flash("Mitglied gespeichert.")
    return redirect(url_for('space_settings', space_id=space_id))


@app.route('/spaces/<int:space_id>/delete', methods=['POST'])
def delete_space_route(space_id):
    deleted, reason = delete_space(space_id)
    flash("Suchraum gelöscht." if deleted else reason)
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    schedule_crawler()
    threading.Thread(target=lambda: asyncio.run(run_bot()), daemon=True).start()
    if os.getenv('FLASK_ENV') == 'development':
        app.run(debug=False)
    else:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000)
