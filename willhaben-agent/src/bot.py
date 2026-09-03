import threading
import json
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import asyncio
import logging
from db_utils import (
    save_chat_id,
    add_url_to_crawl,
    get_urls_to_crawl,
    delete_url_to_crawl,
    get_chat_ids,
    remove_chat_id,  # Function to remove a chat ID from the database
    get_listing,
    set_listing_user_state,
)
from listings import build_caption, draft_inquiry, map_link
from config import config

# Set up logging
logging.basicConfig(level=logging.INFO)

# Global variable to store the bot application
bot_application = None


# Telegram command handlers with password check for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    # Check if password is provided and correct
    if len(context.args) < 1 or context.args[0] != config['start_password']:
        await update.message.reply_text("Invalid password. Please use: /start <password>")
        return

    # Save chat ID if the password is correct
    save_chat_id(chat.id, chat.type)
    await update.message.reply_text("Hello! I'm your crawling bot. Use /help to see available commands.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Here are the available commands:\n"
        "/start <password> - Start the bot and save your chat ID\n"
        "/help - Show this help message\n"
        "/addurl <name> <url> - Add a new URL to crawl with a given name\n"
        "/listurls - List all URLs being crawled\n"
        "/removeurl <id> - Remove a URL from the crawl list by its ID\n"
        "/stop - Stop receiving messages from this bot and remove your chat ID"
    )
    await update.message.reply_text(help_text)


async def addurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    save_chat_id(chat.id, chat.type)

    if len(context.args) >= 2:
        name = ' '.join(context.args[:len(context.args) -1])
        url = context.args[len(context.args)-1]
        if add_url_to_crawl(url, name):
            await update.message.reply_text(f"URL added to crawl list: {url} with name: {name}")
        else:
            await update.message.reply_text("URL already exists in the crawl list.")
    else:
        await update.message.reply_text(
            "Please provide a name and a URL after the /addurl command. Example: /addurl MySite https://example.com"
        )


async def listurls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = get_urls_to_crawl()
    if urls:
        message = "URLs being crawled:\n"
        for id, url, name, created_date, last_checked, last_update in urls:
            message += f"{id}: {url} - {name}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("No URLs are currently being crawled.")


async def removeurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            url_id = int(context.args[0])
            delete_url_to_crawl(url_id)
            await update.message.reply_text(f"URL with ID {url_id} has been removed from the crawl list.")
        except ValueError:
            await update.message.reply_text("Please provide a valid numeric ID.")
    else:
        await update.message.reply_text("Please provide the ID of the URL to remove after the /removeurl command.")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if remove_chat_id(chat.id):
        await update.message.reply_text("Bot stopped, and your chat ID has been removed.")
    else:
        await update.message.reply_text("You weren't registered, but the bot has been stopped for you.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that command. Use /help to see available commands.")


# --------------------------------------------------------------------------- #
# Outgoing messages
# --------------------------------------------------------------------------- #
def _run_send(token, chat_id, coro_builder):
    async def _do():
        async with Bot(token=token) as bot:
            await coro_builder(bot, chat_id)

    try:
        asyncio.run(_do())
    except Exception as e:
        logging.error(f"Error sending message to Telegram chat {chat_id}: {e}")


def _send_to_all(coro_builder):
    """coro_builder(bot, chat_id) -> awaitable, dispatched to every chat."""
    token = config.get('telegram_token')
    if not token:
        logging.warning("No telegram_token configured; message not sent.")
        return
    for chat_id in get_chat_ids():
        threading.Thread(
            target=_run_send, args=(token, chat_id, coro_builder), daemon=True
        ).start()


# Send a plain Telegram text message to all chats
def send_telegram_message(message):
    logging.info(f"Sending Telegram chat message: {message}")
    _send_to_all(lambda bot, cid: bot.send_message(chat_id=cid, text=message))


