import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TELEGRAM_BOT_TOKEN = "8698370133:AAH6yRXtsjTorCCx5iT0PYRjVuOj_Nng0x8"
TELEGRAM_CHAT_ID = "8201127054"

TICKER_URL = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
CANDLES_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=3"
ORDERBOOK_URL = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=40"

# 1. خادم الويب للحفاظ على نشاط الحاوية في Railway
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OKX Bot is running continuously!")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطأ في إرسال تليجرام: {e}")

def run_bot_logic():
    try:
        ticker = requests.get(TICKER_URL, timeout=10).json()['data'][0]
        candles = requests.get(CANDLES_URL, timeout=10).json()['data']
        books = requests.get(ORDERBOOK_URL, timeout=10).json()['data'][0]

        last_price = float(ticker['last'])
        high_24h = float(ticker['high24h'])
        low_24h = float(ticker['low24h'])

        # تجهيز التقرير
        report = f"📊 *(OKX) تقرير مراقبة البيتكوين*\n"
        report += f"-----------------------------------\n"
        report += f"💰 السعر الحالي: `{last_price}`\n"
        report += f"📈 قمة فريم اليوم: `{high_24h}`\n"
        report += f"📉 قاع فريم اليوم: `{low_24h}`\n"
        report += f"-----------------------------------\n"

        # حوائط السيولة
        bids = books.get('bids', [])
        asks = books.get('asks', [])
        
        if bids:
            report += f"🧱 حائط الشراء: `{bids[0][0]}` | الكمية: `{bids[0][1]}` BTC\n"
        if asks:
            report += f"🧱 حائط البيع: `{asks[0][0]}` | الكمية: `{asks[0][1]}` BTC\n"

        print(report)
        send_telegram_message(report)

    except Exception as e:
        print(f"خطأ أثناء جلب البيانات: {e}")

print("... بدء تشغيل بوت تليجرام لمراقبة السوق ...")

# 2. الحلقة اللانهائية لمنع السكريبت من الانتهاء والخروج!
while True:
    run_bot_logic()
    # ينفذ التقرير ويرسله كل 5 دقائق (300 ثانية)، يمكنك تغيير الرقم كما تحب
    time.sleep(300) 
