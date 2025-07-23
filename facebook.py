import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from yt_dlp import YoutubeDL

BOT_TOKEN = "7691521101:AAEPuxV1ksuweZjw0X4jFGCp6sNe_stO_pI"
user_data = {}
DOWNLOAD_TTL = 10 * 60  # 10 minutes

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Send me a YouTube, Instagram, or Facebook video URL to download.")

# === Handle URL (YouTube / Instagram / Facebook) ===
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.message.from_user.id
    user_data[user_id] = {"url": url}

    if "instagram.com" in url:
        await update.message.reply_text("⏳ Downloading Instagram video...")
        await download_instagram_video(update, context, url)
        return

    if "facebook.com" in url or "fb.watch" in url:
        await update.message.reply_text("⏳ Downloading Facebook video...")
        await download_facebook_video(update, context, url)
        return

    # YouTube resolution buttons
    buttons = [
        [InlineKeyboardButton("480p", callback_data="480")],
        [InlineKeyboardButton("720p", callback_data="720")],
        [InlineKeyboardButton("1080p", callback_data="1080")],
        [InlineKeyboardButton("4K", callback_data="4k")],
    ]
    await update.message.reply_text(
        "🎞 Choose resolution:", reply_markup=InlineKeyboardMarkup(buttons)
    )

# === Download Instagram Video ===
async def download_instagram_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    await download_social_video(update, context, url, platform="Instagram")

# === Download Facebook Video ===
async def download_facebook_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    await download_social_video(update, context, url, platform="Facebook")

# === Shared Downloader for Instagram & Facebook ===
async def download_social_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, platform=""):
    user_id = update.message.from_user.id
    base_filename = f"{platform.lower()}_{user_id}_{int(time.time())}"
    filename_template = f"{base_filename}.%(ext)s"

    ydl_opts = {
        "outtmpl": filename_template,
        "merge_output_format": "mp4",
        "quiet": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", f"{platform} Video")

        filename = None
        for ext in [".mp4", ".webm", ".mkv"]:
            candidate = f"{base_filename}{ext}"
            if os.path.exists(candidate):
                filename = candidate
                break

        if not filename:
            await context.bot.send_message(chat_id=user_id, text="❌ Downloaded file not found.")
            return

        file_size = os.path.getsize(filename)

        if file_size <= 50 * 1024 * 1024:
            await context.bot.send_video(
                chat_id=user_id,
                video=open(filename, "rb"),
                caption=title
            )
        elif file_size <= 2 * 1024 * 1024 * 1024:
            await context.bot.send_document(
                chat_id=user_id,
                document=open(filename, "rb"),
                filename=os.path.basename(filename),
                caption=title
            )
        else:
            await context.bot.send_message(chat_id=user_id, text="❌ File too big to send (>2GB).")

    except Exception as e:
        await context.bot.send_message(
            chat_id=user_id,
            text=(f"⚠️ Error downloading {platform} video:\n"
                  f"```{str(e)}```"),
            parse_mode="Markdown"
        )

# === YouTube Resolution Selection Handler ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    resolution = query.data
    user_id = query.from_user.id

    if user_id not in user_data:
        await query.edit_message_text("⚠️ Please send a YouTube link first.")
        return

    url = user_data[user_id]["url"]
    await query.edit_message_text(f"⏳ Downloading {resolution}...")

    base_filename = f"{user_id}_{resolution}"
    filename_template = f"{base_filename}.%(ext)s"
    cached_file = None

    # Check for cached file
    for ext in [".mp4", ".mkv", ".webm"]:
        candidate = f"{base_filename}{ext}"
        if os.path.exists(candidate):
            if time.time() - os.path.getmtime(candidate) < DOWNLOAD_TTL:
                cached_file = candidate
                break
            else:
                os.remove(candidate)

    if resolution == "4k":
        ydl_format = "bestvideo[ext=mp4][height>=2160]+bestaudio[ext=m4a]/best"
    else:
        ydl_format = f"bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]/best[height<={resolution}]"

    ydl_opts = {
        "format": ydl_format,
        "outtmpl": filename_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 20,
        "socket_timeout": 30,
        "continuedl": True,
        "quiet": True,
    }

    filename = cached_file
    try:
        title = "video"
        if not cached_file:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "video")

            for ext in [".mp4", ".mkv", ".webm"]:
                candidate = f"{base_filename}{ext}"
                if os.path.exists(candidate):
                    filename = candidate
                    break

            if not filename:
                await context.bot.send_message(chat_id=user_id, text="❌ Download failed.")
                return

        file_size = os.path.getsize(filename)

        if file_size <= 50 * 1024 * 1024:
            await context.bot.send_video(
                chat_id=user_id,
                video=open(filename, "rb"),
                caption=f"{title} - {resolution}"
            )
        elif file_size <= 2 * 1024 * 1024 * 1024:
            await context.bot.send_document(
                chat_id=user_id,
                document=open(filename, "rb"),
                filename=os.path.basename(filename),
                caption=f"{title} - {resolution}"
            )
        else:
            await context.bot.send_message(chat_id=user_id, text="❌ File too big to send (>2GB).")

    except Exception as e:
        await context.bot.send_message(
            chat_id=user_id,
            text=(f""
                  f"```{str(e)}```\n"
                  f"💡 Try another resolution or check the link."),
            parse_mode="Markdown"
        )

# === Run Bot ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
