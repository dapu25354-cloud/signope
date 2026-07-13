"""
股性掃描 —— 每檔股票該用哪種打法，一次看清楚
------------------------------------------------------------
不是技術指標，是「這檔股票的個性」：趨勢股別來回做、震盪股高賣低撿、
定存股別看動能、題材股別重壓。分類是她跟Claude討論定案的，不是算出來的，
改分類/加新股直接改下面 CHARACTER 這個字典就好。
"""
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CATEGORY_ORDER = ["trend", "range", "dividend", "theme", "weak", "special"]
CATEGORY_INFO = {
    "trend":     ("🚀 趨勢型", "一動就是一大段，順勢抱、別來回做、別漲一段就想跑"),
    "range":     ("🔁 震盪/箱型型", "核心不動+機動倉高賣低撿，貼近高點賣機動、拉回撿回"),
    "dividend":  ("💰 定存/領息型", "看殖利率跟成本，不看短期動能，別用波段尺去評"),
    "theme":     ("🎲 高波動題材觀察股", "高基期高波動，等拉回不過熱才小量試單、別重壓"),
    "weak":      ("🥶 弱勢/換股候選", "動能最弱這一批，放著別加碼，突破或站回關鍵均線才重新評估"),
    "special":   ("⚠️ 特殊/不適用一般判斷", "另一本帳、或不適用公司體質判斷法，別套一般規則"),
}

# (代號, 名字): (分類, 一句話打法)
CHARACTER = {
    "2330.TW": ("trend", "權值龍頭，抱著讓它衝、不用盯，RSI≥75才小賣"),
    "2308.TW": ("trend", "長線核心，分批接、別設緊停損"),
    "6669.TW": ("trend", "飆股大贏家，核心抱、弱才小量接、別追高別大攤"),
    "3211.TWO": ("trend", "順勢持有，RSI≥70貼高才賣強，20MA上抱、別手癢"),
    "2618.TW": ("trend", "景氣循環復甦股，拉回才撿，別追高、別當長抱波段，順勢抱不要來回做"),

    "2885.TW": ("range", "金控組，貼近季高賣機動、拉回20MA撿回"),
    "2891.TW": ("range", "金控組，貼近季高賣機動、拉回20MA撿回"),
    "3231.TW": ("range", "箱型整理，核心不動、只用機動倉來回做"),
    "5347.TWO": ("range", "核心不動+機動倉高賣低撿，她最熟練的範本"),

    "2889.TW": ("dividend", "抱20年的定存股，別用波段尺去評"),

    "3450.TW": ("theme", "CPO矽光子題材股，高基期高波動，小量試單、別重壓"),
    "3363.TWO": ("theme", "CPO矽光子題材股，高基期高波動，小量試單、別重壓"),
    "4979.TWO": ("theme", "CPO矽光子題材股，高基期高波動，小量試單、別重壓"),

    "2002.TW": ("weak", "傳產牛皮悶股，放著別期待大漲，換股候選"),
    "6561.TWO": ("weak", "好公司(IDC/ROE高)但跌破年線修正中，汰弱換強第一順位，別攤平"),
    "7703.TWO": ("weak", "全帳動能最弱，換股候選"),
    "9904.TW": ("weak", "跌破年線，觀察就好，先別碰"),
    "9907.TW": ("weak", "跌破年線，觀察就好，先別碰"),
    "3362.TWO": ("weak", "空手(起漲前弱勢時出清、之後沒買回，以前一直有庫存)：公司現在賠錢(EPS負)，只能短打快進快出，絕不長抱、別接刀"),
    "6830.TW": ("weak", "賠錢被炒，只能短打快進快出，絕不長抱"),
    "1527.TW": ("weak", "復甦股但動能弱，換股候選"),

    "2887.TW": ("special", "老公的另一本帳，不用波段邏輯評"),
    "3008.TW": ("special", "貼近前高才算過熱(看RSI別只看單日漲幅)，過熱貼高賣強別追加、核心抱；漲太快留意「衝高遇壓」(創高當天長上影線+爆量)"),
    "4551.TW": ("special", "2026/07/13已零股買回20股@220(持有中，不是空手等接回)：買在跌破月線處，先守紀律別加碼，跌破季線才出場；之前噴過頭的老毛病是「別追高」，現在的功課是「別攤平」，性質不同別搞混"),
    "0050.TW": ("special", "大盤ETF，不適用「公司賺不賺錢」這套判斷法(它沒有ROE可言)"),

    "2395.TW": ("trend", "溫和健康多頭，順勢抱、拉回20MA小撿"),
    "3551.TWO": ("trend", "溫和健康多頭，順勢抱、拉回20MA小撿"),
    "2382.TW": ("trend", "AI伺服器供應鏈，目前空手(之前被洗掉、還沒買回)：等站回月線/帶量突破再考慮接回，別接刀"),
    "3711.TW": ("trend", "題材+基本面都有，但目前空手觀察中(不是抱著)：拉回不過熱可小量試單、設停損，別當成已經在抱"),
    "6640.TWO": ("special", "曾大幅修正中重新接回，目前築底階段，守停止加碼線、站回月線才算止跌"),
    "2912.TW": ("range", "零售景氣循環復甦股，較穩定，拉回撿波段"),
}


def get_price(symbol):
    try:
        import yfinance as yf
        tk = yf.Ticker(symbol)
        info = tk.info
        p = info.get('regularMarketPrice') or info.get('currentPrice')
        return float(p) if p else None
    except Exception:
        return None


def main():
    import json
    with open(os.path.join(HERE, "watch_list.json"), encoding="utf-8") as f:
        items = json.load(f)
    name_of = {it["symbol"]: it["name"] for it in items}

    print("=" * 70)
    print("  股性掃描 —— 每檔該用哪種打法")
    print("=" * 70)

    for cat in CATEGORY_ORDER:
        members = [(sym, note) for sym, (c, note) in CHARACTER.items() if c == cat and sym in name_of]
        if not members:
            continue
        title, desc = CATEGORY_INFO[cat]
        print(f"\n{title}：{desc}")
        print("-" * 70)
        for sym, note in members:
            name = name_of.get(sym, sym)
            price = get_price(sym)
            price_str = f"{price:.1f}" if price else "?"
            print(f"  {name}({sym.split('.')[0]}) 現價{price_str}：{note}")

    covered = set(CHARACTER.keys())
    missing = [it["name"] for it in items if it["symbol"] not in covered]
    if missing:
        print("\n" + "-" * 70)
        print(f"  ❓ 還沒分類的：{'、'.join(missing)}（跟Claude聊一下補上）")


if __name__ == "__main__":
    main()
