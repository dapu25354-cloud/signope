import os
import sys
import pandas as pd
import yfinance as yf
import ta
import json
import time
from datetime import datetime
from diamond_filter import analyze_diamond  # 同層

# 強制 UTF-8 輸出
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 全系統共用同一張清單(放在 TODOLIST，線上雷達也讀這張，永遠不會不一致)
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watch_list.json")

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def analyze(symbol, name):
    """
    冷血獵殺 = 抄超賣(RSI<30 或觸布林下軌)且今天止跌不破昨低。
    但抄超賣容易撿到弱股，所以先過鑽石閘門：長線趨勢向上才值得抄。
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        if df.empty or len(df) < 70:
            return None

        close = df['Close']
        low = df['Low']
        df['rsi'] = ta.momentum.rsi(close=close, window=14)
        bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
        df['bb_lband'] = bb.bollinger_lband()
        ma60 = close.rolling(60).mean()
        ma120 = close.rolling(120).mean()

        last = df.iloc[-1]
        price = float(last['Close'])
        rsi = float(last['rsi'])
        bb_l = float(last['bb_lband'])
        season_ma = float(ma60.iloc[-1])
        season_ma_20ago = float(ma60.iloc[-21])
        half_ma = float(ma120.iloc[-1]) if not pd.isna(ma120.iloc[-1]) else season_ma

        season_rising = season_ma > season_ma_20ago

        # 冷血訊號(先算技術面，便宜又快)
        stop_lower_low = float(last['Close']) >= float(df['Close'].iloc[-2])
        rsi_oversold = rsi < 30
        touch_bb = float(last['Low']) <= bb_l
        signal = stop_lower_low and (rsi_oversold or touch_bb)

        # 只有技術面先觸發的股，才去查體質(analyze_diamond 的 .info 很慢，別對整表24檔都查)
        is_diamond, grade, roe = False, "-", None
        if signal:
            dia = analyze_diamond(symbol, name)
            is_diamond = dia['is_true']
            grade = dia['grade']
            roe = dia['metrics']['roe']

        worth = is_diamond and signal
        pitch = ""
        if worth:
            trig = "RSI跌破30超賣" if rsi_oversold else "殺到布林下軌"
            pitch = (f"{name}{trig}(RSI{rsi:.0f})、今天止跌沒再破低，而且是真鑽石"
                     f"({roe and str(round(roe*100))+'% ROE' or '體質實在'})"
                     f"→強勢股被錯殺、跌到便宜區，值得撿。")

        detail = (f"[{grade}] 收{price:.1f} | RSI{rsi:.0f}"
                  f"{'(超賣)' if rsi_oversold else ''} | 布林下軌{bb_l:.1f}"
                  f"{'(觸及)' if touch_bb else ''} | 季線{season_ma:.1f}{'↑' if season_rising else '↓'}")

        return {"symbol": symbol, "name": name, "worth": worth, "pitch": pitch,
                "detail": detail, "diamond": is_diamond, "signal": signal, "grade": grade}
    except Exception as e:
        print(f"❌ {symbol} 出錯: {e}")
        return None

def run_full_scan():
    watchlist = load_watchlist()
    if not watchlist:
        print("錯誤: 觀察名單為空。")
        return

    print("--- ⚔️ 冷血獵殺(抄超賣強勢股)掃描 ---")
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    results = []
    for item in watchlist:
        print(f"掃描中: {item['symbol']} {item['name']}...", end="\r")
        r = analyze(item['symbol'], item['name'])
        if r:
            results.append(r)
        time.sleep(0.3)

    worth_list = [r for r in results if r['worth']]

    print("\n" + "=" * 60)
    if worth_list:
        print("🎯 今天值得撿的(強勢股被錯殺到超賣):")
        for r in worth_list:
            print(f"\n  ✅ {r['name']} ({r['symbol']})")
            print(f"     {r['pitch']}")
    else:
        # 有訊號但都是弱股，也講清楚，別讓她以為漏看
        weak_hits = [r for r in results if r['signal'] and not r['diamond']]
        print("🟢 今天沒有值得撿的冷血訊號。")
        if weak_hits:
            names = "、".join(f"{r['name']}({r['grade']})" for r in weak_hits)
            print(f"   ({names} 雖然超賣，但不是真鑽石，錯殺也不撿)")
        else:
            print("   名單裡沒有真鑽石跌進超賣區，沒事做。")
        print("   → 別為了做而做。")
    print("=" * 60)

if __name__ == "__main__":
    run_full_scan()
    try:
        input("\n掃描結束，按 Enter 鍵關閉視窗...")
    except EOFError:
        pass