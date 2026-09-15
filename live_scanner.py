import urllib.request
import urllib.parse
import json
import os
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import base64

# =========================================================
#  TWILIO CONFIGURATION (GitHub Secrets se uthaye ga)
# =========================================================
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
USER_WHATSAPP_NUMBER = os.environ.get("USER_WHATSAPP_NUMBER")

PAIRS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'XAUUSDT', 'LINKUSDT']

def send_whatsapp_alert(message):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("⚠️ Twilio credentials missing in environment variables!")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = urllib.parse.urlencode({
        'From': TWILIO_WHATSAPP_NUMBER,
        'To': USER_WHATSAPP_NUMBER,
        'Body': message
    }).encode('utf-8')
    
    auth_string = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
    auth_header = "Basic " + base64.b64encode(auth_string.encode('ascii')).decode('ascii')
    
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': auth_header,
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0'
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            print("📲 WhatsApp alert sent successfully!")
    except Exception as e:
        print(f"❌ WhatsApp Error: {e}")

def fetch_recent_1h_data(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1h&limit=250"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=250"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'tb_base', 'tb_quote', 'ignore'
    ])
    df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
        
    df['EMA_20'] = ta.ema(df['close'], length=20)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['EMA_200'] = ta.ema(df['close'], length=200)
    df['RSI_14'] = ta.rsi(df['close'], length=14)
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    df['ADX_14'] = adx_df['ADX_14'] if adx_df is not None and 'ADX_14' in adx_df.columns else 25.0
    df['ATR_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['Vol_MA'] = ta.sma(df['volume'], length=20)
    return df

def check_live_signals():
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{now_str}] --- SCANNING TOP 5 ASSETS (1H CANDLES) ---")
    
    signals_found = 0

    for symbol in PAIRS:
        try:
            df = fetch_recent_1h_data(symbol)
            i = len(df) - 2  # Last completed 1H candle
            
            coin_name = symbol.replace('USDT', '')
            close = df.loc[i, 'close']
            ema_20, ema_50, prev_ema_50 = df.loc[i, 'EMA_20'], df.loc[i, 'EMA_50'], df.loc[i-1, 'EMA_50']
            ema_200 = df.loc[i, 'EMA_200']
            rsi, prev_rsi = df.loc[i, 'RSI_14'], df.loc[i-1, 'RSI_14']
            adx, atr = df.loc[i, 'ADX_14'], df.loc[i, 'ATR_14']
            vol, vol_ma = df.loc[i, 'volume'], df.loc[i, 'Vol_MA']
            
            if symbol in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']:
                min_adx = 18
            elif symbol == 'XAUUSDT':
                min_adx = 24
            else:
                min_adx = 22

            # BUY SIGNAL
            if (ema_20 > ema_50) and (ema_50 > prev_ema_50) and (close > ema_200) and (adx > min_adx):
                if (prev_rsi <= 42) and (rsi > 42) and (vol >= 0.85 * vol_ma):
                    sl = close - (1.4 * atr)
                    tp = close + (3.5 * atr)
                    signals_found += 1
                    
                    alert_msg = (
                        f"🚀 BUY SIGNAL DETECTED!\n\n"
                        f"Asset: #{coin_name}/USDT\n"
                        f"Entry Price: ${close:,.4f}\n"
                        f"Stop Loss (SL): ${sl:,.4f}\n"
                        f"Take Profit (TP): ${tp:,.4f}\n"
                        f"Risk/Reward: 1 : 2.5\n\n"
                        f"Time: {now_str}"
                    )
                    print(f"🔥 [BUY SIGNAL] {symbol} @ ${close:,.4f}")
                    send_whatsapp_alert(alert_msg)
                    continue

            # SELL SIGNAL
            if (ema_20 < ema_50) and (ema_50 < prev_ema_50) and (close < ema_200) and (adx > min_adx):
                if (prev_rsi >= 58) and (rsi < 58) and (vol >= 0.85 * vol_ma):
                    sl = close + (1.4 * atr)
                    tp = close - (3.5 * atr)
                    signals_found += 1
                    
                    alert_msg = (
                        f"🔻 SELL / SHORT SIGNAL DETECTED!\n\n"
                        f"Asset: #{coin_name}/USDT\n"
                        f"Entry Price: ${close:,.4f}\n"
                        f"Stop Loss (SL): ${sl:,.4f}\n"
                        f"Take Profit (TP): ${tp:,.4f}\n"
                        f"Risk/Reward: 1 : 2.5\n\n"
                        f"Time: {now_str}"
                    )
                    print(f"🔻 [SELL SIGNAL] {symbol} @ ${close:,.4f}")
                    send_whatsapp_alert(alert_msg)
                    continue

            print(f"[{coin_name}] Status: No Signal | Price: ${close:,.2f}")
        except Exception as e:
            print(f"⚠️ Error checking {symbol}: {e}")

    if signals_found == 0:
        print("✅ Scan complete: All 5 assets checked. No active signal.")

if __name__ == "__main__":
    check_live_signals()