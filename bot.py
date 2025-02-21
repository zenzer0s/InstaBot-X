import asyncio
import os
import re
import logging
from pathlib import Path
import aiohttp
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from cachetools import TTLCache

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set Windows event loop policy for compatibility
if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TOKEN = "8185026608:AAGBKqTSOMM1Unx430TLikYaAIM-EpzMCxA"
DEVELOPER_CHAT_ID = None  # Will be set when first user starts the bot

# Caching to store fetched data (10 min cache)
cache = TTLCache(maxsize=100, ttl=600)

# Create an Instaloader instance
L = instaloader.Instaloader()

# Regular expressions for Instagram URLs
INSTAGRAM_URL_PATTERN = re.compile(
    r'(https?://)?(www\.)?(instagram\.com|instagr\.am)/(?:p|reel|tv)/([^/?#&]+)'
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global DEVELOPER_CHAT_ID
    if DEVELOPER_CHAT_ID is None:
        DEVELOPER_CHAT_ID = update.effective_chat.id
        logger.info(f"Developer chat ID set to: {DEVELOPER_CHAT_ID}")

    await update.message.reply_text(
        "👋 Hello! I'm Instagram Caption Downloader Bot.\n\n"
        "🔹 Send me an Instagram Reel/Post link to download captions or media.\n"
        "🔹 Use /profile username to download profile pictures.\n\n"
        "Made with ❤️ by @YourUsername"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    match = INSTAGRAM_URL_PATTERN.search(user_text)

    if match:
        shortcode = match.group(4)

        keyboard = [
            [
                InlineKeyboardButton("📝 Caption Only", callback_data=f"caption_{shortcode}"),
                InlineKeyboardButton("📥 Media Only", callback_data=f"media_{shortcode}"),
            ],
            [InlineKeyboardButton("🔄 Both Caption & Media", callback_data=f"both_{shortcode}")],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🔍 Instagram link detected! What would you like to download?",
            reply_markup=reply_markup,
        )

        # **Pre-fetch data to reduce wait time**
        asyncio.create_task(fetch_instagram_data(shortcode))

    else:
        await update.message.reply_text(
            "❓ Please send a valid Instagram post or reel link.\n"
            "Example: https://www.instagram.com/p/ABC123/"
        )

async def fetch_instagram_data(shortcode):
    """Fetch Instagram post caption and media using aiohttp for async requests."""
    if shortcode in cache:
        logger.info(f"Using cached data for shortcode: {shortcode}")
        return cache[shortcode]

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        caption_text = post.caption if post.caption else "No caption found."

        temp_dir = "temp_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        media_urls = []

        if post.typename in ["GraphImage", "GraphSidecar"]:
            media_urls = [post.url] + [sidecar.url for sidecar in post.get_sidecar_nodes()]
        elif post.typename == "GraphVideo":
            media_urls = [post.video_url]

        media_files = await download_media_async(media_urls, temp_dir)

        # Store fetched data in cache
        cache[shortcode] = {"caption": caption_text, "media": media_files}
        return cache[shortcode]

    except Exception as e:
        logger.error(f"Error processing {shortcode}: {e}")
        return None

async def download_media_async(urls, save_dir):
    """Download media asynchronously using aiohttp."""
    media_files = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, url in enumerate(urls):
            ext = ".mp4" if "video" in url else ".jpg"
            filename = Path(save_dir) / f"media_{i}{ext}"
            tasks.append(download_file(session, url, filename))
        media_files = await asyncio.gather(*tasks)
    return media_files

async def download_file(session, url, filename):
    """Helper function to download a file asynchronously."""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                with open(filename, "wb") as f:
                    f.write(await response.read())
                return filename
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return None

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    shortcode = data[1]

    processing_message = await query.message.reply_text("⏳ Processing your request...")

    # Fetch everything in one call (pre-fetched if available)
    fetched_data = await fetch_instagram_data(shortcode)
    if not fetched_data:
        await processing_message.edit_text("❌ Failed to fetch data. Try again later.")
        return

    caption_text = fetched_data["caption"]
    media_files = fetched_data["media"]

    if action in ["caption", "both"]:
        if caption_text:
            await query.message.reply_text(f"📝 *Caption:*\n\n{caption_text}", parse_mode="Markdown")
        else:
            await query.message.reply_text("❌ No caption found.")

    if action in ["media", "both"]:
        if media_files:
            await processing_message.edit_text("📤 Uploading media to Telegram...")
            for media_file in media_files:
                if media_file and Path(media_file).exists():
                    if media_file.endswith(".jpg"):
                        await query.message.reply_photo(photo=open(media_file, 'rb'))
                    elif media_file.endswith(".mp4"):
                        await query.message.reply_video(video=open(media_file, 'rb'))
                else:
                    await query.message.reply_text("❌ Media file not found.")
        else:
            await query.message.reply_text("❌ No media found.")

    await processing_message.edit_text("✅ Done!")

async def post_init(application: Application) -> None:
    bot = application.bot
    logger.info("Bot started successfully!")

    if DEVELOPER_CHAT_ID:
        await bot.send_message(
            chat_id=DEVELOPER_CHAT_ID,
            text="✅ Instagram Caption Downloader Bot has started successfully!"
        )

def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.run_polling()
    logger.info("Bot stopped gracefully")

if __name__ == "__main__":
    main()
