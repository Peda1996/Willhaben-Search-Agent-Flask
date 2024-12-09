import threading
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio
import logging
from db_utils import (
    save_chat_id,
    add_url_to_crawl,
    get_urls_to_crawl,
    delete_url_to_crawl,
    get_chat_ids,
    remove_chat_id  # Function to remove a chat ID from the database
)
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


# Send Telegram message to all chats
def send_telegram_message(message):
    chat_ids = get_chat_ids()
    logging.info(f"Sending Telegram chat message: {message}, Chat_Ids: {chat_ids}")
    for chat_id in chat_ids:
        try:
            bot = Bot(token=config['telegram_token'])
            threading.Thread(target=lambda: asyncio.run(bot.send_message(chat_id=chat_id, text=message))).start()
        except Exception as e:
            logging.error(f"Error sending message to Telegram chat {chat_id}: {e}")


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
