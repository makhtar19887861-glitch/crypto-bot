import os
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from twilio.rest import Client

# Top 5 Assets
ASSETS = {
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',
    'XRP': 'XRP-USD',
    'XAUUSD': 'GC=F',
    'LINK': 'LINK-USD'
}

# Twilio Credentials from GitHub Secrets / Environment Variables
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
USER_WHATSAPP_TO = os.getenv('USER_WHATSAPP_TO')

def send_whatsapp_alert(message):
    print(f"\n📢 SIGNAL ALERT:\n{message}\n")
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and USER_WHATSAPP_TO:
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=TWILIO_WHATSAPP_FROM,
                to=USER_WHATSAPP_TO
            )
            print("✅ WhatsApp Alert Sent Successfully!")
        except Exception as e:
            print(f"⚠️ Failed to send WhatsApp alert: {e}")
    else:
        print("ℹ️ Twilio credentials not found. Running in local print-only mode.")

def scan_markets():
    print("=" * 60)
    print("🚀 RUNNING LIVE SMART MOMENTUM SCANNER (15m)")
    print("=" * 60)

    signals_found = 0

    for coin_name, ticker in ASSETS.items():
        try:
            # Fetch recent data to calculate indicators
            df = yf.download(ticker, period="5d", interval="15m", progress=False)
            if df.empty:
                print(f"⚠️ No data fetched for {coin_name}")
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df = df.reset_index()
            df.columns = [str(col).lower() for col in df.columns]
            
            rename_dict = {}
            for col in df.columns:
                if 'date' in col or 'time' in col:
                    rename_dict[col] = 'open_time'
                elif 'open' in col:
                    rename_dict[col] = 'open'
                elif 'high' in col:
                    rename_dict[col] = 'high'
                elif 'low' in col:
                    rename_dict[col] = 'low'
                elif 'close' in col:
                    rename_dict[col] = 'close'
                elif 'volume' in col:
                    rename_dict[col] = 'volume'
            df = df.rename(columns=rename_dict)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna()

            # Indicators Calculation
            df['EMA_9'] = ta.ema(df['close'], length=9)
            df['EMA_21'] = ta.ema(df['close'], length=21)
            df['EMA_50'] = ta.ema(df['close'], length=50)
            df['RSI_14'] = ta.rsi(df['close'], length=14)
            df['ATR_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            df['Vol_MA'] = ta.sma(df['volume'], length=20)
            df = df.dropna().reset_index(drop=True)

            # Check the latest completed candle (Index -2 or -1 depending on execution, let's check index len-2)
            i = len(df) - 2
            close = df.loc[i, 'close']
            ema_9, prev_ema_9 = df.loc[i, 'EMA_9'], df.loc[i-1, 'EMA_9']
            ema_21, prev_ema_21 = df.loc[i, 'EMA_21'], df.loc[i-1, 'EMA_21']
            ema_50 = df.loc[i, 'EMA_50']
            rsi = df.loc[i, 'RSI_14']
            atr = df.loc[i, 'ATR_14']
            vol = df.loc[i, 'volume']
            vol_ma = df.loc[i, 'Vol_MA']

            is_bullish_cross = (prev_ema_9 <= prev_ema_21) and (ema_9 > ema_21)
            is_bearish_cross = (prev_ema_9 >= prev_ema_21) and (ema_9 < ema_21)

            signal_type = None
            if is_bullish_cross and (close > ema_50) and (rsi > 48) and (vol >= 0.8 * vol_ma):
                signal_type = 'BUY'
            elif is_bearish_cross and (close < ema_50) and (rsi < 52) and (vol >= 0.8 * vol_ma):
                signal_type = 'SELL'

            if signal_type:
                signals_found += 1
                initial_sl_distance = 2.0 * atr
                if signal_type == 'BUY':
                    sl = close - initial_sl_distance
                    tp_suggestion = close + (3.0 * atr)
                else:
                    sl = close + initial_sl_distance
                    tp_suggestion = close - (3.0 * atr)

                msg = (
                    f"🚨 *{signal_type} SIGNAL DETECTED* 🚨\n"
                    f"🪙 Asset: *{coin_name}*\n"
                    f"💲 Entry Price: `{close:.4f}`\n"
                    f"🛑 Initial SL: `{sl:.4f}`\n"
                    f"🎯 Target Zone: `{tp_suggestion:.4f}`\n"
                    f"📊 RSI: `{rsi:.1f}` | ATR: `{atr:.4f}`\n"
                    f"⚡ Strategy: Smart Momentum Trailing"
                )
                send_whatsapp_alert(msg)
            else:
                print(f"🔍 Asset: {coin_name:<6} | Status: No active signal on latest candle.")

        except Exception as e:
            print(f"⚠️ Error scanning {coin_name}: {e}")

    print("-" * 60)
    print(f"🏁 Scan Complete. Total Signals Generated: {signals_found}")
    print("=" * 60)

if __name__ == "__main__":
    scan_markets()
