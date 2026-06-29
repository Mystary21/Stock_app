# step1_fetcher.py
import sqlite3
import requests
import time
import random
import json
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
import urllib3

# TPEx SSL 憑證問題處理
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定常數
START_DATE = "2016-01-01"
END_DATE = datetime.today().strftime('%Y-%m-%d')
STAGING_DIR = Path("staging")
DB_PATH = "task_status.db"



def init_db():
    """Phase 1: 初始化任務清單與狀態管理 (SQLite)"""
    # 確保暫存資料夾存在
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fetch_status (
            date TEXT PRIMARY KEY,
            status TEXT
        )
    ''')
    
    # 產生過去 10 年的平日 (剔除六日)
    dates = pd.bdate_range(start=START_DATE, end=END_DATE).strftime('%Y-%m-%d').tolist()
    
    for d in dates:
        cursor.execute("INSERT OR IGNORE INTO fetch_status (date, status) VALUES (?, 'pending')", (d,))
    
    conn.commit()
    return conn

def fetch_with_retry(url, max_retries=5, base_delay=3, backoff=2, max_delay=30,
                     headers=None, timeout=10):
    """
    帶指數退避重試的 HTTP 請求。

    Args:
        url: 請求 URL
        max_retries: 最大重試次數
        base_delay: 基礎等待秒數
        backoff: 每次重試的倍數
        max_delay: 最大等待秒數
        headers: HTTP headers
        timeout: 請求超時秒數

    Returns:
        (response, status) tuple
    """
    for attempt in range(max_retries + 1):
        try:
            if headers is None:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            res = requests.get(url, headers=headers, timeout=timeout)
            return res, res.status_code
        except Exception as e:
            if attempt == max_retries:
                print(f"[Error] 請求 {url[:60]}... 失敗 ({e})")
                return None, -1
            wait = min(base_delay * (backoff ** attempt), max_delay)
            print(f"[Retry {attempt+1}/{max_retries}] 等待 {wait} 秒後重試...")
            time.sleep(wait)

    return None, -1


def fetch_twse_data(date_str):
    """從 TWSE 抓取上市股票資料（帶指數退避重試）"""
    twse_date = date_str.replace('-', '')
    url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={twse_date}&type=ALLBUT0999"

    res, status_code = fetch_with_retry(url, max_retries=5, base_delay=3, backoff=2,
                                        timeout=30)
    if res is None:
        return "error", None

    if status_code != 200:
        print(f"\n[Error] {date_str} TWSE 回傳 HTTP {status_code}")
        return "error", None

    if 'application/json' not in res.headers.get('Content-Type', ''):
        print(f"\n[Warning] {date_str} TWSE 回傳非 JSON 格式")
        return "no_data", None

    try:
        res_json = res.json()
    except Exception:
        return "error", None

    if res_json.get('stat') != 'OK':
        return "no_data", None

    return "success", res_json

def fetch_tpex_data(date_str, max_retries=5, base_delay=3, backoff=2, max_delay=30):
    """
    從 TPEx (櫃買中心) 抓取上櫃股票資料（帶指數退避重試）。
    TPEx API 以「日」為回傳單位 (tables 陣列)，直接抓取指定日期即可。
    回傳格式與 TWSE 相容 (fields9/data9)。

    Args:
        date_str: 日期字串 YYYY-MM-DD
        max_retries: 最大重試次數
        base_delay: 基礎等待秒數
        backoff: 每次重試的倍數
        max_delay: 最大等待秒數
    """
    twse_date = date_str.replace('-', '')
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    url = (f"https://www.tpex.org.tw/web/stock/aftertrading/"
           f"daily_close_quotes/stk_quote_result.php"
           f"?l=zh-tw&d={dt.year}/{dt.month:02d}/{dt.day:02d}&stk=ALL&s=0,asc,1")

    res, status_code = fetch_with_retry(url, max_retries=max_retries, base_delay=base_delay,
                                        backoff=backoff, max_delay=max_delay, timeout=30)
    if res is None or status_code != 200:
        return "error", None

    if 'application/json' not in res.headers.get('Content-Type', ''):
        return "no_data", None

    try:
        raw = res.json()
    except Exception:
        return "error", None

    if str(raw.get('stat', '')).lower() != 'ok':
        return "no_data", None

    # TPEx 回傳格式: { tables: [{ fields, data, ... }] }
    tables = raw.get('tables', [])
    if not tables:
        return "no_data", None

    # 找第一個有 代號/名稱 欄位的 table
    for tbl in tables:
        raw_fields = [str(c).strip() for c in tbl.get('fields', [])]
        if not any('代號' in f for f in raw_fields):
            continue
        all_rows = tbl.get('data', [])
        if not all_rows:
            continue

        # 建立欄位對應: TPEx 原生欄位 → 標準欄位
        remap = {
            '代號': '證券代號', '名稱': '證券名稱',
            '收盤': '收盤價', '開盤': '開盤價',
            '最高': '最高價', '最低': '最低價',
            '漲跌': '漲跌價差',  # TPEx 的漲跌是帶正負號的文字
            '成交股數': '成交股數', '成交金額(元)': '成交金額',
            '成交金額': '成交金額', '成交筆數': '成交筆數',
            '本益比': '本益比',
        }
        mapped_fields = []
        for f in raw_fields:
            mapped = next((v for k, v in remap.items() if k in f), f)
            if mapped not in mapped_fields:  # 去除重複 (如兩個開盤)
                mapped_fields.append(mapped)

        result = {'fields9': mapped_fields, 'data9': all_rows}
        return "success", result

    return "no_data", None

def backfill_otc(recent_days: int = 0, sleep_range=(3.5, 5.5), min_year: int = 0):
    """
    針對已有 TWSE JSON 但缺少 OTC JSON 的日期，補抓上櫃資料。

    Args:
        recent_days: 只補最近 N 天 (預設 0 = 全部補齊)
        sleep_range: API 呼叫前等待的秒數範圍
        min_year: 最小年份 (例: 2016 = 只補 2016 年以後的資料)
    """
    existing_twse = {f.stem for f in STAGING_DIR.glob("[0-9]*.json")}
    existing_otc  = {f.stem.replace('OTC_', '') for f in STAGING_DIR.glob("OTC_*.json")}
    missing = sorted(existing_twse - existing_otc)

    if not missing:
        print("所有 OTC 資料已齊全，無需補抓。")
        return

    # 過濾年份
    if min_year > 0:
        missing = [d for d in missing if len(d) == 8 and int(d[:4]) >= min_year]
        print(f"過濾年份 >= {min_year} 後，剩 {len(missing)} 天待補")

    if recent_days > 0:
        missing = missing[-recent_days:]
        print(f"需補抓 {len(missing)} 天 (最近 {recent_days} 天) 的 OTC 資料...")
    else:
        print(f"需補抓 {len(missing)} 天的 OTC 資料 (全部補齊)...")

    remap = {
        '代號': '證券代號', '名稱': '證券名稱',
        '收盤': '收盤價', '開盤': '開盤價',
        '最高': '最高價', '最低': '最低價',
        '漲跌': '漲跌價差',
        '成交股數': '成交股數', '成交金額(元)': '成交金額',
        '成交金額': '成交金額', '成交筆數': '成交筆數',
        '本益比': '本益比',
    }
    fetched = 0

    for raw_date in tqdm(missing, desc="補抓 OTC"):
        date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        status, data = fetch_tpex_data(date_str)
        if status == "success" and data is not None:
            with open(STAGING_DIR / f"OTC_{raw_date}.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            fetched += 1

    print(f"OTC 補抓完成，新增 {fetched} 天。")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TWSE + TPEx 股票資料抓取器")
    parser.add_argument("--otc-backfill", action="store_true", help="補抓最近 120 天的 OTC 資料")
    parser.add_argument("--otc-backfill-all", action="store_true", help="補抓全部歷史 OTC 資料")
    args, _ = parser.parse_known_args()

    if args.otc_backfill_all:
        backfill_otc(recent_days=0, sleep_range=(1.5, 2.5), min_year=2016)
        return
    if args.otc_backfill:
        backfill_otc(recent_days=120)
        return

    conn = init_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT date FROM fetch_status WHERE status IN ('pending', 'error') ORDER BY date ASC")
    tasks = [row[0] for row in cursor.fetchall()]
    
    if not tasks:
        print("所有 TWSE 資料皆已抓取完畢。若需補 OTC，請執行: python step1_fetcher.py --otc-backfill")
        # 仍嘗試補 OTC
        backfill_otc()
        return
        
    print(f"準備抓取 {len(tasks)} 天的資料（上市 + 上櫃）...")

    for date_str in tqdm(tasks):
        # ── 1. 上市 ──
        twse_status, twse_json = fetch_twse_data(date_str)
        if twse_status == "success" and twse_json is not None:
            save_path = STAGING_DIR / f"{date_str.replace('-', '')}.json"
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(twse_json, f, ensure_ascii=False)
        elif twse_status == "error":
            print(f"\n[!] {date_str} TWSE 抓取最終失敗")

        # ── 2. 上櫃 (TPEx) ──
        otc_status, otc_json = fetch_tpex_data(date_str)
        if otc_status == "success" and otc_json is not None:
            otc_path = STAGING_DIR / f"OTC_{date_str.replace('-', '')}.json"
            with open(otc_path, 'w', encoding='utf-8') as f:
                json.dump(otc_json, f, ensure_ascii=False)

        final_status = "success" if twse_status == "success" else twse_status
        cursor.execute("UPDATE fetch_status SET status = ? WHERE date = ?", (final_status, date_str))
        conn.commit()


if __name__ == "__main__":
    main()