def _deal_keyboard(listing):
    ad_id = listing.get('ad_id')
    if not ad_id:
        return None
    rows = [
        [
            InlineKeyboardButton("⭐ Merken", callback_data=f"d:save:{ad_id}"),
            InlineKeyboardButton("✉️ Kontaktiert", callback_data=f"d:contact:{ad_id}"),
            InlineKeyboardButton("✅ Gekauft", callback_data=f"d:bought:{ad_id}"),
        ],
        [
            InlineKeyboardButton("\U0001f507 Stumm", callback_data=f"d:mute:{ad_id}"),
            InlineKeyboardButton("✍️ Nachricht", callback_data=f"d:draft:{ad_id}"),
        ],
    ]
    link = map_link(
        listing.get('coordinates', ''),
        listing.get('postcode', ''),
        listing.get('location', ''),
    )
    if link:
        rows[1].append(InlineKeyboardButton("\U0001f5fa️ Karte", url=link))
    return InlineKeyboardMarkup(rows)


def send_listing_notification(listing, kind="new", old_price=None, search_name=None):
    """Send a rich listing card (photo + caption + inline buttons)."""
    caption = build_caption(listing, kind, old_price, search_name)
    markup = _deal_keyboard(listing)
    image = listing.get('image_url')

    async def _send(bot, chat_id):
        if image:
            try:
                await bot.send_photo(
                    chat_id=chat_id, photo=image, caption=caption,
                    parse_mode='HTML', reply_markup=markup,
                )
                return
            except Exception as e:
                logging.warning(f"send_photo failed ({e}); falling back to text.")
        await bot.send_message(
            chat_id=chat_id, text=caption, parse_mode='HTML',
            reply_markup=markup, disable_web_page_preview=False,
        )

    logging.info(f"Sending listing notification ({kind}): {listing.get('url')}")
    _send_to_all(lambda bot, cid: _send(bot, cid))


_STATE_ACTIONS = {
    'save': ('saved', "⭐ Gemerkt"),
    'contact': ('contacted', "✉️ Als kontaktiert markiert"),
    'bought': ('bought', "✅ Als gekauft markiert"),
    'mute': ('muted', "\U0001f507 Stummgeschaltet"),
}


def _html_escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def deal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        _, action, ad_id_raw = query.data.split(":")
        ad_id = int(ad_id_raw)
    except (ValueError, AttributeError):
        await query.answer("Ungültige Aktion")
        return

    if action == 'draft':
        listing = get_listing(ad_id)
        if not listing:
            await query.answer("Inserat nicht gefunden")
            return
        data = listing
        if listing.get('attrs_json'):
            try:
                data = json.loads(listing['attrs_json'])
            except (ValueError, TypeError):
                pass
        try:
            factor = float(config.get('offer_factor', 0.87))
        except (ValueError, TypeError):
            factor = 0.87
        text = draft_inquiry(data, offer_factor=factor)
        await query.answer("Textvorschlag erstellt")
        await query.message.reply_text(
            "✍️ <b>Nachrichtenvorschlag</b> (zum Kopieren):\n\n"
            f"<code>{_html_escape(text)}</code>",
            parse_mode='HTML',
        )
        return

    if action in _STATE_ACTIONS:
        state, label = _STATE_ACTIONS[action]
        set_listing_user_state(ad_id, state)
        await query.answer(label)
        return

    await query.answer()


# Run the Telegram bot as a background task
async def run_bot():
    global bot_application
    if bot_application:
        logging.warning("Bot is already running. Stopping it first.")
        await stop_bot()

    bot_application = Application.builder().token(config['telegram_token']).build()

    # Add command handlers
    bot_application.add_handler(CommandHandler('start', start))
    bot_application.add_handler(CommandHandler('help', help_command))
    bot_application.add_handler(CommandHandler('addurl', addurl))
    bot_application.add_handler(CommandHandler('listurls', listurls))
    bot_application.add_handler(CommandHandler('removeurl', removeurl))
    bot_application.add_handler(CommandHandler('stop', stop_command))  # Register stop command
    bot_application.add_handler(CallbackQueryHandler(deal_callback, pattern=r"^d:"))
    bot_application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Initialize and start the bot
    await bot_application.initialize()
    await bot_application.start()
    await bot_application.updater.start_polling()
    logging.info("Telegram bot started.")
    await asyncio.Event().wait()


# Stop the Telegram bot if it's running
async def stop_bot():
    global bot_application
    if bot_application:
        try:
            await bot_application.updater.stop()
            await bot_application.stop()
            bot_application = None
            logging.info("Telegram bot stopped.")
        except Exception as e:
            logging.error(f"Failed to stop the bot: {e}")


# Start the bot if run directly
if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        asyncio.run(stop_bot())
