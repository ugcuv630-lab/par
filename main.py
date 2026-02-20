import asyncio
import logging
import requests
import sqlite3
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

API_TOKEN = '8580530107:AAHri716h46-e_8Jf_MXEcVtvsYKWB6Nj0w'
YOUR_ID = 1875258011
PAYMENT_LINK = "https://send.monobank.ua/jar/93SyfWeGhc"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (chat_id INTEGER PRIMARY KEY, keyword TEXT, status INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sent_ads 
                      (ad_id TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

def save_user(chat_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (chat_id, keyword, status) VALUES (?, ?, ?)', (chat_id, "", 0))
    conn.commit()
    conn.close()

def update_filter(chat_id, keyword):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET keyword = ? WHERE chat_id = ?', (keyword.lower(), chat_id))
    conn.commit()
    conn.close()

def activate_user_db(chat_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET status = 1 WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

def get_user_status(chat_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM users WHERE chat_id = ?', (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def is_ad_new(ad_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT ad_id FROM sent_ads WHERE ad_id = ?', (ad_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO sent_ads (ad_id) VALUES (?)', (ad_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_active_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, keyword FROM users WHERE status = 1')
    users = cursor.fetchall()
    conn.close()
    return users

async def parse_auto_ria():
    url = "https://auto.ria.com/uk/search/?indexName=auto,order_auto,newauto_search&categories.main.id=0&price.currency=1&sort[0].order=dates.created.desc"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            offers = soup.find_all('section', class_='ticket-item')
            results = []
            for offer in offers:
                ad_id = offer.get('data-good-id')
                if ad_id and is_ad_new(ad_id):
                    title = offer.find('a', class_='address').text.strip()
                    price = offer.find('span', class_='bold').text.strip()
                    link = offer.find('a', class_='address')['href']
                    results.append({"title": title, "price": price, "link": link})
            return results
    except:
        pass
    return []

async def monitoring_loop():
    print("🚀 Monitoring started")
    while True:
        new_ads = await parse_auto_ria()
        if new_ads:
            active_users = get_active_users()
            for ad in new_ads:
                for chat_id, keyword in active_users:
                    if not keyword or keyword in ad['title'].lower():
                        text = f"🔥 НОВЕ ОГОЛОШЕННЯ! 🔥\n\n🚗 {ad['title']}\n💰 Ціна: {ad['price']}\n🔗 {ad['link']}"
                        try:
                            await bot.send_message(chat_id, text)
                        except:
                            pass
        await asyncio.sleep(60)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.chat.id)
    status = get_user_status(message.chat.id)
    if message.chat.id != YOUR_ID:
        await bot.send_message(YOUR_ID, f"👤 Новий клієнт!\nID: `{message.chat.id}`\nІм'я: {message.from_user.full_name}\nUsername: @{message.from_user.username}")
    
    status_text = "✅ Активна" if status == 1 else "⏳ Очікує активації"
    text = (
        f"🏎 **Вітаємо в Auto Monitor UA!**\n\n"
        f"Ваш ID: `{message.chat.id}`\n"
        f"Статус підписки: {status_text}\n\n"
        f"💳 **Для підключення (150 грн/міс):**\n"
        f"1. Поповніть банку: {PAYMENT_LINK}\n"
        f"2. У коментарі вкажіть ваш ID.\n"
        f"3. Доступ відкриється після перевірки.\n\n"
        f"🆘 Підтримка: @Faree_1"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("set"))
async def cmd_set(message: types.Message):
    if get_user_status(message.chat.id) == 0:
        await message.answer("❌ Встановлення фільтрів доступне лише після оплати.")
        return
    keyword = message.text.replace("/set", "").strip().lower()
    update_filter(message.chat.id, keyword)
    await message.answer(f"🔎 Фільтр оновлено: **{keyword if keyword else 'Всі авто'}**", parse_mode="Markdown")

@dp.message(Command("activate"))
async def cmd_activate(message: types.Message):
    if message.from_user.id == YOUR_ID:
        try:
            target_id = int(message.text.replace("/activate", "").strip())
            activate_user_db(target_id)
            await message.answer(f"✅ Доступ для {target_id} активовано!")
            await bot.send_message(target_id, "🌟 **Ваш доступ активовано.**\nФільтр: `/set марка` (наприклад `/set toyota`) або залиште порожнім.")
        except:
            await message.answer("Помилка. Вводь: /activate ID")

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    await message.answer("📡 Auto Monitor UA онлайн!")

async def main():
    print("📡 Bot starting...")
    init_db()
    asyncio.create_task(monitoring_loop())
    print("🤖 Polling started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        print("停止")