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
CHART_DIR = os.path.join(os.path.dirname(HERE), "轉折圖表")  # 觸發爆量黑K/量縮上漲時存K線圖，桌面看盤時自己先練習判讀


def save_chart(symbol, name, df):
    """觸發爆量黑K/量縮上漲時，存一張K線圖(近60日+月線)方便她自己練習看圖，不影響主流程(存圖失敗就算了)。"""
    try:
        import mplfinance as mpf
        os.makedirs(CHART_DIR, exist_ok=True)
        plot_df = df.tail(60).copy()
        plot_df["MA20"] = df["Close"].rolling(20).mean().tail(60)
        mc = mpf.make_marketcolors(up="#ff5252", down="#4caf50", edge="inherit", wick="inherit", volume="in")
        style = mpf.make_mpf_style(base_mpf_style="nightclouds", marketcolors=mc,
                                     rc={"font.sans-serif": "Microsoft JhengHei", "axes.unicode_minus": False})
        out_path = os.path.join(CHART_DIR, f"{name}_{symbol.split('.')[0]}.png")
        mpf.plot(plot_df, type="candle", style=style, volume=True,
                  addplot=[mpf.make_addplot(plot_df["MA20"], color="#ffb74d", width=1.3)],
                  title=f"\n{name}({symbol}) 近60日K線 — 月線(橘)", savefig=out_path)
        return out_path
    except Exception:
        logging.error("存%s圖表失敗", name, exc_info=True)
        return None


