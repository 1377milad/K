import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import random
import time
from threading import Thread
import sqlite3
import string
import qrcode
from io import BytesIO

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# اتصال به دیتابیس
conn = sqlite3.connect('miner_bot.db', check_same_thread=False)
cursor = conn.cursor()

# ایجاد جداول دیتابیس
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    referral_id TEXT,
    referred_by TEXT,
    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS wallets (
    user_id INTEGER,
    btc TEXT,
    eth TEXT,
    doge TEXT,
    tron TEXT,
    sol TEXT,
    ltc TEXT,
    xrp TEXT,
    PRIMARY KEY (user_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS mining (
    user_id INTEGER,
    btc_balance REAL DEFAULT 0,
    eth_balance REAL DEFAULT 0,
    doge_balance REAL DEFAULT 0,
    tron_balance REAL DEFAULT 0,
    sol_balance REAL DEFAULT 0,
    ltc_balance REAL DEFAULT 0,
    xrp_balance REAL DEFAULT 0,
    last_mining_time TIMESTAMP,
    mining_speed INTEGER DEFAULT 1,
    PRIMARY KEY (user_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS lottery (
    user_id INTEGER,
    lottery_300k INTEGER DEFAULT 0,
    lottery_100k INTEGER DEFAULT 0,
    lottery_50k INTEGER DEFAULT 0,
    PRIMARY KEY (user_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS tokens (
    user_id INTEGER,
    token_m_balance REAL DEFAULT 0,
    token_n_balance REAL DEFAULT 0,
    last_click_time TIMESTAMP,
    PRIMARY KEY (user_id)
)
''')

conn.commit()

# توکن ربات تلگرام
TOKEN = "8087872727:AAG6_Fy_SL6z-s_cJkojfihiBUVd-UfvSRM"

# آدرس‌های کیف پول پیشفرض
DEFAULT_WALLETS = {
    'btc': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
    'eth': '0x71C7656EC7ab88b098defB751B7401B5f6d8976F',
    'doge': 'DLXE4y8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy',
    'tron': 'TNPZxCXeQy8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy',
    'sol': 'SoLXy8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy8',
    'ltc': 'LZ4Xy8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy8X4Xy',
    'xrp': 'rPdvC6CCqN7pS1X4Xy8X4Xy8X4Xy8X4Xy8X'
}

# توابع کمکی
def generate_referral_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def create_user(user_id, username, first_name, last_name, referred_by=None):
    referral_id = generate_referral_id()
    cursor.execute('''
    INSERT INTO users (user_id, username, first_name, last_name, referral_id, referred_by)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, referral_id, referred_by))
    
    # ایجاد رکوردهای مرتبط
    cursor.execute('INSERT INTO wallets (user_id) VALUES (?)', (user_id,))
    cursor.execute('INSERT INTO mining (user_id) VALUES (?)', (user_id,))
    cursor.execute('INSERT INTO lottery (user_id) VALUES (?)', (user_id,))
    cursor.execute('INSERT INTO tokens (user_id) VALUES (?)', (user_id,))
    
    conn.commit()

def update_wallets(user_id, wallet_type, address):
    cursor.execute(f'UPDATE wallets SET {wallet_type} = ? WHERE user_id = ?', (address, user_id))
    conn.commit()

def get_wallets(user_id):
    cursor.execute('SELECT * FROM wallets WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def get_mining_balance(user_id):
    cursor.execute('SELECT * FROM mining WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def update_mining_balance(user_id, coin_type, amount):
    cursor.execute(f'UPDATE mining SET {coin_type}_balance = {coin_type}_balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()

def get_lottery_tickets(user_id):
    cursor.execute('SELECT * FROM lottery WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def add_lottery_ticket(user_id, lottery_type):
    cursor.execute(f'UPDATE lottery SET {lottery_type} = {lottery_type} + 1 WHERE user_id = ?', (user_id,))
    conn.commit()

def get_token_balance(user_id):
    cursor.execute('SELECT * FROM tokens WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def update_token_balance(user_id, token_type, amount):
    cursor.execute(f'UPDATE tokens SET {token_type}_balance = {token_type}_balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()

# دستورات ربات
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    referred_by = context.args[0] if context.args else None
    
    if not get_user(user_id):
        create_user(user_id, user.username, user.first_name, user.last_name, referred_by)
        
        # تنظیم آدرس‌های پیشفرض
        wallets = get_wallets(user_id)
        if not any(wallets[1:]):
            for coin, address in DEFAULT_WALLETS.items():
                update_wallets(user_id, coin, address)
    
    # ایجاد صفحه اصلی
    keyboard = [
        [InlineKeyboardButton("💰 ماینر ارزها", callback_data='miner')],
        [InlineKeyboardButton("🎫 قرعه کشی", callback_data='lottery')],
        [InlineKeyboardButton("🪙 توکن M و N", callback_data='tokens')],
        [InlineKeyboardButton("👥 لینک دعوت", callback_data='referral')],
        [InlineKeyboardButton("🆘 پشتیبانی", callback_data='support')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"👋 سلام {user.first_name}!\n\n"
        "به ربات ماینر چند ارزی خوش آمدید!\n\n"
        "🛠️ این ربات امکان ماینینگ مجازی 7 ارز دیجیتال مختلف را فراهم می‌کند.\n"
        "🎁 همچنین می‌توانید در قرعه کشی‌های مختلف شرکت کنید و توکن‌های M و N دریافت نمایید.",
        reply_markup=reply_markup
    )

# صفحه اصلی
def main_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💰 ماینر ارزها", callback_data='miner')],
        [InlineKeyboardButton("🎫 قرعه کشی", callback_data='lottery')],
        [InlineKeyboardButton("🪙 توکن M و N", callback_data='tokens')],
        [InlineKeyboardButton("👥 لینک دعوت", callback_data='referral')],
        [InlineKeyboardButton("🆘 پشتیبانی", callback_data='support')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "منوی اصلی:\n\n"
        "💰 ماینر ارزها - استخراج مجازی 7 ارز دیجیتال\n"
        "🎫 قرعه کشی - شرکت در قرعه کشی‌های مختلف\n"
        "🪙 توکن M و N - دریافت توکن‌های اختصاصی\n"
        "👥 لینک دعوت - دعوت دوستان و دریافت پاداش\n"
        "🆘 پشتیبانی - راهنمایی و پشتیبانی",
        reply_markup=reply_markup
    )

# صفحه ماینر
def miner_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    mining_data = get_mining_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔄 به‌روزرسانی", callback_data='update_miner')],
        [InlineKeyboardButton("🎫 قرعه کشی", callback_data='lottery')],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # شبیه‌سازی ماینینگ
    mining_text = "⛏️ ماینر در حال کار...\n\n"
    mining_text += f"🔹 بیت‌کوین: {mining_data[1]:.12f} BTC\n"
    mining_text += f"🔹 اتریوم: {mining_data[2]:.12f} ETH\n"
    mining_text += f"🔹 دوج‌کوین: {mining_data[3]:.12f} DOGE\n"
    mining_text += f"🔹 ترون: {mining_data[4]:.12f} TRX\n"
    mining_text += f"🔹 سولانا: {mining_data[5]:.12f} SOL\n"
    mining_text += f"🔹 لایت‌کوین: {mining_data[6]:.12f} LTC\n"
    mining_text += f"🔹 ریپل: {mining_data[7]:.12f} XRP\n\n"
    mining_text += "🔄 اعداد به صورت تصادفی و با سرعت بالا در حال افزایش هستند!"
    
    query.edit_message_text(mining_text, reply_markup=reply_markup)
    
    # شبیه‌سازی افزایش اعداد
    def update_mining_numbers():
        for _ in range(10):
            time.sleep(0.5)
            for coin_idx in range(1, 8):
                increment = random.uniform(0.00000001, 0.000001) * mining_data[9]
                cursor.execute(f'''
                UPDATE mining 
                SET {"btc_eth_doge_tron_sol_ltc_xrp".split('_')[coin_idx-1]}_balance = 
                {"btc_eth_doge_tron_sol_ltc_xrp".split('_')[coin_idx-1]}_balance + ?
                WHERE user_id = ?
                ''', (increment, user_id))
            conn.commit()
    
    Thread(target=update_mining_numbers).start()

# صفحه قرعه کشی
def lottery_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    lottery_data = get_lottery_tickets(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("🎟️ 300,000$", callback_data='lottery_300k'),
            InlineKeyboardButton("🎟️ 100,000$", callback_data='lottery_100k'),
            InlineKeyboardButton("🎟️ 50,000$", callback_data='lottery_50k')
        ],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    lottery_text = "🎫 قرعه کشی‌های فعال:\n\n"
    lottery_text += f"🎟️ قرعه کشی 300,000$: {lottery_data[1]} بلیط\n"
    lottery_text += f"🎟️ قرعه کشی 100,000$: {lottery_data[2]} بلیط\n"
    lottery_text += f"🎟️ قرعه کشی 50,000$: {lottery_data[3]} بلیط\n\n"
    lottery_text += "برای شرکت در هر قرعه کشی روی دکمه مربوطه کلیک کنید."
    
    query.edit_message_text(lottery_text, reply_markup=reply_markup)

# شرکت در قرعه کشی
def join_lottery(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    lottery_type = query.data
    
    add_lottery_ticket(user_id, lottery_type)
    
    # ارسال آدرس‌های کیف پول
    wallets = get_wallets(user_id)
    wallet_text = "🔐 آدرس‌های کیف پول شما:\n\n"
    wallet_text += f"💰 بیت‌کوین: {wallets[1]}\n"
    wallet_text += f"💎 اتریوم: {wallets[2]}\n"
    wallet_text += f"🐕 دوج‌کوین: {wallets[3]}\n"
    wallet_text += f"⚡ ترون: {wallets[4]}\n"
    wallet_text += f"🌞 سولانا: {wallets[5]}\n"
    wallet_text += f"🔶 لایت‌کوین: {wallets[6]}\n"
    wallet_text += f"✖️ ریپل: {wallets[7]}\n\n"
    wallet_text += "شما با موفقیت در قرعه کشی ثبت نام کردید!"
    
    query.answer("شما با موفقیت در قرعه کشی ثبت نام کردید! آدرس‌های کیف پول شما در چت ارسال شد.")
    context.bot.send_message(chat_id=user_id, text=wallet_text)
    
    # بازگشت به صفحه قرعه کشی
    lottery_menu(update, context)

# صفحه توکن‌ها
def tokens_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    token_data = get_token_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🪙 دریافت توکن M", callback_data='get_token_m')],
        [InlineKeyboardButton("🪙 دریافت توکن N", callback_data='get_token_n')],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    token_text = "🪙 توکن‌های شما:\n\n"
    token_text += f"🔸 توکن M: {token_data[1]:.2f}\n"
    token_text += f"🔹 توکن N: {token_data[2]:.2f}\n\n"
    token_text += "برای دریافت توکن‌های بیشتر روی دکمه‌های زیر کلیک کنید."
    
    query.edit_message_text(token_text, reply_markup=reply_markup)

# دریافت توکن
def get_token(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    token_type = query.data.split('_')[-1]  # 'm' یا 'n'
    
    amount = random.uniform(0.1, 5.0)
    update_token_balance(user_id, f'token_{token_type}', amount)
    
    query.answer(f"شما {amount:.2f} توکن {token_type.upper()} دریافت کردید!")
    tokens_menu(update, context)

# صفحه دعوت دوستان
def referral_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    user_data = get_user(user_id)
    
    # تعداد دعوت‌های موفق
    cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (user_id,))
    referrals_count = cursor.fetchone()[0]
    
    referral_link = f"https://t.me/{context.bot.username}?start={user_data[4]}"
    
    keyboard = [
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    referral_text = "👥 سیستم دعوت دوستان\n\n"
    referral_text += f"🔗 لینک دعوت شما:\n{referral_link}\n\n"
    referral_text += f"📊 تعداد دعوت‌های موفق: {referrals_count}\n\n"
    referral_text += "با دعوت هر دوست، هم شما و هم دوستتان پاداش دریافت می‌کنید!"
    
    query.edit_message_text(referral_text, reply_markup=reply_markup)

# صفحه پشتیبانی
def support_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    support_text = "🆘 پشتیبانی\n\n"
    support_text += "در صورت بروز هرگونه مشکل یا سوال می‌توانید با آیدی زیر در ارتباط باشید:\n"
    support_text += "@SupportUsername\n\n"
    support_text += "همچنین می‌توانید از طریق دکمه‌های زیر کیف پول‌های مورد نظر خود را تغییر دهید."
    
    query.edit_message_text(support_text, reply_markup=reply_markup)

# تنظیمات کیف پول
def wallet_settings(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("BTC", callback_data='set_wallet_btc'),
            InlineKeyboardButton("ETH", callback_data='set_wallet_eth'),
            InlineKeyboardButton("DOGE", callback_data='set_wallet_doge')
        ],
        [
            InlineKeyboardButton("TRX", callback_data='set_wallet_tron'),
            InlineKeyboardButton("SOL", callback_data='set_wallet_sol'),
            InlineKeyboardButton("LTC", callback_data='set_wallet_ltc')
        ],
        [
            InlineKeyboardButton("XRP", callback_data='set_wallet_xrp'),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data='main_menu')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "🔐 تنظیمات کیف پول\n\n"
        "لطفا ارزی را که می‌خواهید آدرس کیف پول آن را تغییر دهید انتخاب کنید:",
        reply_markup=reply_markup
    )

# تنظیم آدرس کیف پول
def set_wallet_address(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    coin_type = query.data.split('_')[-1]
    
    query.answer()
    query.edit_message_text(
        f"لطفا آدرس کیف پول {coin_type.upper()} خود را ارسال کنید:"
    )
    
    # ذخیره کوین انتخابی در context برای استفاده در مرحله بعد
    context.user_data['setting_wallet_for'] = coin_type
    return 'WAITING_FOR_WALLET_ADDRESS'

# دریافت آدرس کیف پول از کاربر
def receive_wallet_address(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    wallet_address = update.message.text
    coin_type = context.user_data['setting_wallet_for']
    
    update_wallets(user_id, coin_type, wallet_address)
    
    update.message.reply_text(
        f"آدرس کیف پول {coin_type.upper()} شما با موفقیت به روز شد!"
    )
    
    return -1  # خاتمه حالت گفتگو

# تابع اصلی
def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # دستورات
    dispatcher.add_handler(CommandHandler('start', start))
    
    # callback queries
    dispatcher.add_handler(CallbackQueryHandler(main_menu, pattern='^main_menu$'))
    dispatcher.add_handler(CallbackQueryHandler(miner_menu, pattern='^miner$'))
    dispatcher.add_handler(CallbackQueryHandler(miner_menu, pattern='^update_miner$'))
    dispatcher.add_handler(CallbackQueryHandler(lottery_menu, pattern='^lottery$'))
    dispatcher.add_handler(CallbackQueryHandler(join_lottery, pattern='^lottery_'))
    dispatcher.add_handler(CallbackQueryHandler(tokens_menu, pattern='^tokens$'))
    dispatcher.add_handler(CallbackQueryHandler(get_token, pattern='^get_token_'))
    dispatcher.add_handler(CallbackQueryHandler(referral_menu, pattern='^referral$'))
    dispatcher.add_handler(CallbackQueryHandler(support_menu, pattern='^support$'))
    dispatcher.add_handler(CallbackQueryHandler(wallet_settings, pattern='^wallet_settings$'))
    dispatcher.add_handler(CallbackQueryHandler(set_wallet_address, pattern='^set_wallet_'))
    
    # دریافت آدرس کیف پول
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command,
        receive_wallet_address,
        pass_user_data=True
    ))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()