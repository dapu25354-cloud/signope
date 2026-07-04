# -*- coding: utf-8 -*-
"""
轉折燈 v3 ── 五過關確認 (勢+量+均線+K棒+RSI)，含 RSI 背離
============================================================
單看5日線會被盤整雜訊巴。真轉折五關一起看：
  ① 勢  : 先漲過/跌過一段，盤整區穿越不算
  ② 量  : 轉折要帶量(量比≥1.2)
  ③ 均線: 站上/跌破10日線
  ④ K棒 : 長紅(底)/長黑(頂)實體確認
  ⑤ RSI : 動能由弱轉強(上車)/由強轉弱(下車)
  ＋背離: 價創高RSI沒跟上=頂背離(轉折前兆)；價創低RSI墊高=底背離

判定：站上/跌破5日線 + 過≥3關「且含量或均線」→ 轉折確認(買/賣)；
      過≥3關但沒量沒站上10MA = 只是彈5日線 → 🔸留意別追；只過2關 → 疑似待確認。
誠實：轉折是「轉了才確認」，抓不到最高最低，少賺頭尾換不被巴。
"""

import os
import sys
import json
import logging
import pandas as pd

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "error.log"),
    level=logging.ERROR,
    format="%(asctime)s  %(message)s",
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(__file__)
WATCHLIST = os.path.join(HERE, "watch_list.json")  # 本檔在 TODOLIST 內，清單同層
LIGHT_ORDER = {"🔻": 0, "🟠": 1, "🔺": 2, "🟡": 3, "🔸": 4, "🟢": 5, "⚪": 6, "⚠️": 7}


