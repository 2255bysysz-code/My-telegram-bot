import os
import logging
import base64
import qrcode
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI

# Настройки
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "deepseek-flash")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "Ты — полезный ассистент.")
ALLOWED_USER_IDS = os.environ.get("ALLOWED_USER_IDS", "")

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
logging.basicConfig(level=logging.INFO)

def is_allowed(user_id):
    if not ALLOWED_USER_IDS.strip():
        return True
    return str(user_id) in [uid.strip() for uid in ALLOWED_USER_IDS.split(",")]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    await update.message.reply_text(f"Привет! Я работаю на {OPENAI_MODEL}. Отправь текст, фото или команду /qr (например, /qr https://google.com).")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    user_text = update.message.text
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"Ошибка ИИ: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    b64_image = base64.b64encode(photo_bytes).decode('utf-8')
    caption = update.message.caption or "Что на этой картинке? Опиши подробно."
    
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке фото: {e}")

async def handle_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id): return
    text = update.message.text
    qr_text = text.replace('/qr', '').strip()
    
    if not qr_text:
        await update.message.reply_text("Пожалуйста, напиши текст после команды, например: /qr https://google.com")
        return

    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = BytesIO()
        bio.name = 'qr.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        
        await update.message.reply_photo(photo=bio, caption=f"QR-код для: {qr_text}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при создании QR-кода: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CommandHandler("qr", handle_qr))
    app.run_polling()

if __name__ == "__main__":
    main()
