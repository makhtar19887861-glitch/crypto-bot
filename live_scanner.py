import os
import datetime
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

# File to track the last heartbeat timestamp
HEARTBEAT_FILE = 'last_heartbeat.txt'

def send_whatsapp_alert(message):
    print(f"\n📢 WHATSAPP MESSAGE:\n{message}\n")
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and USER_WHATSAPP_TO:
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=TWILIO_WHATSAPP_FROM,
                to=USER_WHATSAPP_TO
            )
            print("✅ WhatsApp Message Sent Successfully!")
        except Exception as e:
            print(f"⚠️ Failed to send WhatsApp message: {e}")
    else:
        print("ℹ️ Twilio credentials not found. Running in local print-only mode.")

def check_heartbeat():
    """Checks if 12 hours have passed since the last status/heartbeat message."""
    now = datetime.datetime.utcnow()
    if os.path.exists(HEARTBEAT_FILE):
        try:
            with open(HEARTBEAT_FILE, 'r') as f:
                last_time_str = f.read().strip()
                last_time = datetime.datetime.fromisoformat(last_time_str)
                # If less than 12 hours have passed, don't send heartbeat
                if (now - last_time).total_seconds() < 12 * 3600:
                    return False
        except Exception:
            pass
    
    # Update heartbeat file to current time
    try:
        with open(HEARTBEAT_FILE, 'w') as f:
            f.write(now.isoformat())
    except Exception as e:
        print(f"⚠️ Could not write heartbeat file: {e}")
        
    return True

def scan_markets():
    print("=" * 60)
    print("🚀 RUNNING FLEXIBLE SMART MOMENTUM SCANNER (15m)")
    print("=" * 60)

    signals_found = 0
    signal_messages = []

    for coin_name, ticker in ASSETS.items():
        try:
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

            i = len(df) - 2
            close = df.loc[i, 'close']
            ema_9 = df.loc[i, 'EMA_9']
            ema_21 = df.loc[i, 'EMA_21']
            ema_50 = df.loc[i, 'EMA_50']
            rsi = df.loc[i, 'RSI_14']
            atr = df.loc[i, 'ATR_14']
            vol = df.loc[i, 'volume']
            vol_ma = df.loc[i, 'Vol_MA']

            # Flexible Crossover Check
            cross_bullish_now = (df.loc[i-1, 'EMA_9'] <= df.loc[i-1, 'EMA_21']) and (ema_9 > ema_21)
            cross_bullish_prev = (df.loc[i-2, 'EMA_9'] <= df.loc[i-2, 'EMA_21']) and (df.loc[i-1, 'EMA_9'] > df.loc[i-1, 'EMA_21'])
            is_bullish_setup = (cross_bullish_now or cross_bullish_prev) and (ema_9 > ema_21)

            cross_bearish_now = (df.loc[i-1, 'EMA_9'] >= df.loc[i-1, 'EMA_21']) and (ema_9 < ema_21)
            cross_bearish_prev = (df.loc[i-2, 'EMA_9'] >= df.loc[i-2, 'EMA_21']) and (df.loc[i-1, 'EMA_9'] < df.loc[i-1, 'EMA_21'])
            is_bearish_setup = (cross_bearish_now or cross_bearish_prev) and (ema_9 < ema_21)

            signal_type = None
            if is_bullish_setup and (close > ema_50) and (rsi > 45) and (vol >= 0.6 * vol_ma):
                signal_type = 'BUY'
            elif is_bearish_setup and (close < ema_50) and (rsi < 55) and (vol >= 0.6 * vol_ma):
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
                    f"⚡ Strategy: Flexible Smart Momentum"
                )
                signal_messages.append(msg)
            else:
                print(f"🔍 Asset: {coin_name:<6} | Status: No active signal on latest candle.")

        except Exception as e:
            print(f"⚠️ Error scanning {coin_name}: {e}")

    # Send actual trade signals if any found
    if signal_messages:
        for msg in signal_messages:
            send_whatsapp_alert(msg)
    else:
        # If no trade signals, check if 12 hours have passed for a heartbeat message
        if check_heartbeat():
            heartbeat_msg = (
                f"🟢 *BOT HEALTH CHECK (12H)* 🟢\n"
                f"🤖 Status: Bot is running smoothly and monitoring markets.\n"
                f"📊 No active high-probability signals right now, keeping capital safe!"
            )
            send_whatsapp_alert(heartbeat_msg)
        else:
            print("ℹ️ No signals found and 12-hour heartbeat window not reached yet.")

    print("-" * 60)
    print(f"🏁 Scan Complete. Total Signals Generated: {signals_found}")
    print("=" * 60)

if __name__ == "__main__":
    scan_markets()
