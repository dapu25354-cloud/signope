# -*- coding: utf-8 -*-
"""
真鑽石判斷核心（三支獵人 + 真鑽石篩選器共用同一套定義）。

分級邏輯：光靠「季線上揚」會把賠錢股/被炒的當鑽石，所以改用基本面 + 年線：
  真鑽石     = 有賺錢(ROE正) + 有成長 + 站上年線且年線上揚 → 沒人炒也站得住，可長抱
  老鑽石熄火 = 有賺錢 + 長線也好，但成長停了 → 中長線可抱、動能弱
  鍍金石頭   = 賠錢卻在漲、或基本面撐不起漲幅(離年線太遠) → 只能短線，別長抱
  石頭       = 賠錢又沒結構、或長線還沒過關 → 避開

對外主要欄位：
  grade        中文分級
  is_true      是否真鑽石(獵人的鑽石閘門用這個)
  fund_ok      基本面是否過關(恐慌接刀用：崩盤時價會摜破年線，只看體質)
  short_only   是否只能短線(鍍金)
  reason       一句白話說明為什麼
"""
import yfinance as yf
import pandas as pd


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _pct(x):
    return f"{x*100:.0f}%" if isinstance(x, (int, float)) else "--"


def analyze_diamond(symbol, name=""):
    t = yf.Ticker(symbol)
    try:
        info = t.info
    except Exception:
        info = {}

    roe = _num(info.get('returnOnEquity'))
    pm = _num(info.get('profitMargins'))
    eps = _num(info.get('trailingEps'))
    fwd_eps = _num(info.get('forwardEps'))  # 分析師預估的未來EPS，抓轉折點用
    eg = _num(info.get('earningsGrowth'))
    if eg is None:
        eg = _num(info.get('earningsQuarterlyGrowth'))
    rg = _num(info.get('revenueGrowth'))

    try:
        df = t.history(period="2y")
    except Exception:
        df = pd.DataFrame()

    if df.empty or len(df) < 60:
        return {"symbol": symbol, "name": name, "grade": "資料不足", "is_true": False,
                "fund_ok": False, "short_only": False,
                "reason": "抓不到足夠的基本面/歷史資料，無法判斷，保守當非鑽石。",
                "metrics": {"roe": roe, "pm": pm, "eps": eps, "eg": eg, "rg": rg,
                            "year_ma": None, "bias_year": None}}

    # 盤中抓的話今天這根K棒收盤價還沒定案、yfinance常給NaN，
    # NaN混進rolling窗口會讓整條年線變NaN、誤判成「跌破年線」，所以先丟掉NaN。
    close = df['Close'].dropna()
    ma240 = close.rolling(240).mean()
    price = float(close.iloc[-1])
    has_year = not pd.isna(ma240.iloc[-1])
    year_ma = float(ma240.iloc[-1]) if has_year else None
    year_rising = has_year and len(ma240) > 61 and float(ma240.iloc[-1]) > float(ma240.iloc[-61])
    above_year = has_year and price > year_ma
    bias_year = (price - year_ma) / year_ma * 100 if has_year else None

    # 基本面判定
    # 未來EPS明顯高於過去 = 分析師看它成長(循環股/轉機股在谷底時，過去財報最難看，靠這個救)
    fwd_growing = bool(fwd_eps is not None and eps is not None and eps > 0 and fwd_eps > eps * 1.05)
    profitable = (eps is not None and eps > 0) or (roe is not None and roe > 0 and (pm is None or pm > 0))
    # 高品質：ROE高 或 毛利率高(高毛利龍頭常現金多、ROE不靠槓桿而偏低，別只看ROE誤殺)
    high_quality = (roe is not None and roe >= 0.12) or (pm is not None and pm >= 0.20)
    growing = (eg is not None and eg > 0) or (rg is not None and rg > 0) or fwd_growing
    declining = (eg is not None and eg < 0) and (rg is not None and rg <= 0) and not fwd_growing
    # 炒過頭：離年線太遠(+40%以上) 而且 不是高品質公司。高毛利/高ROE龍頭就算漲多也不算炒
    hyped = (bias_year is not None and bias_year > 40) and not high_quality

    long_ok = bool(above_year and year_rising)
    fund_ok = bool(profitable and not declining)

    metrics = {"roe": roe, "pm": pm, "eps": eps, "eg": eg, "rg": rg,
               "year_ma": year_ma, "above_year": above_year,
               "year_rising": year_rising, "bias_year": bias_year}

    if not profitable:
        if long_ok:
            grade, is_true, short_only = "🔴 鍍金石頭(賠錢被炒)", False, True
            reason = "公司根本在賠錢，股價全靠題材炒上來——量退就打回原形，最多短線快進快出，絕不長抱。"
        else:
            grade, is_true, short_only = "⚫ 石頭(避開)", False, False
            reason = "又賠錢、長多結構也沒有，沒有值得碰的理由，避開。"
    elif not above_year:
        grade, is_true, short_only = "⚫ 石頭(跌破年線)", False, False
        reason = "雖然有賺錢，但股價還在年線之下，長多還沒站上來，先別碰、等站上年線再說。"
    elif not year_rising:
        # 站上年線、但年線還在下彎 = 從谷底剛翻上來的復甦股(常見於景氣循環股)
        if growing and not declining:
            grade, is_true, short_only = "🔄 復甦股(景氣循環·等年線翻正)", False, False
            reason = "有賺錢、也站上年線了，但年線還在下彎(前一波跌勢剛翻上來)——屬谷底復甦股，適合『拉回』撿波段/賺殖利率，還不是能無腦長抱的真鑽石，追高別追。"
        else:
            grade, is_true, short_only = "⚫ 石頭(長線未確認)", False, False
            reason = "有賺錢，但年線還在下彎、成長也沒跟上，長多趨勢沒確認，先別當鑽石、等站穩。"
    elif hyped:
        # 注意：這裡的公司「有在賺錢」(賠錢的前面就擋掉了)，只是股價跑在過去財報前面。
        # 循環股/轉機股在谷底時過去EPS最難看，但股價已在反映未來復甦——不能跟賠錢鍍金混為一談。
        grade, is_true, short_only = "🔶 估值透支(靠預期·別重壓)", False, False
        reason = (f"公司有在賺錢，但股價離年線+{bias_year:.0f}%、跑在過去財報前面(ROE {_pct(roe)})"
                  f"——市場在反映未來預期(轉單/新廠/景氣復甦)。是真轉機還是純想像，要查故事；"
                  f"拉回分批、別追高重壓，也別當無腦長抱的真鑽石。")
    elif declining or not growing:
        grade, is_true, short_only = "🟡 老鑽石(成長熄火)", False, False
        reason = "公司體質好但成長停了(EPS沒成長)，可以中長線抱、但別期待噴出，動能偏弱。"
    else:
        grade, is_true, short_only = "💎 真鑽石", True, False
        reason = f"有賺錢(ROE {_pct(roe)})、營收獲利有成長、年線一路墊高——就算沒人炒也站得住，可長抱的真貨。"

    return {"symbol": symbol, "name": name, "grade": grade, "is_true": is_true,
            "fund_ok": fund_ok, "short_only": short_only, "reason": reason, "metrics": metrics}


def metrics_line(r):
    """把基本面數字排成一行給人看。"""
    m = r["metrics"]
    bias = f"{m['bias_year']:+.0f}%" if m['bias_year'] is not None else "--"
    yline = f"年線{m['year_ma']:.0f}({'站上' if m['above_year'] else '跌破'}{'↑' if m['year_rising'] else '↓'})" if m['year_ma'] else "年線不足"
    return (f"ROE{_pct(m['roe'])} 淨利率{_pct(m['pm'])} 營收增{_pct(m['rg'])} EPS增{_pct(m['eg'])} "
            f"| 離年線{bias} | {yline}")
