import time
import requests
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

TELEGRAM_BOT_TOKEN = "8698370133:AAH6yRXtsjTorCCx5iT0PYRjVuOj_Nng0x8"
TELEGRAM_CHAT_ID = "8201127054"

TICKER_URL = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
CANDLES_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=3"
ORDERBOOK_URL = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=40"

last_update_offset = 0
last_alerted_price = 0  # لتجنب تكرار نفس التنبيه المزعج

# 1. خادم الويب لإرضاء Railway ومنع توقف الحاوية
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Monitoring Bot is active!")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"خطأ في الإرسال: {e}")

def get_report():
    try:
        ticker = requests.get(TICKER_URL, timeout=10).json()['data'][0]
        candles = requests.get(CANDLES_URL, timeout=10).json()['data']
        last = float(ticker['last'])
        open_p = float(candles[0][1]) if len(candles) >= 2 else last
        prev_close = float(candles[1][4]) if len(candles) >= 2 else last
        
        return f"📊 *تقرير السوق المباشر*\n💰 السعر الحالي: `{last}`\n🌅 فتح اليوم: `{open_p}`\n📊 إغلاق الأمس: `{prev_close}`\n📈 أعلى: `{ticker['high24h']}`\n📉 أدنى: `{ticker['low24h']}`"
    except Exception as e:
        return f"⚠️ تعذر جلب البيانات حالياً: {e}"

# 2. وظيفة المراقبة التلقائية (تتحدث وتُنبه تلقائياً)
def background_monitoring():
    global last_alerted_price
    while True:
        try:
            ticker = requests.get(TICKER_URL, timeout=10).json()['data'][0]
            current_price = float(ticker['last'])
            
            # مثال للتنبيه التلقائي: إذا تحرك السعر بنسبة ملحوظة أو كلما أردت
            # يمكنك تخصيص الشرط هنا (مثلاً رصد الحوائط الضخمة أو تغير السعر)
            print(f"تم فحص السوق بنجاح. السعر الحالي: {current_price}")
            
        except Exception as e:
            print(f"خطأ في فحص السوق الخلفي: {e}")
            
        time.sleep(60) # يفحص السوق كل 60 ثانية ويرسل تنبيه إذا لزم الأمر

threading.Thread(target=background_monitoring, daemon=True).start()

print("بوت المراقبة والتنبيه يعمل الآن بثبات تام...")

# 3. حلقة الاستقبال للتفاعل مع رسائلك في تليجرام
while True:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_update_offset}&timeout=5"
        res = requests.get(url, timeout=7).json()
        
        if res.get("ok"):
            for item in res.get("result", []):
                last_update_offset = item["update_id"] + 1
                msg = item.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = msg.get("chat", {}).get("id")
                
                if str(chat_id) == str(TELEGRAM_CHAT_ID):
                    if "بيانات" in text or "سعر" in text or "تقرير" in text:
                        report = get_report()
                        send_message(report)
    except Exception as e:
        print(f"خطأ في الاستماع: {e}")
    
    time.sleep(2)
