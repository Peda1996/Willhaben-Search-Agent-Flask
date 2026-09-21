import asyncio
import logging
import threading

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import config
from db_utils import (
    add_url_to_crawl,
    create_invitation,
    create_space,
    delete_url_to_crawl,
    get_active_space,
    get_chat_ids,
    get_member_role,
    get_space_members,
    get_spaces,
    get_url_to_crawl,
    get_urls_to_crawl,
    is_chat_registered,
    join_space,
    remove_chat_id,
    save_chat_id,
    set_active_space,
    set_notifications,
)


logging.basicConfig(level=logging.INFO)
bot_application = None


def _chat_name(chat, user):
    return chat.title or user.full_name or user.username


async def _active_space_or_prompt(update):
    chat_id = update.effective_chat.id
    if not is_chat_registered(chat_id):
        await update.message.reply_text("Bitte zuerst mit /start <Passwort> registrieren.")
        return None
    space = get_active_space(chat_id)
    if not space:
        await update.message.reply_text("Kein aktiver Suchraum. Nutze /spaces und danach /use <Nummer>.")
    return space


def _can_edit(space, chat_id):
    return get_member_role(space['id'], chat_id) in {'owner', 'editor'}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if len(context.args) < 1 or context.args[0] != config['start_password']:
        await update.message.reply_text("Ungültiges Passwort. Nutzung: /start <Passwort>")
        return
    save_chat_id(chat.id, chat.type, _chat_name(chat, update.effective_user))
    space = get_active_space(chat.id)
    await update.message.reply_text(
        f"Willkommen! Dein aktiver Suchraum ist „{space['name']}“.\n\n"
        "Der Standardraum „Allgemein“ enthält die bisherigen gemeinsamen Suchen. "
        "Mit /create <Name> erzeugst du einen getrennten Raum. "
        "Mit /spaces siehst du deine Räume, mit /use <Nummer> wechselst du.\n\n"
        "Alle Befehle erklärt /help."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Suchräume trennen Suchen, Treffer und Benachrichtigungen. Ein Telegram-Chat kann Mitglied in mehreren Räumen sein.\n\n"
        "Grundlagen\n"
        "/start <Passwort> – Chat registrieren und „Allgemein“ beitreten\n"
        "/spaces – eigene Suchräume anzeigen\n"
        "/use <Nummer oder Name> – aktiven Suchraum wechseln\n"
        "/create <Name> – neuen Suchraum erstellen\n"
        "/join <Code> – per Einladung beitreten\n\n"
        "Suchen im aktiven Raum\n"
        "/addurl <Name> <URL> – Suche hinzufügen\n"
        "/listurls – Suchen anzeigen\n"
        "/removeurl <ID> – Suche entfernen\n\n"
        "Zusammenarbeit\n"
        "/invite [viewer|editor] – Einladung erstellen (nur Owner)\n"
        "/members – Mitglieder anzeigen\n"
        "/notify on|off – Meldungen für den aktiven Raum an-/ausschalten\n"
        "/stop – Chat vollständig abmelden\n\n"
        "Im Browser kannst du Suchräume, Mitglieder, Rollen und Einladungen ebenfalls verwalten."
    )


