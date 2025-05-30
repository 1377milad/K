import asyncio
import logging
import os
import json
from io import BytesIO
from typing import Dict, Optional
import aiofiles
import aiohttp
import speech_recognition as sr
from gtts import gTTS
from googletrans import Translator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from pydub import AudioSegment
import tempfile

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# کلاس اصلی ربات
class TranslatorBot:
    def run(self):
        """راه‌اندازی ربات"""
        # ایجاد اپلیکیشن
        app = Application.builder().token(self.bot_token).build()
        
        # اضافه کردن هندلرها
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("language", self.language_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CallbackQueryHandler(self.language_callback, pattern="^lang_"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        app.add_handler(MessageHandler(filters.AUDIO, self.handle_audio_message))
        
        # راه‌اندازی ربات
        print("🤖 ربات ترجمه شروع شد...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    async def handle_audio_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت فایل‌های صوتی (نه voice message)"""
        user_id = update.message.from_user.id
        
        if user_id not in self.user_languages:
            keyboard = self.create_language_keyboard()
            await update.message.reply_text(
                "❌ ابتدا زبان مقصد خود را انتخاب کنید:",
                reply_markup=keyboard
            )
            return
        
        target_lang = self.user_languages[user_id]
        
        try:
            processing_msg = await update.message.reply_text("🎵 در حال پردازش فایل صوتی...")
            
            # دانلود فایل صوتی
            audio_file = await update.message.audio.get_file()
            
            # ذخیره موقت فایل
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                await audio_file.download_to_drive(temp_audio.name)
                
                # تبدیل به WAV
                audio = AudioSegment.from_file(temp_audio.name)
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                    audio.export(temp_wav.name, format="wav")
                    
                    # تشخیص گفتار
                    await processing_msg.edit_text("🔄 در حال تشخیص گفتار...")
                    
                    with sr.AudioFile(temp_wav.name) as source:
                        # تنظیم برای کاهش نویز
                        self.recognizer.adjust_for_ambient_noise(source, duration=1)
                        audio_data = self.recognizer.record(source)
                        
                        # تشخیص با زبان‌های مختلف
                        recognized_text = None
                        detected_lang = None
                        
                        # لیست زبان‌های احتمالی برای تشخیص
                        recognition_languages = [
                            ('fa-IR', 'fa'), ('en-US', 'en'), ('ar-SA', 'ar'), 
                            ('tr-TR', 'tr'), ('de-DE', 'de'), ('fr-FR', 'fr'),
                            ('es-ES', 'es'), ('it-IT', 'it'), ('ru-RU', 'ru'),
                            ('zh-CN', 'zh'), ('ja-JP', 'ja'), ('ko-KR', 'ko')
                        ]
                        
                        for google_lang, trans_lang in recognition_languages:
                            try:
                                recognized_text = self.recognizer.recognize_google(
                                    audio_data, language=google_lang
                                )
                                detected_lang = trans_lang
                                break
                            except sr.UnknownValueError:
                                continue
                            except sr.RequestError:
                                continue
                        
                        if not recognized_text:
                            await processing_msg.edit_text(
                                "❌ متأسفانه نتوانستم محتوای صوتی را تشخیص دهم.\n"
                                "لطفاً مطمئن شوید که:\n"
                                "• صدا واضح و بدون نویز باشد\n"
                                "• زبان صحبت از زبان‌های پشتیبانی شده باشد"
                            )
                            return
                        
                        # ترجمه
                        await processing_msg.edit_text("🔄 در حال ترجمه...")
                        
                        if detected_lang != target_lang:
                            translation = self.translator.translate(
                                recognized_text, src=detected_lang, dest=target_lang
                            )
                            translated_text = translation.text
                        else:
                            translated_text = recognized_text
                        
                        # نمایش نتیجه
                        source_lang_name = self.supported_languages.get(detected_lang, detected_lang.upper())
                        target_lang_name = self.supported_languages.get(target_lang, target_lang.upper())
                        
                        result_message = f"""
🎵 **ترجمه فایل صوتی**

📥 متن تشخیص داده شده ({source_lang_name}):
{recognized_text}

📤 ترجمه ({target_lang_name}):
{translated_text}

⏱️ مدت فایل: {len(audio) // 1000} ثانیه
                        """
                        
                        await processing_msg.edit_text(result_message, parse_mode='Markdown')
                        
                        # ارسال فایل صوتی ترجمه
                        await self.send_audio_translation(update, translated_text, target_lang)
                
                # پاک کردن فایل‌های موقت
                os.unlink(temp_audio.name)
                os.unlink(temp_wav.name)
                        
        except Exception as e:
            logger.error(f"خطا در پردازش فایل صوتی: {e}")
            await processing_msg.edit_text("❌ خطا در پردازش فایل صوتی. لطفاً دوباره تلاش کنید.")

# تابع اصلی برای راه‌اندازی
def main():
    """تابع اصلی"""
    # توکن ربات را از متغیر محیطی بخوانید یا مستقیماً وارد کنید
    BOT_TOKEN = "8104124383:AAFrGB8uZmgkRx2EGGMd_H6ldASsLaRQclw"  # توکن ربات خود را اینجا قرار دهید
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ لطفاً توکن ربات را در متغیر BOT_TOKEN وارد کنید")
        print("برای دریافت توکن از @BotFather در تلگرام استفاده کنید")
        return
    
    # ایجاد و راه‌اندازی ربات
    bot = TranslatorBot(BOT_TOKEN)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 ربات متوقف شد")
    except Exception as e:
        print(f"❌ خطا در راه‌اندازی ربات: {e}")

if __name__ == "__main__":
    main() __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.translator = Translator()
        self.recognizer = sr.Recognizer()
        self.user_languages = {}  # ذخیره زبان انتخابی کاربران
        
        # لیست زبان‌های پشتیبانی شده
        self.supported_languages = {
            'fa': 'فارسی 🇮🇷',
            'en': 'English 🇺🇸',
            'ar': 'العربية 🇸🇦',
            'fr': 'Français 🇫🇷',
            'de': 'Deutsch 🇩🇪',
            'es': 'Español 🇪🇸',
            'it': 'Italiano 🇮🇹',
            'ru': 'Русский 🇷🇺',
            'zh': '中文 🇨🇳',
            'ja': '日本語 🇯🇵',
            'ko': '한국어 🇰🇷',
            'tr': 'Türkçe 🇹🇷',
            'pt': 'Português 🇵🇹',
            'nl': 'Nederlands 🇳🇱',
            'sv': 'Svenska 🇸🇪',
            'da': 'Dansk 🇩🇰',
            'no': 'Norsk 🇳🇴',
            'fi': 'Suomi 🇫🇮',
            'pl': 'Polski 🇵🇱',
            'uk': 'Українська 🇺🇦',
            'hi': 'हिन्दी 🇮🇳',
            'th': 'ไทย 🇹🇭',
            'vi': 'Tiếng Việt 🇻🇳'
        }

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پیام خوش‌آمدگویی"""
        welcome_message = """
🌍 سلام! به ربات ترجمه خوش اومدی

قابلیت‌های من:
🔤 ترجمه متن از هر زبانی به زبان دلخواه شما
🎤 ترجمه پیام صوتی به متن و صوت
🗣️ تبدیل متن به صوت

دستورات:
/start - شروع
/language - انتخاب زبان مقصد
/help - راهنما

برای شروع، ابتدا زبان مقصد خود را انتخاب کنید:
        """
        
        keyboard = self.create_language_keyboard()
        await update.message.reply_text(welcome_message, reply_markup=keyboard)

    def create_language_keyboard(self):
        """ایجاد کیبورد انتخاب زبان"""
        keyboard = []
        languages = list(self.supported_languages.items())
        
        # ایجاد دکمه‌ها به صورت 2 تا در هر ردیف
        for i in range(0, len(languages), 2):
            row = []
            for j in range(2):
                if i + j < len(languages):
                    code, name = languages[i + j]
                    row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """انتخاب زبان مقصد"""
        keyboard = self.create_language_keyboard()
        await update.message.reply_text("🌍 زبان مقصد خود را انتخاب کنید:", reply_markup=keyboard)

    async def language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت انتخاب زبان"""
        query = update.callback_query
        await query.answer()
        
        selected_lang = query.data.replace("lang_", "")
        user_id = query.from_user.id
        
        self.user_languages[user_id] = selected_lang
        language_name = self.supported_languages[selected_lang]
        
        await query.edit_message_text(
            f"✅ زبان مقصد شما به {language_name} تنظیم شد!\n\n"
            "حالا می‌تونید:\n"
            "📝 متن بفرستید تا ترجمه شه\n"
            "🎤 پیام صوتی بفرستید تا ترجمه و به صوت تبدیل شه"
        )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت پیام‌های متنی"""
        user_id = update.message.from_user.id
        text = update.message.text
        
        # چک کردن انتخاب زبان کاربر
        if user_id not in self.user_languages:
            keyboard = self.create_language_keyboard()
            await update.message.reply_text(
                "❌ ابتدا زبان مقصد خود را انتخاب کنید:",
                reply_markup=keyboard
            )
            return
        
        target_lang = self.user_languages[user_id]
        
        try:
            # نمایش پیام در حال پردازش
            processing_msg = await update.message.reply_text("🔄 در حال ترجمه...")
            
            # تشخیص زبان اصلی
            detected = self.translator.detect(text)
            source_lang = detected.lang
            
            # ترجمه متن
            if source_lang == target_lang:
                translated_text = text
                await processing_msg.edit_text(
                    f"ℹ️ متن شما قبلاً به زبان مقصد هست:\n\n{text}"
                )
                return
            
            translation = self.translator.translate(text, src=source_lang, dest=target_lang)
            translated_text = translation.text
            
            # ایجاد پیام نهایی
            source_lang_name = self.supported_languages.get(source_lang, source_lang.upper())
            target_lang_name = self.supported_languages.get(target_lang, target_lang.upper())
            
            result_message = f"""
🔤 **ترجمه متن**

📥 متن اصلی ({source_lang_name}):
{text}

📤 ترجمه ({target_lang_name}):
{translated_text}
            """
            
            await processing_msg.edit_text(result_message, parse_mode='Markdown')
            
            # ایجاد فایل صوتی
            await self.send_audio_translation(update, translated_text, target_lang)
            
        except Exception as e:
            logger.error(f"خطا در ترجمه متن: {e}")
            await processing_msg.edit_text("❌ خطا در ترجمه متن. لطفاً دوباره تلاش کنید.")

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت پیام‌های صوتی"""
        user_id = update.message.from_user.id
        
        # چک کردن انتخاب زبان کاربر
        if user_id not in self.user_languages:
            keyboard = self.create_language_keyboard()
            await update.message.reply_text(
                "❌ ابتدا زبان مقصد خود را انتخاب کنید:",
                reply_markup=keyboard
            )
            return
        
        target_lang = self.user_languages[user_id]
        
        try:
            processing_msg = await update.message.reply_text("🎤 در حال پردازش صوت...")
            
            # دانلود فایل صوتی
            voice_file = await update.message.voice.get_file()
            
            # ذخیره موقت فایل
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
                await voice_file.download_to_drive(temp_ogg.name)
                
                # تبدیل OGG به WAV
                audio = AudioSegment.from_ogg(temp_ogg.name)
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                    audio.export(temp_wav.name, format="wav")
                    
                    # تشخیص گفتار
                    await processing_msg.edit_text("🔄 در حال تشخیص گفتار...")
                    
                    with sr.AudioFile(temp_wav.name) as source:
                        audio_data = self.recognizer.record(source)
                        
                        # تلاش برای تشخیص با زبان‌های مختلف
                        recognized_text = None
                        for lang_code in ['fa-IR', 'en-US', 'ar-SA', 'tr-TR']:
                            try:
                                recognized_text = self.recognizer.recognize_google(
                                    audio_data, language=lang_code
                                )
                                source_lang = lang_code.split('-')[0]
                                break
                            except:
                                continue
                        
                        if not recognized_text:
                            await processing_msg.edit_text("❌ متأسفانه نتوانستم صوت را تشخیص دهم.")
                            return
                        
                        # ترجمه متن تشخیص داده شده
                        await processing_msg.edit_text("🔄 در حال ترجمه...")
                        
                        if source_lang != target_lang:
                            translation = self.translator.translate(
                                recognized_text, src=source_lang, dest=target_lang
                            )
                            translated_text = translation.text
                        else:
                            translated_text = recognized_text
                        
                        # ارسال نتیجه
                        source_lang_name = self.supported_languages.get(source_lang, source_lang.upper())
                        target_lang_name = self.supported_languages.get(target_lang, target_lang.upper())
                        
                        result_message = f"""
🎤 **ترجمه پیام صوتی**

📥 متن تشخیص داده شده ({source_lang_name}):
{recognized_text}

📤 ترجمه ({target_lang_name}):
{translated_text}
                        """
                        
                        await processing_msg.edit_text(result_message, parse_mode='Markdown')
                        
                        # ارسال فایل صوتی ترجمه
                        await self.send_audio_translation(update, translated_text, target_lang)
                
                # پاک کردن فایل‌های موقت
                os.unlink(temp_ogg.name)
                os.unlink(temp_wav.name)
                        
        except Exception as e:
            logger.error(f"خطا در پردازش صوت: {e}")
            await processing_msg.edit_text("❌ خطا در پردازش فایل صوتی.")

    async def send_audio_translation(self, update: Update, text: str, lang_code: str):
        """ایجاد و ارسال فایل صوتی ترجمه"""
        try:
            # ایجاد فایل صوتی
            tts = gTTS(text=text, lang=lang_code, slow=False)
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                tts.save(temp_audio.name)
                
                # ارسال فایل صوتی
                with open(temp_audio.name, 'rb') as audio_file:
                    await update.message.reply_voice(
                        voice=audio_file,
                        caption=f"🔊 نسخه صوتی ترجمه ({self.supported_languages[lang_code]})"
                    )
                
                # پاک کردن فایل موقت
                os.unlink(temp_audio.name)
                
        except Exception as e:
            logger.error(f"خطا در ایجاد فایل صوتی: {e}")
            await update.message.reply_text("❌ خطا در ایجاد فایل صوتی.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """راهنمای استفاده"""
        help_text = """
📚 **راهنمای استفاده از ربات ترجمه**

🔧 **دستورات:**
/start - شروع و نمایش خوش‌آمدگویی
/language - تغییر زبان مقصد
/help - نمایش این راهنما

📝 **نحوه استفاده:**
1️⃣ ابتدا زبان مقصد خود را انتخاب کنید
2️⃣ متن یا پیام صوتی خود را ارسال کنید
3️⃣ ربات ترجمه و فایل صوتی را ارسال می‌کند

🌍 **زبان‌های پشتیبانی شده:**
فارسی، انگلیسی، عربی، فرانسوی، آلمانی، اسپانیایی، ایتالیایی، روسی، چینی، ژاپنی، کره‌ای، ترکی، پرتغالی و بسیاری دیگر...

💡 **نکات:**
• کیفیت تشخیص صوت بستگی به وضوح و کیفیت ضبط دارد
• برای بهترین نتیجه، در محیط آرام صحبت کنید
• ربات قادر به تشخیص خودکار زبان اصلی متن است

⚡ **سرعت:** ترجمه و تولید صوت معمولاً کمتر از 10 ثانیه طول می‌کشد
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    def