import subprocess
import sys

def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"جاري تثبيت المكتبة ({package})...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_and_import("requests")

import time
import requests
import datetime

# --- بيانات بوت تيليجرام الخاص بك ---
TELEGRAM_BOT_TOKEN = "8698370133:AAH6yRXtsjTorCCx5iT0PYRjVUoJ_NngOx8"
TELEGRAM_CHAT_ID = "8201127054"
# -----------------------------------

# روابط OKX
TICKER_URL = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
CANDLES_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=2" # فريم اليوم
ORDERBOOK_URL = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=50"
TRADES_URL = "https://www.okx.com/api/v5/market/trades?instId=BTC-USDT&limit=50"

WHALE_THRESHOLD_BTC = 1.0     # حجم صفقة الحوت
WALL_VOLUME_THRESHOLD = 50.0  # حجم السيولة المعلقة للحائط (بالبتكوين)

last_alerted_bid_wall = 0
last_alerted_ask_wall = 0
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        print("رد تيليجرام:", response.text) # <-- أضف هذا السطر لنرى الرد
        if response.status_code != 200:
            print("فشل إرسال رسالة تيليجرام")
    except Exception as e:
        print(f"خطأ في الاتصال بتيليجرام: {e}")

def monitor_market():
    global last_alerted_bid_wall, last_alerted_ask_wall
    try:
        # 1. جلب السعر الحالي
        ticker_res = requests.get(TICKER_URL).json()
        if ticker_res.get("code") == "0" and ticker_res.get("data"):
            current_price = float(ticker_res["data"][0]["last"])
        else:
            return

        # 2. جلب بيانات فريم اليوم (آخر قمة وآخر قاع يومي)
        candles_res = requests.get(CANDLES_URL).json()
        daily_high = "غير محدد"
        daily_low = "غير محدد"
        if candles_res.get("code") == "0" and candles_res.get("data"):
            # شمعة اليوم السابقة أو الحالية [timestamp, open, high, low, close, ...]
            day_data = candles_res["data"][0] 
            daily_high = day_data[2]
            daily_low = day_data[3]

        # 3. فحص دفتر الأوامر والأموال المعلقة (الحوائط)
        book_res = requests.get(ORDERBOOK_URL).json()
        bid_wall_text = "لا يوجد حائط شراء ضخم حالياً"
        ask_wall_text = "لا يوجد حائط بيع ضخم حالياً"
        
        if book_res.get("code") == "0" and book_res.get("data"):
            bids = book_res["data"][0]["bids"]
            asks = book_res["data"][0]["asks"]
            
            strongest_bid = max(bids, key=lambda x: float(x[1])) if bids else [0, 0]
            strongest_ask = max(asks, key=lambda x: float(x[1])) if asks else [0, 0]
            
            bid_price, bid_vol = float(strongest_bid[0]), float(strongest_bid[1])
            ask_price, ask_vol = float(strongest_ask[0]), float(strongest_ask[1])

            bid_wall_text = f"السعر: {bid_price} | الكمية المعلقة: {bid_vol} BTC"
            ask_wall_text = f"السعر: {ask_price} | الكمية المعلقة: {ask_vol} BTC"

            # تنبيهات فورية للحوائط الكبيرة أو كسرها
            if bid_vol >= WALL_VOLUME_THRESHOLD and bid_price != last_alerted_bid_wall:
                msg = f"🟢 *حائط شراء ضخم (دعم معلق)*\nالسعر: {bid_price}\nالكمية: {bid_vol} BTC"
                send_telegram_message(msg)
                last_alerted_bid_wall = bid_price

            if ask_vol >= WALL_VOLUME_THRESHOLD and ask_price != last_alerted_ask_wall:
                msg = f"🔴 *حائط بيع ضخم (مقاومة معلقة)*\nالسعر: {ask_price}\nالكمية: {ask_vol} BTC"
                send_telegram_message(msg)
                last_alerted_ask_wall = ask_price

        # 4. رصد صفقات الحيتان (السيولة الكبيرة اللحظية)
        trades_res = requests.get(TRADES_URL).json()
        if trades_res.get("code") == "0" and trades_res.get("data"):
            for trade in trades_res["data"]:
                price = float(trade["px"])
                amount = float(trade["sz"])
                side = trade["side"].upper()
                
                if amount >= WHALE_THRESHOLD_BTC:
                    whale_msg = f"🐋 *رصد صفقة حوت كبيرة!*\n• الاتجاه: {side}\n• الكمية: {amount} BTC\n• السعر: {price}"
                    send_telegram_message(whale_msg)

        # تجميع تقرير منظم بالبيانات المطلوبة وعرضه في الترمنال
        report = (
            f"📊 *تقرير مراقبة البيتكوين (OKX)*\n"
            f"----------------------------------\n"
            f"💰 السعر الحالي: `{current_price}`\n"
            f"📈 قمة فريم اليوم: `{daily_high}`\n"
            f"📉 قاع فريم اليوم: `{daily_low}`\n"
            f"----------------------------------\n"
            f"🧱 حائط الشراء (السيولة المعلقة):\n{bid_wall_text}\n"
            f"🧱 حائط البيع (السيولة المعلقة):\n{ask_wall_text}\n"
            f"----------------------------------\n"
            f"🕒 الوقت: {datetime.datetime.now().strftime('%H:%M:%S')}"
        )
        print(report)

    except Exception as e:
        print(f"خطأ أثناء جلب البيانات: {e}")

if __name__ == "__main__":
    print("بدء تشغيل بوت تيليجرام لمراقبة السوق...")
    while True:
        monitor_market()
        time.sleep(30) # التحديث كل 30 ثانية
    