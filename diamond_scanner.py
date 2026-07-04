# -*- coding: utf-8 -*-
"""
真鑽石篩選器 —— 只挑「就算沒人炒也站得住」的真貨。
把觀察名單每一檔分成：真鑽石(可長抱) / 老鑽石熄火(中長線) / 鍍金石頭(只能短線) / 石頭(避開)，
每一檔都用白話寫清楚為什麼，不是丟一堆數字讓你自己猜。
"""
import os
import sys
import json
import time
from datetime import datetime
# 本檔就在 TODOLIST 內，diamond_filter 與清單都在同一層，直接讀
from diamond_filter import analyze_diamond, metrics_line

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 全系統共用同一張清單(同層)
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watch_list.json")


def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def run():
    watchlist = load_watchlist()
    if not watchlist:
        print("觀察名單為空。")
        return

    print("--- 💎 真鑽石篩選器 (分清真鑽石 vs 鍍金石頭) ---")
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("（要抓基本面，每檔慢幾秒，請稍等）")
    print("=" * 74)

    buckets = {"💎 真鑽石": [], "🔄 復甦股(拉回撿波段)": [], "🔶 估值透支(轉機·別重壓)": [],
               "🟡 老鑽石(成長熄火)": [], "🔴 鍍金石頭(賠錢被炒·只能短線)": [],
               "⚫ 石頭(避開)": [], "資料不足": []}

    for item in watchlist:
        r = analyze_diamond(item['symbol'], item['name'])
        print(f"  ...{item['name']} ({item['symbol']}) → {r['grade']}")
        g = r['grade']
        if "真鑽石" in g:
            buckets["💎 真鑽石"].append(r)
        elif "復甦" in g:
            buckets["🔄 復甦股(拉回撿波段)"].append(r)
        elif "估值透支" in g:
            buckets["🔶 估值透支(轉機·別重壓)"].append(r)
        elif "老鑽石" in g:
            buckets["🟡 老鑽石(成長熄火)"].append(r)
        elif "鍍金" in g:
            buckets["🔴 鍍金石頭(賠錢被炒·只能短線)"].append(r)
        elif "石頭" in g:
            buckets["⚫ 石頭(避開)"].append(r)
        else:
            buckets["資料不足"].append(r)
        time.sleep(0.3)

    print("\n" + "=" * 74)
    print("📋 分級結果")
    print("=" * 74)

    order = ["💎 真鑽石", "🔄 復甦股(拉回撿波段)", "🔶 估值透支(轉機·別重壓)",
             "🟡 老鑽石(成長熄火)", "🔴 鍍金石頭(賠錢被炒·只能短線)", "⚫ 石頭(避開)", "資料不足"]
    action = {
        "💎 真鑽石": "→ 這才是可以長抱的核心，回檔就是撿貨機會。",
        "🔄 復甦股(拉回撿波段)": "→ 有賺錢、谷底翻上來的景氣循環股，『拉回』才撿(賺波段/殖利率)，追高別追、也別當真鑽石長抱。",
        "🔶 估值透支(轉機·別重壓)": "→ 有賺錢但股價跑在過去財報前面，市場在賭未來(轉單/新廠/復甦)。查故事是真是假，拉回分批、別追高重壓。",
        "🟡 老鑽石(成長熄火)": "→ 體質好但不會噴，中長線可、別重壓。",
        "🔴 鍍金石頭(賠錢被炒·只能短線)": "→ 公司在賠錢、純靠題材炒，量退就崩，只能短線快進快出，千萬別長抱套牢。",
        "⚫ 石頭(避開)": "→ 沒有值得碰的理由，直接跳過。",
        "資料不足": "→ 抓不到基本面，先擱著。",
    }

    for grade in order:
        rows = buckets[grade]
        if not rows:
            continue
        print(f"\n【{grade}】  {action[grade]}")
        print("-" * 74)
        for r in rows:
            print(f"  {r['name']} ({r['symbol']})")
            print(f"     {r['reason']}")
            print(f"     {metrics_line(r)}")

    print("\n" + "=" * 74)
    n_true = len(buckets["💎 真鑽石"])
    if n_true:
        names = "、".join(r['name'] for r in buckets["💎 真鑽石"])
        print(f"✅ 名單裡真正的鑽石只有 {n_true} 檔：{names}")
        print("   其他的漲得再兇也是鍍金/熄火，別被騙進去長抱。")
    else:
        print("🟢 名單裡目前沒有一檔是真鑽石。強勢的多半是被炒的，長抱要小心。")
    print("=" * 74)


if __name__ == "__main__":
    run()
    input("\n分析完成，按 Enter 鍵關閉視窗...")
