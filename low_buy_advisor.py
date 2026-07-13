# -*- coding: utf-8 -*-
"""
精密低接決策輔助系統 (Low-Buy Advisor)
------------------------------------------------------------
用途：針對核心與潛力股，從各股 level 檔中抓取最新市價與均線判定，
      以「防守優先、絕不亂接」為原則，輸出清晰的低接紅綠燈與決策說明。
"""
import sys
import os
import io
import contextlib

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import json
import levels_watch

# 載入當前觀察名單中的 active symbols
def load_watchlist():
    watchlist_path = os.path.join(HERE, "watch_list.json")
    if not os.path.exists(watchlist_path):
        watchlist_path = os.path.join(HERE, "..", "watch_list.json")
    try:
        if os.path.exists(watchlist_path):
            with open(watchlist_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"讀取 watch_list.json 失敗: {e}")
    return []

watchlist = load_watchlist()
active_symbols = {item["symbol"]: item.get("name", "") for item in watchlist if "symbol" in item}

# 從 levels_watch 中的 MODS 清單過濾出觀察名單中的股票
MODS = []
for mod in levels_watch.MODS:
    symbol = getattr(mod, "SYMBOL", None)
    if symbol in active_symbols:
        name = getattr(mod, "NAME", active_symbols[symbol])
        MODS.append((name, mod))

def analyze_low_buy(name, mod):
    # 捕獲模組的資料與判斷
    try:
        if name == "台達電":
            price, ma60 = mod.get_price()[:2]
            # 強制讀取加碼判斷 (不論是否已加滿)
            verdict = mod.judge_not_added(price)
            ma20 = None
        else:
            data_vals = None
            if hasattr(mod, "get_data"):
                data_vals = mod.get_data()
            elif hasattr(mod, "get_price_and_volume"):
                data_vals = mod.get_price_and_volume()

            if data_vals is not None:
                # 動態解包參數呼叫 judge
                verdict = mod.judge(*data_vals)
                
                # 依位置提取顯示值
                price = data_vals[0] if len(data_vals) > 0 else None
                ma20 = None
                ma60 = None
                if name in ["緯穎", "銳澤", "緯創"]:
                    pass
                else:
                    ma20 = data_vals[1] if len(data_vals) > 1 else None
                    ma60 = data_vals[2] if len(data_vals) > 2 else None
            else:
                # 備用方案：執行 run() 並擷取 stdout
                if hasattr(mod, "run"):
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        try:
                            mod.run()
                        except Exception as run_err:
                            print(f"執行出錯: {run_err}")
                    output_text = buf.getvalue().strip()
                    lines = [ln.strip() for ln in output_text.split("\n") if ln.strip()]
                    if lines:
                        price = None
                        for ln in lines:
                            if "現價" in ln:
                                try:
                                    parts = ln.split("現價")
                                    price = float(parts[1].split()[0])
                                except Exception:
                                    pass
                            elif "市價" in ln:
                                try:
                                    parts = ln.split("市價")
                                    price_str = parts[1].replace("：", "").strip().split()[0]
                                    price = float(price_str)
                                except Exception:
                                    pass
                        # 抓真正的判斷句(以訊號表情符號開頭那行)，不是盲目抓最後一行——
                        # 最後一行常是「備忘」註解，不是判斷結果(2026-07-13踩過先進光這個坑)。
                        VERDICT_EMOJI = ("⚪", "⚠️", "🟡", "🔴", "🟢", "⛔", "🚀", "🟩", "⏸")
                        verdict_lines = [ln for ln in lines if ln.startswith(VERDICT_EMOJI)]
                        verdict = verdict_lines[-1] if verdict_lines else lines[-1]
                        ma20, ma60 = None, None
                    else:
                        price, ma20, ma60 = None, None, None
                        verdict = "無法取得執行輸出"
                else:
                    price, ma20, ma60 = None, None, None
                    verdict = "無法取得資料"
    except Exception as e:
        return {
            "name": name,
            "status": "❓ 異常",
            "price": 0,
            "ma20": 0,
            "ma60": 0,
            "desc": f"資料讀取失敗: {e}",
            "color": "yellow"
        }

    # 決策引擎分類
    status = "⚪ 區間觀望"
    desc = verdict
    color = "white"

    # 1. 偵測暫緩/停止接刀詞彙
    stop_keywords = ["別接", "暫緩", "別接刀", "不宜攤平", "停止加碼", "別追加", "別攤", "縮手", "避開", "別搶", "別追"]
    buy_keywords = ["分批撿", "小量試接", "可以小量", "撿多一點", "撿貨區", "低撿", "買進區", "加碼點", "試接回", "靠近20日線"]

    if any(kw in verdict for kw in stop_keywords) or "⛔" in verdict or "⚠️" in verdict:
        status = "⏸ 暫緩接刀"
        color = "yellow"
    # 2. 偵測過熱不追
    elif "🔴" in verdict or "過熱" in verdict:
        status = "🔴 過熱不追"
        color = "red"
    # 3. 偵測低接區
    elif any(kw in verdict for kw in buy_keywords) or "🟢" in verdict:
        status = "🟢 進入低接"
        color = "green"
    
    # 4. 針對空手股的特別提示
    if "空手" in verdict and status == "⚪ 區間觀望":
        status = "⚪ 空手觀望"
        color = "white"

    return {
        "name": name,
        "status": status,
        "price": price,
        "ma20": ma20,
        "ma60": ma60,
        "desc": desc,
        "color": color
    }

def print_report():
    print("=" * 80)
    print("   🛡️  精 密 低 接 決 策 輔 助 報 告 (盤 後 掃 描)  🛡️")
    print("=" * 80)
    print(f" 掃描時間：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(" 核心原則：只接『確認止跌』或『打底支撐』，絕不在半山腰接墜落的刀子。")
    print("-" * 80)
    print(f"{'股票名稱':<10}{'決策狀態':<12}{'當前市價':<10}{'20日線':<10}{'決策白話說明':<35}")
    print("-" * 80)

    for name, mod in MODS:
        res = analyze_low_buy(name, mod)
        p_str = f"{res['price']:.1f}" if res['price'] else "--"
        m20_str = f"{res['ma20']:.1f}" if res['ma20'] else "--"
        
        # 截短說明以便排版
        desc_clean = res['desc'].split("—")[-1].strip() if "—" in res['desc'] else res['desc']
        if len(desc_clean) > 35:
            desc_clean = desc_clean[:33] + ".."
            
        print(f"{res['name']:<10}{res['status']:<12}{p_str:<10}{m20_str:<10}{desc_clean:<35}")
    
    print("=" * 80)
    print(" 💡 決策燈號說明：")
    print("   🟢 [進入低接]：已落入預設支撐區，且跌勢收斂，可分批佈局。")
    print("   ⏸ [暫緩接刀]：雖在跌，但下殺力道強、跌破關鍵防守，不可加碼/攤平！")
    print("   🔴 [過熱不追]：股價漲多乖離大，不可追高，耐心等回檔。")
    print("   ⚪ [區間/空手]：無明確低吸訊號，冷眼旁觀即可。")
    print("=" * 80)

if __name__ == "__main__":
    print_report()