async def spaces(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    entries = get_spaces(update.effective_chat.id)
    lines = ["Deine Suchräume:"]
    for item in entries:
        marker = "• aktiv" if item['id'] == space['id'] else ""
        default = " (Standard)" if item['is_default'] else ""
        lines.append(f"{item['id']}: {item['name']}{default} — {item['role']} {marker}".rstrip())
    lines.append("\nWechsel: /use <Nummer oder Name>")
    await update.message.reply_text("\n".join(lines))


async def use_space(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_chat_registered(update.effective_chat.id):
        await _active_space_or_prompt(update)
        return
    if not context.args:
        await update.message.reply_text("Nutzung: /use <Nummer oder Name>")
        return
    space = set_active_space(update.effective_chat.id, " ".join(context.args))
    if not space:
        await update.message.reply_text("Diesen Suchraum findest du nicht. Nutze /spaces für die Liste.")
        return
    await update.message.reply_text(f"Aktiver Suchraum: „{space['name']}“.")


async def create_space_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_chat_registered(update.effective_chat.id):
        await _active_space_or_prompt(update)
        return
    name = " ".join(context.args).strip()
    if not name:
        await update.message.reply_text("Nutzung: /create <Name des Suchraums>")
        return
    space_id = create_space(name, creator_chat_id=update.effective_chat.id)
    if not space_id:
        await update.message.reply_text("Der Name ist leer oder wird bereits verwendet.")
        return
    await update.message.reply_text(
        f"Suchraum „{name}“ erstellt und aktiviert.\n"
        "Füge mit /addurl eine Suche hinzu oder erstelle mit /invite eine Einladung."
    )


async def join_space_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    if not context.args:
        await update.message.reply_text("Nutzung: /join <Einladungs-Code>")
        return
    invitation, error = join_space(update.effective_chat.id, context.args[0])
    if error:
        await update.message.reply_text(error)
        return
    await update.message.reply_text(
        f"Du bist „{invitation['name']}“ als {invitation['role']} beigetreten. Der Raum ist jetzt aktiv."
    )


async def addurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    if not _can_edit(space, update.effective_chat.id):
        await update.message.reply_text("Du darfst in diesem Suchraum keine Suchen ändern.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Nutzung: /addurl <Name> <URL>\nBeispiel: /addurl Wohnung Wien https://example.com")
        return
    name, url = " ".join(context.args[:-1]), context.args[-1]
    if add_url_to_crawl(url, name, space['id']):
        await update.message.reply_text(f"Suche in „{space['name']}“ hinzugefügt:\n{name}\n{url}")
    else:
        await update.message.reply_text("Diese URL existiert bereits in einer Suche.")


async def listurls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    urls = get_urls_to_crawl(space['id'])
    if not urls:
        await update.message.reply_text(f"In „{space['name']}“ sind noch keine Suchen aktiv.")
        return
    lines = [f"Suchen in „{space['name']}“:"]
    for item in urls:
        lines.append(f"{item['id']}: {item['name']}\n{item['url']}")
    await update.message.reply_text("\n\n".join(lines))


async def removeurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    if not _can_edit(space, update.effective_chat.id):
        await update.message.reply_text("Du darfst in diesem Suchraum keine Suchen ändern.")
        return
    try:
        url_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Nutzung: /removeurl <ID>")
        return
    url_data = get_url_to_crawl(url_id)
    if not url_data or url_data['space_id'] != space['id'] or not delete_url_to_crawl(url_id, space['id']):
        await update.message.reply_text("Diese Suche gehört nicht zum aktiven Raum oder existiert nicht.")
        return
    await update.message.reply_text(f"Suche {url_id} aus „{space['name']}“ entfernt.")


async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    if get_member_role(space['id'], update.effective_chat.id) != 'owner':
        await update.message.reply_text("Nur Owner können Einladungen erstellen.")
        return
    role = context.args[0].lower() if context.args else 'editor'
    if role not in {'editor', 'viewer'}:
        await update.message.reply_text("Nutzung: /invite [viewer|editor]")
        return
    code = create_invitation(space['id'], role)
    await update.message.reply_text(
        f"Einladung für „{space['name']}“ ({role}, 7 Tage gültig):\n\n/join {code}\n\n"
        "Diesen Befehl einfach an den gewünschten Telegram-Chat weiterleiten."
    )


async def members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    lines = [f"Mitglieder von „{space['name']}“:"]
    for member in get_space_members(space['id']):
        label = member['chat_name'] or f"Chat {member['chat_id']}"
        notifications = "Meldungen an" if member['notifications_enabled'] else "Meldungen aus"
        lines.append(f"• {label} — {member['role']}, {notifications}")
    await update.message.reply_text("\n".join(lines))


async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    space = await _active_space_or_prompt(update)
    if not space:
        return
    if not context.args or context.args[0].lower() not in {'on', 'off'}:
        await update.message.reply_text("Nutzung: /notify on oder /notify off")
        return
    enabled = context.args[0].lower() == 'on'
    set_notifications(space['id'], update.effective_chat.id, enabled)
    await update.message.reply_text(f"Benachrichtigungen für „{space['name']}“ sind jetzt {'an' if enabled else 'aus'}.")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if remove_chat_id(update.effective_chat.id):
        await update.message.reply_text("Dieser Chat wurde vollständig abgemeldet und erhält keine Benachrichtigungen mehr.")
    else:
        await update.message.reply_text("Dieser Chat war nicht registriert.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Diesen Befehl kenne ich nicht. Mit /help siehst du alle Möglichkeiten.")


def send_telegram_message(message, space_id=None):
    """Send only to members of the affected workspace with notifications enabled."""
    chat_ids = get_chat_ids(space_id)
    logging.info("Sending Telegram message to workspace %s, chats: %s", space_id, chat_ids)
    for chat_id in chat_ids:
        try:
            bot = Bot(token=config['telegram_token'])
            threading.Thread(target=lambda chat_id=chat_id: asyncio.run(bot.send_message(chat_id=chat_id, text=message)),
                             daemon=True).start()
        except Exception as error:
            logging.error("Error sending Telegram message to %s: %s", chat_id, error)


async def run_bot():
    global bot_application
    if bot_application:
        await stop_bot()
    bot_application = Application.builder().token(config['telegram_token']).build()
    for command, handler in (
        ('start', start), ('help', help_command), ('spaces', spaces), ('use', use_space),
        ('create', create_space_command), ('join', join_space_command), ('addurl', addurl),
        ('listurls', listurls), ('removeurl', removeurl), ('invite', invite),
        ('members', members), ('notify', notify), ('stop', stop_command),
    ):
        bot_application.add_handler(CommandHandler(command, handler))
    bot_application.add_handler(MessageHandler(filters.COMMAND, unknown))
    await bot_application.initialize()
    await bot_application.start()
    await bot_application.updater.start_polling()
    logging.info("Telegram bot started.")
    await asyncio.Event().wait()


async def stop_bot():
    global bot_application
    if bot_application:
        try:
            await bot_application.updater.stop()
            await bot_application.stop()
            bot_application = None
            logging.info("Telegram bot stopped.")
        except Exception as error:
            logging.error("Failed to stop the bot: %s", error)
