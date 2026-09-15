import os
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import urllib.request
import urllib.parse
import base64
import yfinance as yf

# =========================================================
#  TWILIO CONFIGURATION
# =========================================================
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
USER_WHATSAPP_NUMBER = os.environ.get("USER_WHATSAPP_NUMBER")

# Yahoo Finance Tickers for Top 5 Assets
ASSETS = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'XRP': 'XRP-USD',
    'XAUUSD': 'XAUUSD=X',
    'LINK': 'LINK-USD'
}

def send_whatsapp_alert(message):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("⚠️ Twilio credentials missing!")
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
            print("📲 WhatsApp summary sent successfully!")
    except Exception as e:
        print(f"❌ WhatsApp Error: {e}")

def fetch_1h_data(ticker):
    """ Fetches 1H candles using Yahoo Finance """
    df = yf.download(ticker, period="60d", interval="1h", progress=False)
    if df.empty:
        raise ValueError(f"No data fetched for {ticker}")
    
    # Flatten multi-index columns if yfinance returns them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df.reset_index()
    # Standardize column names
    df = df.rename(columns={
        'Datetime': 'open_time', 'Date': 'open_time',
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
    })
    
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
    print(f"\n[{now_str}] --- SCANNING TOP 5 ASSETS (YAHOO FINANCE) ---")
    
    report_message = f"📊 Hourly Scan Report\nTime: {now_str}\n\n"

    for coin_name, ticker in ASSETS.items():
        try:
            df = fetch_1h_data(ticker)
            i = len(df) - 2  # Last completed 1H candle
            
            close = df.loc[i, 'close']
            ema_20, ema_50, prev_ema_50 = df.loc[i, 'EMA_20'], df.loc[i, 'EMA_50'], df.loc[i-1, 'EMA_50']
            ema_200 = df.loc[i, 'EMA_200']
            rsi, prev_rsi = df.loc[i, 'RSI_14'], df.loc[i-1, 'RSI_14']
            adx, atr = df.loc[i, 'ADX_14'], df.loc[i, 'ATR_14']
            vol, vol_ma = df.loc[i, 'volume'], df.loc[i, 'Vol_MA']
            
            if coin_name in ['BTC', 'ETH', 'XRP']:
                min_adx = 18
            elif coin_name == 'XAUUSD':
                min_adx = 24
            else:
                min_adx = 22

            # BUY SIGNAL
            if (ema_20 > ema_50) and (ema_50 > prev_ema_50) and (close > ema_200) and (adx > min_adx):
                if (prev_rsi <= 42) and (rsi > 42) and (vol >= 0.85 * vol_ma):
                    report_message += f"🟢 #{coin_name}: BUY SIGNAL! (${close:,.2f})\n"
                    print(f"🔥 [BUY SIGNAL] {coin_name} @ ${close:,.4f}")
                    continue

            # SELL SIGNAL
            if (ema_20 < ema_50) and (ema_50 < prev_ema_50) and (close < ema_200) and (adx > min_adx):
                if (prev_rsi >= 58) and (rsi < 58) and (vol >= 0.85 * vol_ma):
                    report_message += f"🔴 #{coin_name}: SELL SIGNAL! (${close:,.2f})\n"
                    print(f"🔻 [SELL SIGNAL] {coin_name} @ ${close:,.4f}")
                    continue

            # NO SIGNAL
            report_message += f"⚪ #{coin_name}: No Signal (${close:,.2f})\n"
            print(f"[{coin_name}] Status: No Signal | Price: ${close:,.2f}")

        except Exception as e:
            print(f"⚠️ Error checking {coin_name}: {e}")
            report_message += f"⚠️ #{coin_name}: Error\n"

    send_whatsapp_alert(report_message)

if __name__ == "__main__":
    check_live_signals()
