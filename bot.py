import time
import requests
from datetime import datetime

# إعدادات تيليجرام (تأكد من وضع بياناتك هنا أو سحبها من البيئة Environment Variables)
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"[Telegram Mock]: {message}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending telegram message: {e}")

def get_okx_market_data():
    """
    جلب بيانات البيتكوين الحالية من OKX (السعر، الفوليوم، أعلى/أدنى سعر)
    """
    try:
        url = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data["code"] == "0" and len(data["data"]) > 0:
            ticker = data["data"][0]
            return {
                "last": float(ticker["last"]),
                "vol24h": float(ticker["vol24h"]),
                "high24h": float(ticker["high24h"]),
                "low24h": float(ticker["low24h"])
            }
    except Exception as e:
        print(f"Error fetching OKX data: {e}")
    return None

def get_okx_orderbook_walls():
    """
    محاكاة أو جلب الجدران والأموال المعلقة من دفتر الأوامر
    """
    try:
        url = "https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=20"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data["code"] == "0" and len(data["data"]) > 0:
            basks = data["data"][0]["asks"] # عروض البيع (الجدران العلوية)
            bids = data["data"][0]["bids"] # طلبات الشراء (الجدران السفلية)
            
            # البحث عن أكبر حجم أموال معلق (حائط)
            max_bid_vol = 0
            max_bid_price = 0
            for item in bids:
                price = float(item[0])
                vol = float(item[1])
                if vol > max_bid_vol:
                    max_bid_vol = vol
                    max_bid_price = price
                    
            return {"wall_price": max_bid_price, "wall_vol": max_bid_vol}
    except Exception as e:
        print(f"Error fetching orderbook: {e}")
    return None

def main():
    print("Bot started monitoring OKX Bitcoin market...")
    
    # متغيرات لتتبع الحالة وتجنب التكرار
    last_day = datetime.now().day
    last_sent_candle_time = 0
    
    previous_ath = 0
    previous_atl = 99999999
    last_wall_price = 0
    
    # رسالة بداية التشغيل اليومية
    market_data = get_okx_market_data()
    if market_data:
        day_msg = (
            f"🌅 *تقرير بداية اليوم للبيتكوين*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 سعر الافتتاح / الحالي: `{market_data['last']}` $\n"
            f"📈 أعلى قمة مسجلة: `{market_data['high24h']}` $\n"
            f"📉 أدنى قاع مسجل: `{market_data['low24h']}` $\n"
        )
        send_telegram_message(day_msg)
        previous_ath = market_data['high24h']
        previous_atl = market_data['low24h']

    while True:
        try:
            current_time = time.time()
            current_day = datetime.now().day
            
            # فحص تغيير اليوم لإرسال تقرير يومي جديد
            if current_day != last_day:
                last_day = current_day
                market_data = get_okx_market_data()
                if market_data:
                    send_telegram_message(f"📅 *بداية يوم جديد*\nسعر الافتتاح: `{market_data['last']}` $")
            
            market_data = get_okx_market_data()
            orderbook = get_okx_orderbook_walls()
            
            if market_data:
                price = market_data['last']
                high = market_data['high24h']
                low = market_data['low24h']
                vol = market_data['vol24h']
                
                # 1. التحقق من تسجيل قمة جديدة أو قاع جديد (بدون تكرار مزعج)
                if high > previous_ath:
                    previous_ath = high
                    send_telegram_message(f"🚨 *تم تسجيل قمة جديدة!* 🚀\nالسعر وصل إلى: `{high}` $")
                
                if low < previous_atl and low > 0:
                    previous_atl = low
                    send_telegram_message(f"⚠️ *تم تسجيل قاع جديد!* 🔻\nالسعر انخفض إلى: `{low}` $")

                # 2. إرسال تقرير كل نصف ساعة (إغلاق الشمعة الفرضية والفوليوم)
                # (كل 1800 ثانية = 30 دقيقة)
                if current_time - last_sent_candle_time >= 1800:
                    last_sent_candle_time = current_time
                    
                    # حساب نسبة القرب من القمة والقاع
                    range_span = high - low if high != low else 1
                    distance_from_high_pct = ((high - price) / range_span) * 100
                    
                    candle_msg = (
                        f"📊 *تحديث إغلاق نصف ساعة (شمعة البيتكوين)*\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"💵 سعر الإغلاق: `{price}` $\n"
                        f"📦 الفوليوم (حجم التداول): `{vol:.2f}`\n"
                        f"📏 القرب من القمة: يبعد بنسبة `{distance_from_high_pct:.2f}%`\n"
                        f"📈 القمة الحالية: `{high}` $ | القاع الحالي: `{low}` $"
                    )
                    send_telegram_message(candle_msg)

                # 3. مراقبة الجدران والأموال المعلقة وكسرها
                if orderbook:
                    wall_p = orderbook['wall_price']
                    wall_v = orderbook['wall_vol']
                    
                    if last_wall_price == 0:
                        last_wall_price = wall_p
                        send_telegram_message(f"🧱 *تم رصد حائط (أموال معلقة جديد)*\nالسعر: `{wall_p}` $ | الحجم: `{wall_v}` BTC")
                    
                    # إذا تم كسر الحائط (تجاوز السعر الحالي سعر الحائط بشكل واضح)
                    elif abs(price - last_wall_price) > 50 and price > last_wall_price:
                        send_telegram_message(f"💥 *تم كسر الحائط بنجاح!* \nالسعر الحالي تجاوز الحائط عند سعر: `{price}` $ (كان الحائط عند `{last_wall_price}` $)")
                        last_wall_price = wall_p # تحديث الحائط الجديد

            # فحص السوق كل 60 ثانية
            time.sleep(60)
            
        except Exception as e:
            print(f"Main loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
