import os
import time
import requests
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

TELEGRAM_BOT_TOKEN = "8698370133:AAH6yRXtsjTorCCx5iT0PYRjVuOj_Nng0x8"
TELEGRAM_CHAT_ID = "8201127054"

# رابط API لمنصة OKX
TICKER_URL = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
CANDLES_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=3"
ORDERBOOK_URL = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=100"
TRADES_URL = "https://www.okx.com/api/v5/market/trades?instId=BTC-USDT&limit=100"

# متغيرة لتتبع حالات التنبيهات المرة الواحدة
last_report_date = None
last_high = 0.0
last_low = 0.0
tracked_wall_bid = None
tracked_wall_ask = None

# الحد الأدنى للجم ليعتبر "حائط سيولة" أو "صفقة ضخمة" (يمكنك تعديل القيم)
WALL_THRESHOLD_BTC = 5.0     # حائط أكبر من 5 بيتكوين
LARGE_TRADE_BTC = 2.0        # صفقة منفذة أكبر من 2 بيتكوين

# 1. خادم الويب لإبقاء الحاوية نشطة في Railway
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OKX Smart Alert Bot is Active!")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        res = requests.post(url, json=payload, timeout=10)
        print(f"تنبيه تليجرام: {res.status_code}")
    except Exception as e:
        print(f"خطأ إرسال: {e}")

# --------------------------------------------------
# وظائف التنبيه الذكية
# --------------------------------------------------

def check_daily_report():
    """ترسل تقرير اليوم مرة واحدة فقط عند بداية كل يوم جديد"""
    global last_report_date, last_high, last_low
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    if last_report_date != today_str:
        try:
            ticker = requests.get(TICKER_URL, timeout=10).json()['data'][0]
            candles = requests.get(CANDLES_URL, timeout=10).json()['data']
            
            last_price = float(ticker['last'])
            open_today = float(candles[0][1]) if len(candles) >= 1 else last_price
            close_yesterday = float(candles[1][4]) if len(candles) >= 2 else last_price
            high_today = float(ticker['high24h'])
            low_today = float(ticker['low24h'])
            
            last_high = high_today
            last_low = low_today
            
            msg = f"📌 [التقرير اليومي - {today_str}]\n"
            msg += f"-----------------------------------\n"
            msg += f"🌅 سعر بداية اليوم (الافتتاح): {open_today}\n"
            msg += f"📊 سعر إغلاق شمعة الأمس: {close_yesterday}\n"
            msg += f"📈 قمة اليوم الحالية: {high_today}\n"
            msg += f"📉 قاع اليوم الحالي: {low_today}\n"
            msg += f"💰 السعر الحالي: {last_price}"
            
            send_telegram(msg)
            last_report_date = today_str
        except Exception as e:
            print(f"خطأ في التقرير اليومي: {e}")

def check_high_low_breakout():
    """تنبيه عند كسر قمة أو قاع اليوم مرة واحدة"""
    global last_high, last_low
    try:
        ticker = requests.get(TICKER_URL, timeout=10).json()['data'][0]
        current_high = float(ticker['high24h'])
        current_low = float(ticker['low24h'])
        current_price = float(ticker['last'])
        
        if last_high > 0 and current_high > last_high:
            send_telegram(f"🔥 *تنبيه قمة جديدة لليوم!*\nالسعر اختلع القمة السابقة ووصل إلى: {current_high}")
            last_high = current_high
            
        if last_low > 0 and current_low < last_low:
            send_telegram(f"⚠️ *تنبيه قاع جديد لليوم!*\nالسعر هبط وكسر القاع السابق إلى: {current_low}")
            last_low = current_low
    except Exception as e:
        print(f"خطأ في فحص القمم والقيعان: {e}")

def check_liquidity_walls():
    """رصد الحوائط الجديدة وتنبيه كسر/حذف الحوائط"""
    global tracked_wall_bid, tracked_wall_ask
    try:
        books = requests.get(ORDERBOOK_URL, timeout=10).json()['data'][0]
        bids = books.get('bids', [])
        asks = books.get('asks', [])
        
        # البحث عن حائط شراء جديد
        current_bid_wall = None
        for price, size, _ in bids:
            if float(size) >= WALL_THRESHOLD_BTC:
                current_bid_wall = (float(price), float(size))
                break
                
        # البحث عن حائط بيع جديد
        current_ask_wall = None
        for price, size, _ in asks:
            if float(size) >= WALL_THRESHOLD_BTC:
                current_ask_wall = (float(price), float(size))
                break

        # تنبيه حائط شراء
        if current_bid_wall and current_bid_wall != tracked_wall_bid:
            send_telegram(f"🧱 *تنبيه حائط شراء جديد!*\nالسعر: {current_bid_wall[0]} | الكمية: {current_bid_wall[1]} BTC")
            tracked_wall_bid = current_bid_wall
        elif not current_bid_wall and tracked_wall_bid:
            send_telegram(f"💥 *تم كسر/تنفيذ حائط الشراء* عند السعر: {tracked_wall_bid[0]}")
            tracked_wall_bid = None

        # تنبيه حائط بيع
        if current_ask_wall and current_ask_wall != tracked_wall_ask:
            send_telegram(f"🧱 *تنبيه حائط بيع جديد!*\nالسعر: {current_ask_wall[0]} | الكمية: {current_ask_wall[1]} BTC")
            tracked_wall_ask = current_ask_wall
        elif not current_ask_wall and tracked_wall_ask:
            send_telegram(f"💥 *تم كسر/تنفيذ حائط البيع* عند السعر: {tracked_wall_ask[0]}")
            tracked_wall_ask = None
            
    except Exception as e:
        print(f"خطأ في رصد الحوائط: {e}")

def check_large_trades_and_flow():
    """رصد الصفقات الكبيرة وحساب السيولة الداخلة والخارجة"""
    try:
        trades = requests.get(TRADES_URL, timeout=10).json()['data']
        inflow = 0.0   # سيولة داخلة (شراء)
        outflow = 0.0  # سيولة خارجة (بيع)
        
        for trade in trades:
            size = float(trade['sz'])
            side = trade['side']
            price = float(trade['px'])
            
            if side == 'buy':
                inflow += size * price
                if size >= LARGE_TRADE_BTC:
                    send_telegram(f"🐳 *صفقة شراء ضخمة (ماركت)!*\nالحجم: {size} BTC | السعر: {price}")
            elif side == 'sell':
                outflow += size * price
                if size >= LARGE_TRADE_BTC:
                    send_telegram(f"🚨 *صفقة بيع ضخمة (ماركت)!*\nالحجم: {size} BTC | السعر: {price}")
                    
    except Exception as e:
        print(f"خطأ في السيولة والصفقات: {e}")

# --------------------------------------------------
# الحلقة الرئيسية للمراقبة
# --------------------------------------------------
print("... بدء تشغيل نظام المراقبة والتنبيهات الذكية ...")

while True:
    check_daily_report()          # يفحص ويرسل التقرير اليومي مرة واحدة
    check_high_low_breakout()     # يفحص كسر القمم/القيعان
    check_liquidity_walls()       # يفحص الحوائط وتغيراتها
    check_large_trades_and_flow() # يفحص الصفقات الضخمة والسيولة
    
    time.sleep(15)  # يفحص السوق كل 15 ثانية صامتاً ولا يرسل إلا عند وجود تنبيه جديد
