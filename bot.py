import subprocess
import sys

def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"جاري تثبيت المكتبة {package} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_and_import("requests")

import time
import requests
import datetime

# --- بيانات بوت تليجرام الخاص بك ---
TELEGRAM_BOT_TOKEN = "8698370133:AAH6yRXtsjTorCCx5iT0PYRjVuOj_Nng0x8"
TELEGRAM_CHAT_ID = "8201127054"
# ----------------------------------

# روابط OKX
TICKER_URL = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
CANDLES_URL = "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=3"
ORDERBOOK_URL = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=40"

# متغيرات تتبع الحالة اليومية
current_day = None
daily_open_price = 0.0
yesterday_close_price = 0.0
day_high = 0.0
day_low = 0.0

last_sent_high = 0.0
last_sent_low = 0.0

active_walls = []      # الحوائط الحالية
broken_walls = []      # الحوائط التي كسرت ومتى كسرت
new_walls_detected = [] # الحوائط الجديدة

last_candle_time = None
last_update_offset = 0

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال تليجرام: {e}")
        return None

def fetch_market_data():
    try:
        # جلب السعر الحالي
        res = requests.get(TICKER_URL, timeout=10).json()
        ticker = res.get('data', [])[0]
        last_price = float(ticker['last'])
        high_24h = float(ticker['high24h'])
        low_24h = float(ticker['low24h'])
        
        # جلب الشموع اليومية (لمعرفة الافتتاح والإغلاق السابق)
        c_res = requests.get(CANDLES_URL, timeout=10).json()
        candles = c_res.get('data', [])
        
        open_price = last_price
        prev_close = last_price
        
        if len(candles) >= 2:
            # شمعة اليوم الحالي
            open_price = float(candles[0][1])
            # شمعة الأمس (إغلاق أمس)
            prev_close = float(candles[1][4])
        
        return last_price, open_price, prev_close, high_24h, low_24h
    except Exception as e:
        print(f"خطأ في جلب بيانات السوق: {e}")
        return None

def fetch_orderbook_walls():
    try:
        res = requests.get(ORDERBOOK_URL, timeout=10).json()
        data = res.get('data', [])[0]
        bids = data.get('bids', []) # الطلبات (شراء)
        asks = data.get('asks', []) # العروض (بيع)
        
        walls = []
        # عتبة اعتبار الطلب أو العرض "حائط" ضخم (مثلاً أكبر من 5 بيتكوين)
        wall_threshold = 5.0 
        
        for price_s, size_s, _, _ in bids:
            price = float(price_s)
            size = float(size_s)
            if size >= wall_threshold:
                walls.append({"type": "شراء (طلب)", "price": price, "size": size, "status": "قائم"})
                
        for price_s, size_s, _, _ in asks:
            price = float(price_s)
            size = float(size_s)
            if size >= wall_threshold:
                walls.append({"type": "بيع (عرض)", "price": price, "size": size, "status": "قائم"})
                
        return walls
    except Exception as e:
        print(f"خطأ في جلب دفتر الأوامر: {e}")
        return []

def generate_market_report():
    data = fetch_market_data()
    if not data:
        return "⚠️ عذراً، تعذر جلب بيانات السوق حالياً من منصة OKX."
    
    last_price, open_price, prev_close, high_24h, low_24h = data
    walls = fetch_orderbook_walls()
    
    report = f"📊 *تقرير بيانات سوق البيتكوين (BTC/USDT)* 📊\n\n"
    report += f"💰 *السعر الحالي:* `{last_price}`\n"
    report += f"📊 *آخر سعر أغلق عليه السوق أمس:* `{prev_close}`\n"
    report += f"🌅 *السوق بدأ اليوم بسعر:* `{open_price}`\n"
    report += f"📈 *أعلى قمة سجلت خلال اليوم:* `{high_24h}`\n"
    report += f"📉 *أدنى قاع سجل خلال اليوم:* `{low_24h}`\n\n"
    
    report += f"🧱 *الحوائط الحالية في السوق ({len(walls)} حائط):*\n"
    if walls:
        for w in walls[:5]: # عرض أول 5 حوائط رئيسية لمنع طول الرسالة
            report += f"- {w['type']} عند السعر `{w['price']}` بحجم `{w['size']} BTC` (الحالة: {w['status']})\n"
    else:
        report += "- لا توجد حوائط ضخمة مرصودة حالياً.\n"
        
    if broken_walls:
        report += f"\n⚠️ *الحوائط التي كسرت اليوم:* {len(broken_walls)}\n"
        for bw in broken_walls[-3:]:
            report += f"- حائط {bw['type']} عند `{bw['price']}` كسر في وقت: `{bw['time']}`\n"
            
    return report

def check_telegram_messages():
    global last_update_offset
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_update_offset}&timeout=1"
    try:
        res = requests.get(url, timeout=3).json()
        if res.get("ok"):
            for result in res.get("result", []):
                last_update_offset = result["update_id"] + 1
                message = result.get("message", {})
                text = message.get("text", "").strip()
                chat_id = message.get("chat", {}).get("id")
                
                # التحقق إذا طلب المستخدم تقرير السوق
                if text and any(word in text for word in ["بيانات", "السوق", "سعر", "قمة", "قاع", "الحوائط", "تحليل", "تقرير"]):
                    if str(chat_id) == str(TELEGRAM_CHAT_ID):
                        report = generate_market_report()
                        send_telegram_message(report)
    except Exception as e:
        print(f"خطأ في قراءة رسائل تليجرام: {e}")

print("تم بدء تشغيل بوت مراقبة وتفاعل OKX بنجاح...")

while True:
    try:
        now = datetime.datetime.utcnow()
        today_date = now.date()
        
        # تفقد الرسائل الواردة من تليجرام بشكل مستمر وسريع
        check_telegram_messages()
        
        # تحديث البيانات اليومية عند بداية يوم جديد
        market_data = fetch_market_data()
        if market_data:
            last_price, open_price, prev_close, high_24h, low_24h = market_data
            
            if current_day != today_date:
                current_day = today_date
                daily_open_price = open_price
                yesterday_close_price = prev_close
                day_high = high_24h
                day_low = low_24h
                active_walls = fetch_orderbook_walls()
                send_telegram_message(f"🌅 *تقرير الافتتاح اليومي*\n- سعر الافتتاح: `{open_price}`\n- إغلاق أمس: `{prev_close}`")
            else:
                if high_24h > day_high:
                    day_high = high_24h
                if low_24h < day_low:
                    day_low = low_24h

        time.sleep(5) # فترة راحة قصيرة لتجنب الضغط على الخوادم
        
    except Exception as e:
        print(f"حدث خطأ في الحلقة الرئيسية: {e}")
        time.sleep(10)