def load_list():
    with open(WATCHLIST, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_all(symbols):
    import yfinance as yf
    try:
        data = yf.download(symbols, period="2y", group_by="ticker",
                           auto_adjust=True, progress=False, threads=True)
    except Exception:
        logging.error("yfinance 整批抓取失敗", exc_info=True)
        return {}
    out = {}
    for s in symbols:
        try:
            df = data[s][["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(df) >= 25:
                out[s] = df
        except Exception:
            logging.error("抓不到 %s 的資料", s, exc_info=True)
    return out


def rsi14(close):
    """Wilder RSI(14)"""
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = up.ewm(alpha=1/14, adjust=False).mean() / down.ewm(alpha=1/14, adjust=False).mean()
    return 100 - 100 / (1 + rs)


def divergence(close, rsi):
    """近10日抓背離：頂背離(看跌) / 底背離(看漲)"""
    c = close.iloc[-10:]; r = rsi.iloc[-10:]
    # 頂背離：今天價接近近10日高，但RSI低於前高
    if c.iloc[-1] >= c.max() * 0.995 and r.iloc[-1] < r.iloc[:-1].max() - 2:
        return "⚡頂背離(轉弱前兆)"
    # 底背離：今天價接近近10日低，但RSI高於前低
    if c.iloc[-1] <= c.min() * 1.005 and r.iloc[-1] > r.iloc[:-1].min() + 2:
        return "⚡底背離(轉強前兆)"
    return ""


def turn(df):
    o = df["Open"]; c = df["Close"]; h = df["High"]; l = df["Low"]; v = df["Volume"]
    ma5, ma10, ma20 = c.rolling(5).mean(), c.rolling(10).mean(), c.rolling(20).mean()
    avg20 = v.rolling(20).mean()
    rsi = rsi14(c)

    # 長線強弱閘門(年線)：站上年線且年線上揚=強勢；跌破年線/年線下彎=弱股(石頭)
    # 只看價不抓基本面，所以不拖慢速度；真鑽石深度檢驗另跑「💎真鑽石篩選」
    ma240 = c.rolling(240).mean()
    yv = ma240.iloc[-1]
    if pd.isna(yv):
        strong = None  # 資料不夠算年線，強弱未知
    else:
        y_ago = ma240.iloc[-61] if len(ma240) > 61 else yv
        strong = bool(c.iloc[-1] > yv and yv > y_ago)

    # 除權斷層防呆：yfinance沒收錄的除權會讓近20日價格斷層，暫不判讀
    if (c.pct_change().abs().tail(20) > 0.35).any():
        cl = c.iloc[-1]; ch = (cl - c.iloc[-2]) / c.iloc[-2] * 100
        return {"light": "⚠️", "act": "近期除權、資料斷層→暫不判讀(等20天)",
                "close": cl, "chg": ch, "vr": float("nan"), "rsi": rsi.iloc[-1], "strong": strong}

    close, close1 = c.iloc[-1], c.iloc[-2]
    m5, m5_1 = ma5.iloc[-1], ma5.iloc[-2]
    m10 = ma10.iloc[-1]
    m5_1v, m20_1v = ma5.iloc[-2], ma20.iloc[-2]
    chg = (close - close1) / close1 * 100
    vr = v.iloc[-1] / avg20.iloc[-1] if not pd.isna(avg20.iloc[-1]) else 1.0
    body = (close - o.iloc[-1]) / o.iloc[-1] * 100
    upper = (h.iloc[-1] - close) / (h.iloc[-1] - l.iloc[-1] + 1e-9)
    rsi_now, rsi_prev = rsi.iloc[-1], rsi.iloc[-2]
    div = divergence(c, rsi)

    # 盤整過濾：近10日振幅太小(<4%)=牛皮股，沒「勢」就沒「折」，不給上下車
    amp10 = (c.iloc[-10:].max() - c.iloc[-10:].min()) / c.iloc[-10:].min() * 100
    has_swing = amp10 >= 4.0

    up_cross = close > m5 and close1 <= m5_1 and has_swing
    down_cross = close < m5 and close1 >= m5_1 and has_swing

    light, act = None, None
    if up_cross:
        checks = {
            "勢": m5_1v < m20_1v,
            "量": vr >= 1.2,
            "均線": close > m10,
            "K棒": body >= 1.5,
            "RSI": rsi_now > rsi_prev and rsi_now < 70,
        }
        n = sum(checks.values()); pl = "·".join(k for k, ok in checks.items() if ok) or "無"
        confirmed = checks["量"] or checks["均線"]   # 真上車要帶量 或 站上10MA,不能只靠勢+K棒+RSI(一根紅K全過)
        if n >= 3 and confirmed:
            light, act = "🔺", f"上車(買)→轉折向上 [{n}/5:{pl}]"
        elif n >= 3:
            light, act = "🔸", f"留意·彈上5日線但沒量沒站上10MA→別當買、別追 [{n}/5:{pl}]"
        elif n == 2:
            light, act = "🔸", f"疑似轉強,待確認 [{n}/5:{pl}]"
    elif down_cross:
        checks = {
            "勢": m5_1v > m20_1v,
            "量": vr >= 1.2,
            "均線": close < m10,
            "K棒": body <= -1.5 or upper > 0.5,
            "RSI": rsi_now < rsi_prev and rsi_now > 30,
        }
        n = sum(checks.values()); pl = "·".join(k for k, ok in checks.items() if ok) or "無"
        confirmed = checks["量"] or checks["均線"]   # 真下車要帶量 或 跌破10MA,不能只靠勢+K棒+RSI
        if n >= 3 and confirmed:
            light, act = "🔻", f"下車(賣)→轉折向下 [{n}/5:{pl}]"
        elif n >= 3:
            light, act = "🔸", f"留意·跌破5日線但沒量沒跌破10MA→別急殺、待確認 [{n}/5:{pl}]"
        elif n == 2:
            light, act = "🔸", f"疑似轉弱,待確認 [{n}/5:{pl}]"

    if light is None:  # 沒確認轉折 → 看續勢
        if not has_swing:
            # 死水裡再分：布林帶收窄到近20日最窄 + 量縮 = 量縮蓄勢(準備噴)，不是死水
            std20 = c.rolling(20).std()
            bbw = (4 * std20) / ma20                       # 布林帶寬 (upper-lower)/ma20
            squeeze = bbw.iloc[-1] <= bbw.tail(20).quantile(0.30)
            if squeeze and vr < 0.8:
                light, act = "🟡", f"量縮蓄勢(布林收窄+量縮{vr:.2f})→可能噴出,留意上車別急換"
            else:
                light, act = "🟠", f"死水盤整(振幅{amp10:.1f}%)→卡資金,汰弱換股"
        elif close > m5 and m5 > m10:
            light, act = "🟢", "多頭續勢,沒轉折→續抱"
        elif close < m5 and m5 < m10:
            light, act = "⚪", "空頭,沒轉折→別接"
        else:
            light, act = "⚪", "盤整,沒轉折→觀望"

    if div:
        act += "  " + div

    # === 特例防呆 (從量燈號併入)：漲跌停/跳空/指數調整假量 ===
    flags = []
    gap = (o.iloc[-1] - close1) / close1 * 100
    if o.iloc[-1] > h.iloc[-2] and gap >= 1.5:
        flags.append(f"⚡跳空+{gap:.1f}%")
    elif o.iloc[-1] < l.iloc[-2] and gap <= -1.5:
        flags.append(f"⚡跳空{gap:.1f}%")
    if chg >= 9.5:
        flags.append("🔺漲停")
    elif chg <= -9.5:
        flags.append("🔻跌停")
    if vr >= 3.0:
        flags.append(f"異常爆量{vr:.1f}(指數調整?假量)")
    if flags:
        act += "  〔" + "·".join(flags) + "·查新聞〕"

    # 弱股閘門：跌破年線的石頭就算技術轉強，也不能當「買進/上車」，只能短搶
    if strong is False and light in ("🔺", "🟡"):
        act += "  ⚠但這是跌破年線的弱股→只能短線搶反彈,別當買進、別加碼長抱"
    # 強勢股保護：站上年線的好股出現下車，多半是回檔洗盤，別被洗出去
    if strong is True and light == "🔻":
        act += "  ⚠但這是站上年線的強勢股→這種下車多半是回檔洗盤,別急殺,拉回反而是接點"

    return {"light": light, "act": act, "close": close, "chg": chg, "vr": vr,
            "rsi": rsi_now, "strong": strong}


def main():
    items = load_list()
    print(f"抓取 {len(items)} 檔…")
    data = fetch_all([it["symbol"] for it in items])

    rows = []
    for i, it in enumerate(items, 1):
        if it["symbol"] in data:
            rows.append((i, it["name"], turn(data[it["symbol"]])))
    rows.sort(key=lambda r: LIGHT_ORDER[r[2]["light"]])

    print("=" * 76)
    print("  轉折燈 v3  (勢+量+均線+K棒+RSI 五過關；上車🔺/下車🔻排前)")
    print("=" * 76)
    print(f"  {'編號':<4}{'燈':<3}{'名稱':<7}{'收盤':>8}{'漲跌%':>7}{'量比':>6}{'RSI':>5}  訊號")
    print("-" * 76)
    for i, name, t in rows:
        nm = name + "　" * (4 - len(name))
        print(f"  {i:<4}{t['light']:<3}{nm}{t['close']:>8.1f}{t['chg']:>+7.1f}{t['vr']:>6.2f}{t['rsi']:>5.0f}  {t['act']}")
    print("=" * 76)
    downs = [r[1] for r in rows if r[2]["light"] == "🔻" and r[2].get("strong") is not True]
    downs_wash = [r[1] for r in rows if r[2]["light"] == "🔻" and r[2].get("strong") is True]
    dead = [r[1] for r in rows if r[2]["light"] == "🟠"]
    ups = [r[1] for r in rows if r[2]["light"] == "🔺" and r[2].get("strong") is not False]
    ups_weak = [r[1] for r in rows if r[2]["light"] == "🔺" and r[2].get("strong") is False]
    sus = [r[1] for r in rows if r[2]["light"] == "🔸"]
    coil = [r[1] for r in rows if r[2]["light"] == "🟡"]
    if downs: print(f"  🔻 下車(賣)：{'、'.join(downs)}")
    if downs_wash: print(f"  🛡️ 強勢股下車=多半回檔洗盤(別被洗掉,拉回是接點)：{'、'.join(downs_wash)}")
    if dead: print(f"  🟠 死水換股(卡資金,汰弱)：{'、'.join(dead)}")
    if ups: print(f"  🔺 上車(買·站上年線的強勢股)：{'、'.join(ups)}")
    if ups_weak: print(f"  ⚠ 技術轉強但破年線弱股(只能短搶,別買進/加碼)：{'、'.join(ups_weak)}")
    if coil: print(f"  🟡 量縮蓄勢(準備噴,留意)：{'、'.join(coil)}")
    if sus: print(f"  🔸 疑似(待確認)：{'、'.join(sus)}")
    if not (downs or downs_wash or dead or ups or ups_weak or coil or sus): print("  今天沒有訊號。")
    print("  RSI>70過熱、<30過冷；⚡背離=轉折前兆，要留意")


if __name__ == "__main__":
    main()