def load_list():
    with open(WATCHLIST, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_all(symbols):
    import yfinance as yf
    try:
        data = yf.download(symbols, period="2y", group_by="ticker",
                           auto_adjust=False, progress=False, threads=True)
    except Exception:
        logging.error("yfinance 整批抓取失敗", exc_info=True)
        return {}
    # 2026-07-13起全系統統一用「未還原價」(跟券商軟體看到的真實成交價一致，
    # 不做除權息的回溯調整)，價格/月線/季線/RSI全部用同一份資料算，不再需要
    # 額外抓一份真實價來覆蓋顯示(之前雙軌做法已停用，見對應記憶)。
    out = {}
    for s in symbols:
        try:
            df = data[s][["Open", "High", "Low", "Close", "Volume"]].dropna()
            # 跳過尾端0成交量的假日(颱風假/未開盤)，讓iloc[-1]永遠是最近一個真實交易日
            while len(df) > 0 and df["Volume"].iloc[-1] == 0:
                df = df.iloc[:-1]
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

    # 爆量黑K收低：近期(近4天內)創過高，當天卻爆量黑K收在當日低點附近 → 比5日線更早的出貨警訊
    recent_peak = h.iloc[-4:].max()
    prior_high = c.iloc[-20:-4].max() if len(c) >= 24 else c.iloc[:-4].max()
    near_recent_high = recent_peak >= prior_high * 0.97
    is_black = close < o.iloc[-1]
    close_low_pos = (close - l.iloc[-1]) / (h.iloc[-1] - l.iloc[-1] + 1e-9)
    blowoff_reversal = near_recent_high and vr >= 1.5 and is_black and close_low_pos <= 0.35

    # 衝高遇壓：不管當天收紅收黑，只要創高當天留一大截上影線+爆量，代表高點有人在賣、股價被打回來
    # (大立光那種噴出頂部就是這型：6/17收紅但留長上影線，不會被「爆量黑K收低」抓到，這條專門補這個洞)
    blowout_top = near_recent_high and vr >= 1.5 and upper >= 0.4

    # 量縮上漲：已經漲一大段之後，今天上漲但量縮，買盤後繼無力的價量背離警訊
    low20 = c.iloc[-20:].min()
    extended_rally = close >= low20 * 1.25
    volume_price_divergence = extended_rally and chg > 0 and vr <= 0.8

    # 爆量黑K的背景判斷：分辨是「漲很久後的真反轉(出貨)」還是「剛突破的正常震盪(換手)」
    # 剛突破的起漲點(爆量那天之前的次高)還守得住 = 換手；已經漲一大段才反轉 = 出貨機率高
    blowoff_type = None
    blowoff_level = None
    if blowoff_reversal:
        pre_breakout = c.iloc[-6:-2].max() if len(c) >= 6 else c.iloc[:-2].max()
        holding_breakout = l.iloc[-1] >= pre_breakout * 0.98
        blowoff_level = pre_breakout
        if extended_rally:
            blowoff_type = "distribution"   # 漲很久後反轉，較可能是真出貨
        elif holding_breakout:
            blowoff_type = "consolidation"  # 剛突破，還守得住起漲點，較可能是換手
        else:
            blowoff_type = "failed"         # 剛突破但已跌破起漲點，突破失敗，要小心

    # 盤整過濾：近10日振幅太小(<4%)=牛皮股，沒「勢」就沒「折」，不給上下車
    amp10 = (c.iloc[-10:].max() - c.iloc[-10:].min()) / c.iloc[-10:].min() * 100
    has_swing = amp10 >= 4.0

    up_cross = close > m5 and close1 <= m5_1 and has_swing
    down_cross = close < m5 and close1 >= m5_1 and has_swing

    light, act, n_checks = None, None, None
    if up_cross:
        checks = {
            "勢": m5_1v < m20_1v,
            "量": vr >= 1.2,
            "均線": close > m10,
            "K棒": body >= 1.5,
            "RSI": rsi_now > rsi_prev and rsi_now < 70,
        }
        n = sum(checks.values()); pl = "·".join(k for k, ok in checks.items() if ok) or "無"
        n_checks = n
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
        n_checks = n
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
    if blowoff_reversal:
        type_label = {"distribution": "疑似出貨", "consolidation": "疑似換手", "failed": "突破失敗"}[blowoff_type]
        act += f"  💣爆量黑K收低({type_label})"
    if volume_price_divergence:
        act += "  📉量縮上漲"
    if blowout_top:
        act += "  ⚠️衝高遇壓"

    # 弱股閘門：跌破年線的石頭就算技術轉強，也不能當「買進/上車」，只能短搶
    if strong is False and light in ("🔺", "🟡"):
        act += "  ⚠但這是跌破年線的弱股→只能短線搶反彈,別當買進、別加碼長抱"
    # 強勢股保護：站上年線的好股出現下車，多半是回檔洗盤，別被洗出去
    if strong is True and light == "🔻":
        act += "  ⚠但這是站上年線的強勢股→這種下車多半是回檔洗盤,別急殺,拉回反而是接點"

    return {"light": light, "act": act, "close": close, "chg": chg, "vr": vr,
            "rsi": rsi_now, "strong": strong, "n_checks": n_checks,
            "blowoff": blowoff_reversal, "blowoff_type": blowoff_type, "blowoff_level": blowoff_level,
            "vol_div": volume_price_divergence, "blowout_top": blowout_top}


def main():
    items = load_list()
    print(f"抓取 {len(items)} 檔…")
    data = fetch_all([it["symbol"] for it in items])

    rows = []
    for i, it in enumerate(items, 1):
        if it["symbol"] in data:
            rows.append((i, it["name"], turn(data[it["symbol"]]), it["symbol"]))
    rows.sort(key=lambda r: LIGHT_ORDER[r[2]["light"]])

    # 觸發爆量黑K/量縮上漲的股票，順手存一張K線圖，她可以自己先練習看圖
    charted = []
    for i, name, t, symbol in rows:
        if t.get("blowoff") or t.get("vol_div"):
            path = save_chart(symbol, name, data[symbol])
            if path:
                charted.append((name, path))

    print("=" * 76)
    print("  轉折燈 v3  (勢+量+均線+K棒+RSI 五過關；上車🔺/下車🔻排前)")
    print("=" * 76)
    print(f"  {'編號':<4}{'燈':<3}{'名稱':<7}{'收盤':>8}{'漲跌%':>7}{'量比':>6}{'RSI':>5}  訊號")
    print("-" * 76)
    for i, name, t, _symbol in rows:
        nm = name + "　" * (4 - len(name))
        vtag = "放量" if t['vr'] >= 1.5 else ("量縮" if t['vr'] <= 0.6 else "量平")
        rtag = "過熱" if t['rsi'] >= 70 else ("超賣" if t['rsi'] <= 30 else "正常")
        print(f"  {i:<4}{t['light']:<3}{nm}{t['close']:>8.1f}{t['chg']:>+7.1f}"
              f"{t['vr']:>6.2f}({vtag}){t['rsi']:>5.0f}({rtag})  {t['act']}")
    print("=" * 76)
    def label_n(name, t):
        n = t.get("n_checks")
        return f"{name}({n}/5{'強,可信' if n and n >= 4 else '弱,先觀察'})"

    downs = [label_n(r[1], r[2]) for r in rows if r[2]["light"] == "🔻" and r[2].get("strong") is not True]
    downs_wash = [label_n(r[1], r[2]) for r in rows if r[2]["light"] == "🔻" and r[2].get("strong") is True]
    dead = [r[1] for r in rows if r[2]["light"] == "🟠"]
    ups = [label_n(r[1], r[2]) for r in rows if r[2]["light"] == "🔺" and r[2].get("strong") is not False]
    ups_weak = [label_n(r[1], r[2]) for r in rows if r[2]["light"] == "🔺" and r[2].get("strong") is False]
    sus = [r[1] for r in rows if r[2]["light"] == "🔸"]
    coil = [r[1] for r in rows if r[2]["light"] == "🟡"]
    blow_distribution = [r[1] for r in rows if r[2].get("blowoff_type") == "distribution"]
    blow_consolidation = [(r[1], r[2].get("blowoff_level")) for r in rows if r[2].get("blowoff_type") == "consolidation"]
    blow_failed = [(r[1], r[2].get("blowoff_level")) for r in rows if r[2].get("blowoff_type") == "failed"]
    vol_divs = [r[1] for r in rows if r[2].get("vol_div")]
    if downs or downs_wash or ups or ups_weak:
        print("  ※上車/下車後面的(n/5)是過關分數：4/5以上才算扎實可信，可以照做；")
        print("    3/5是勉強過關、常常隔天就打臉，當「先觀察」就好，別急著跟單。")
    if downs: print(f"  🔻 下車(賣)：{'、'.join(downs)}")
    if downs_wash: print(f"  🛡️ 強勢股下車=多半回檔洗盤(別被洗掉,拉回是接點)：{'、'.join(downs_wash)}")
    if dead: print(f"  🟠 死水換股(卡資金,汰弱)：{'、'.join(dead)}")
    if ups: print(f"  🔺 上車(買·站上年線的強勢股)：{'、'.join(ups)}")
    if ups_weak: print(f"  ⚠ 技術轉強但破年線弱股(只能短搶,別買進/加碼)：{'、'.join(ups_weak)}")
    if coil: print(f"  🟡 量縮蓄勢(準備噴,留意)：{'、'.join(coil)}")
    if sus: print(f"  🔸 疑似(待確認)：{'、'.join(sus)}")
    if not (downs or downs_wash or dead or ups or ups_weak or coil or sus): print("  今天沒有訊號。")
    if blow_distribution:
        print(f"  💣 爆量黑K收低‧疑似出貨 →【先賣掉一部分鎖利】：{'、'.join(blow_distribution)}")
        print("     → 意思是：這檔已經漲了一大段時間才反轉，前幾天創新高，今天卻爆出將近2倍以上均量、")
        print("       收在當天最低點附近，代表有大戶在高點認真出貨，不是隨便賣賣。這個警訊比「跌破5日線」")
        print("       更早更準，通常提早1~2天示警。具體該做的事：現在就賣掉手上這檔的一部分(例如一半)先")
        print("       落袋，剩下的等真的跌破月線再全出，別等5日線才反應，會少賺一截。")
    if blow_consolidation:
        for name, lvl in blow_consolidation:
            print(f"  🔄 爆量黑K收低‧疑似換手 →【先別賣，每天檢查{lvl:.1f}元有沒有跌破】：{name}")
        print("     → 意思是：這是「剛」噴出/跳空的新鮮突破(不是漲很久了才反轉)，今天雖然爆量收黑，")
        print("       但股價還守在突破起漲點之上，比較像追高的人獲利了結、新買盤繼續接手的正常換手，")
        print("       不一定是壞事。具體該做的事：先不要賣，接下來每天收盤看一次上面那個價位，只要收盤")
        print("       沒跌破，就繼續抱著；哪天收盤真的跌破了，才是該賣的時候。")
    if blow_failed:
        for name, lvl in blow_failed:
            print(f"  ⚠️ 爆量黑K收低‧突破失敗 →【已跌破{lvl:.1f}元，先減碼】：{name}")
        print("     → 意思是：剛突破沒多久，但今天已經跌破突破起漲點了，代表這次突破沒站穩、買盤撐不住，")
        print("       比較像是假突破。具體該做的事：手上如果有留倉，先賣掉一部分減碼，不要因為「已經跌了」")
        print("       就想攤平加碼，這種假突破續跌的機率比較高。")
    if vol_divs:
        print(f"  📉 量縮上漲 →【先別賣，但要開始每天盯量】：{'、'.join(vol_divs)}")
        print("     → 意思是：這檔已經漲了一大段(20天內漲超過25%)，今天雖然還在漲，")
        print("       但買盤變少了(量縮)，代表願意追高的人越來越少，漲勢可能後繼無力。")
        print("       具體該做的事：現在還不用賣，但從明天開始每天看一次量比，如果之後出現「爆量黑K收低」")
        print("       或收盤跌破月線，那時候才是真的該收手、賣掉一部分的時機。")
    print("  RSI>70過熱、<30過冷；⚡背離=轉折前兆，要留意")
    print("-" * 76)
    print("  量比怎麼算：今日成交量 ÷ 最近20天平均成交量。")
    print("  ・量比≥1.5(放量)：今天成交量是平常的1.5倍以上，買賣特別踴躍，通常代表有消息面")
    print("    或資金在動，趨勢比較可信；漲要放量才是真的有人搶，跌要放量才是真的有人在殺。")
    print("  ・量比≤0.6(量縮)：今天不到平常的6成，交投清淡，觀望氣氛濃——漲或跌都缺乏動能，")
    print("    這種時候的漲跌比較不可信，容易一天反覆。")
    print("  ・量比0.6~1.5之間(量平)：正常交易量，沒有特別訊號。")
    if charted:
        print("-" * 76)
        print(f"  📊 已存K線圖到「{CHART_DIR}」資料夾，可以自己先看圖練習判斷：")
        for name, path in charted:
            print(f"     {name}：{os.path.basename(path)}")
        print("     看完想跟我核對妳的判斷，直接跟我說股票名稱就好。")


if __name__ == "__main__":
    main()
