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

def fetch_twse_data(date_str):
    """Phase 2: 暴力全收的抓取器 (無腦接收 JSON)"""
    twse_date = date_str.replace('-', '')
    url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={twse_date}&type=ALLBUT0999"
    
    try:
        # 防 Ban 機制
        time.sleep(random.uniform(3.5, 5.5))
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        # 避免 TWSE 偶爾回傳非 JSON 的錯誤網頁
        if 'application/json' not in res.headers.get('Content-Type', ''):
            print(f"\n[Warning] {date_str} 回傳非 JSON 格式 (可能被暫時阻擋或無資料)")
            return "error", None
            
        res_json = res.json()
        
        # TWSE 官方表示無資料的狀態
        if res_json.get('stat') != 'OK':
            return "no_data", None
            
        # 🌟 不管長怎樣，整包 JSON 直接回傳！
        return "success", res_json
        
    except Exception as e:
        print(f"\n[Error] {date_str} 抓取失敗: {e}")
        return "error", None

def main():
    conn = init_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT date FROM fetch_status WHERE status IN ('pending', 'error') ORDER BY date ASC")
    tasks = [row[0] for row in cursor.fetchall()]
    
    if not tasks:
        print("所有資料皆已抓取完畢！")
        return
        
    print(f"準備抓取 {len(tasks)} 天的資料...")
    
    # 計算連續錯誤次數，保護 IP
    consecutive_errors = 0 
    
    for date_str in tqdm(tasks):
        status, raw_json_data = fetch_twse_data(date_str)
        
        if status == "success" and raw_json_data is not None:
            # Phase 3: 落地為每日 JSON 暫存檔
            save_path = STAGING_DIR / f"{date_str.replace('-', '')}.json"
            
            # 將整包 API 回應寫入 JSON 檔
            with open(save_path, 'w', encoding='utf'
            '-8') as f:
                json.dump(raw_json_data, f, ensure_ascii=False)
                
            consecutive_errors = 0 # 成功就歸零
            
        elif status == "error":
            consecutive_errors += 1
            if consecutive_errors >= 5:
                print("\n[中斷] 遭遇連續 5 次錯誤，可能已被 TWSE 暫時封鎖。請稍後再重試。")
                break
                
        # 更新 SQLite 狀態
        cursor.execute("UPDATE fetch_status SET status = ? WHERE date = ?", (status, date_str))
        conn.commit()

if __name__ == "__main__":
    main()