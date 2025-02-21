import asyncio
import os
import re
import logging
from pathlib import Path
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from cachetools import TTLCache

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set Windows event loop policy
if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TOKEN = "YOUR_BOT_TOKEN"
DEVELOPER_CHAT_ID = None  

# Caching for short-term storage (e.g., 10 min cache)
cache = TTLCache(maxsize=100, ttl=600)

# Create an Instaloader instance
L = instaloader.Instaloader(
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False
)

# Regular expressions for Instagram URLs
INSTAGRAM_URL_PATTERN = re.compile(
    r'(https?://)?(www\.)?(instagram\.com|instagr\.am)/(?:p|reel|tv)/([^/?#&]+)'
)

TEMP_FOLDER = "temp_downloads"

async def cleanup_temp():
    """Deletes the temp folder every 5 minutes."""
    while True:
        await asyncio.sleep(300)  # Wait 5 minutes
        if os.path.exists(TEMP_FOLDER):
            try:
                for file in Path(TEMP_FOLDER).glob("*"):
                    file.unlink()
                os.rmdir(TEMP_FOLDER)
                logger.info("✅ Temp folder cleaned up!")
            except Exception as e:
                logger.error(f"❌ Error deleting temp folder: {e}")

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
    else:
        await update.message.reply_text(
            "❓ Please send a valid Instagram post or reel link.\n"
            "Example: https://www.instagram.com/p/ABC123/"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    shortcode = data[1]
    
    processing_message = await query.message.reply_text("⏳ Processing your request...")

    # Check cache
    caption_text = None
    media_files = []

    if shortcode in cache:
        cached_data = cache[shortcode]
        caption_text = cached_data.get("caption")
        media_files = cached_data.get("media", [])
        logger.info(f"Using cached data for shortcode: {shortcode}")

    else:
        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            
            caption_text = post.caption if post.caption else "No caption found."
            os.makedirs(TEMP_FOLDER, exist_ok=True)
            
            L.download_post(post, target=Path(TEMP_FOLDER))
            files = list(Path(TEMP_FOLDER).glob("*"))
            media_files = [f for f in files if f.suffix in ['.jpg', '.jpeg', '.png', '.mp4']]
            
            cache[shortcode] = {"caption": caption_text, "media": media_files}

        except Exception as e:
            logger.error(f"Error processing {shortcode}: {e}")
            await processing_message.edit_text(f"❌ Error: {str(e)}")
            return

    # Send only what was requested
    if action in ["caption", "both"]:
        if caption_text:
            await query.message.reply_text(f"📝 *Caption:*\n\n{caption_text}", parse_mode="Markdown")
        else:
            await query.message.reply_text("❌ No caption found.")

    if action in ["media", "both"]:
        if media_files:
            await processing_message.edit_text("📤 Uploading media to Telegram...")
            for media_file in media_files:
                if media_file.exists():
                    if media_file.suffix in ['.jpg', '.jpeg', '.png']:
                        await query.message.reply_photo(photo=open(media_file, 'rb'))
                    elif media_file.suffix == '.mp4':
                        await query.message.reply_video(video=open(media_file, 'rb'))
                else:
                    await query.message.reply_text("❌ Media file not found. Try again.")
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
    
    # Run temp folder cleanup in the background
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup_temp())

    application.run_polling()
    logger.info("Bot stopped gracefully")

if __name__ == "__main__":
    main()
