import os
import time
import requests
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# البيانات الخاصة بك
TELEGRAM_BOT_TOKEN = "8614560573:AAEIkl90GlHJ3zUXv1a5c8du70KEH3v49Ic"
TELEGRAM_CHAT_ID = "8201127054"

# روابط OKX API
TICKER_URL = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
CANDLES_DAILY_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=3"
CANDLES_1H_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=24"
ORDERBOOK_URL = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=40"
TRADES_URL = "https://www.okx.com/api/v5/market/trades?instId=BTC-USDT&limit=100"

# متغيرات التتبع
last_report_date = None
last_1h_high = 0.0
last_1h_low = 0.0
tracked_wall_bid = None
tracked_wall_ask = None

# شروط التنبيهات
WALL_THRESHOLD_BTC = 5.0     # حائط أكبر من 5 بيتكوين
LARGE_TRADE_BTC = 2.0        # صفقة أكبر من 2 بيتكوين

# 1. خادم الويب للحفاظ على نشاط الحاوية في Railway
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OKX Smart Bot (1H Frame) is Alive & Running!")
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
        print(f"استجابة تليجرام: {res.status_code}")
    except Exception as e:
        print(f"خطأ في الاتصال بتليجرام: {e}")

def get_1h_high_low():
    """جلب أعلى قمة وأدنى قاع من آخر 24 شمعة على فريم الساعة"""
    try:
        candles_1h = requests.get(CANDLES_1H_URL, timeout=10).json().get('data', [])
        if not candles_1h:
            return 0.0, 0.0
        
        # candle format: [ts, open, high, low, close, ...]
        highs = [float(c[2]) for c in candles_1h]
        lows = [float(c[3]) for c in candles_1h]
        
        return max(highs), min(lows)
    except Exception as e:
        print(f"خطأ في جلب بيانات فريم الساعة: {e}")
        return 0.0, 0.0

def check_daily_report():
    global last_report_date, last_1h_high, last_1h_low
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if last_report_date != today_str:
        try:
            ticker = requests.get(TICKER_URL, timeout=10).json()['data'][0]
            daily_candles = requests.get(CANDLES_DAILY_URL, timeout=10).json()['data']
            
            last_price = float(ticker['last'])
            open_today = float(daily_candles[0][1]) if len(daily_candles) >= 1 else last_price
            close_yesterday = float(daily_candles[1][4]) if len(daily_candles) >= 2 else last_price
            
            # جلب قمة وقاع فريم الساعة
            high_1h, low_1h = get_1h_high_low()
            last_1h_high = high_1h
            last_1h_low = low_1h
            
            msg = f"📌 [التقرير اليومي - {today_str}]\n"
            msg += f"-----------------------------------\n"
            msg += f"🌅 سعر بداية اليوم (الافتتاح): {open_today}\n"
            msg += f"📊 سعر إغلاق شمعة الأمس: {close_yesterday}\n"
            msg += f"📈 أعلى قمة (فريم 1 ساعة): {high_1h}\n"
            msg += f"📉 أدنى قاع (فريم 1 ساعة): {low_1h}\n"
            msg += f"💰 السعر الحالي: {last_price}"
            
            send_telegram(msg)
            last_report_date = today_str
        except Exception as e:
            print(f"خطأ في التقرير اليومي: {e}")

def check_1h_high_low_breakout():
    global last_1h_high, last_1h_low
    try:
        current_high, current_low = get_1h_high_low()
        
        if last_1h_high > 0 and current_high > last_1h_high:
            send_telegram(f"🔥 تنبيه كسر قمة جديدة (فريم الساعة)!\nالقمة الجديدة: {current_high}")
            last_1h_high = current_high
            
        if last_1h_low > 0 and current_low < last_1h_low:
            send_telegram(f"⚠️ تنبيه كسر قاع جديد (فريم الساعة)!\nالقاع الجديد: {current_low}")
            last_1h_low = current_low
    except Exception as e:
        print(f"خطأ في فحص اختراقات فريم الساعة: {e}")

def check_liquidity_walls():
    global tracked_wall_bid, tracked_wall_ask
    try:
        books = requests.get(ORDERBOOK_URL, timeout=10).json()['data'][0]
        bids = books.get('bids', [])
        asks = books.get('asks', [])
        
        current_bid_wall = None
        for item in bids:
            price, size = float(item[0]), float(item[1])
            if size >= WALL_THRESHOLD_BTC:
                current_bid_wall = (price, size)
                break
                
        current_ask_wall = None
        for item in asks:
            price, size = float(item[0]), float(item[1])
            if size >= WALL_THRESHOLD_BTC:
                current_ask_wall = (price, size)
                break

        if current_bid_wall and current_bid_wall != tracked_wall_bid:
            send_telegram(f"🧱 تنبيه حائط شراء جديد!\nالسعر: {current_bid_wall[0]} | الكمية: {current_bid_wall[1]} BTC")
            tracked_wall_bid = current_bid_wall
        elif not current_bid_wall and tracked_wall_bid:
            send_telegram(f"💥 تم كسر/إلغاء حائط الشراء عند السعر: {tracked_wall_bid[0]}")
            tracked_wall_bid = None

        if current_ask_wall and current_ask_wall != tracked_wall_ask:
            send_telegram(f"🧱 تنبيه حائط بيع جديد!\nالسعر: {current_ask_wall[0]} | الكمية: {current_ask_wall[1]} BTC")
            tracked_wall_ask = current_ask_wall
        elif not current_ask_wall and tracked_wall_ask:
            send_telegram(f"💥 تم كسر/إلغاء حائط البيع عند السعر: {tracked_wall_ask[0]}")
            tracked_wall_ask = None
            
    except Exception as e:
        print(f"خطأ في رصد الحوائط: {e}")

def check_large_trades_and_flow():
    try:
        trades = requests.get(TRADES_URL, timeout=10).json()['data']
        for trade in trades:
            size = float(trade['sz'])
            side = trade['side']
            price = float(trade['px'])
            
            if side == 'buy' and size >= LARGE_TRADE_BTC:
                send_telegram(f"🐳 صفقة شراء ضخمة (ماركت)!\nالحجم: {size} BTC | السعر: {price}")
            elif side == 'sell' and size >= LARGE_TRADE_BTC:
                send_telegram(f"🚨 صفقة بيع ضخمة (ماركت)!\nالحجم: {size} BTC | السعر: {price}")
                    
    except Exception as e:
        print(f"خطأ في الصفقات: {e}")

print("... بدء تشغيل نظام المراقبة والتنبيهات الذكية (فريم 1 ساعة) ...")

while True:
    try:
        check_daily_report()
        check_1h_high_low_breakout()
        check_liquidity_walls()
        check_large_trades_and_flow()
    except Exception as e:
        print(f"خطأ عام في التكرار: {e}")
        
    time.sleep(15)
