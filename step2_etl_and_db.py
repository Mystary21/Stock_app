# step2_etl_and_db.py
import json
import sqlite3
import pandas as pd
import re
from pathlib import Path
from tqdm import tqdm


# 設定路徑
STAGING_DIR = Path("staging")
PARQUET_DIR = Path("parquet_data")
DB_PATH = "stock_warehouse.db"

# 確保輸出資料夾存在
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

def clean_and_transform(df, date_str):
    """資料清洗與轉換核心邏輯"""
    # 1. 補上日期欄位
    df['日期'] = date_str
    
    # 2. 清理 HTML 標籤萃取漲跌符號
    # 說明：將 <p style= color:red>+</p> 變成 +。如果是 X (表示平盤) 或是空白，則替換為空字串
    if '漲跌(+/-)' in df.columns:
        df['漲跌(+/-)'] = df['漲跌(+/-)'].astype(str).str.replace(r'<[^>]+>', '', regex=True).str.strip()
        df['漲跌(+/-)'] = df['漲跌(+/-)'].replace({'X': '', ' ': ''})
    else:
        df['漲跌(+/-)'] = ''

    # 3. 合併正負號與價差
    if '漲跌價差' in df.columns:
        # 去除原始價差可能的逗號與空白
        price_diff = df['漲跌價差'].astype(str).str.replace(',', '').str.strip()
        # 組合出例如 "+1.50" 或 "-0.50"
        combined_change = df['漲跌(+/-)'] + price_diff
        df['漲跌'] = pd.to_numeric(combined_change, errors='coerce').fillna(0.0)
    else:
        df['漲跌'] = 0.0

    # 4. 清洗數值欄位並轉型
    numeric_cols = ['成交股數', '成交筆數', '成交金額', '開盤價', '最高價', '最低價', '收盤價', '本益比']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.strip(), errors='coerce')

    # 5. 篩選我們最終需要的 11 個欄位 (注意：我們同時把證券名稱留著，稍後要塞進 SQLite，存 Parquet 時會丟掉)
    target_columns = [
        '日期', '證券代號', '證券名稱', '成交股數', '成交筆數', '成交金額', 
        '開盤價', '最高價', '最低價', '收盤價', '漲跌', '本益比'
    ]
    
    # 確保欄位存在，若不存在則補上空值
    for col in target_columns:
        if col not in df.columns:
            df[col] = None
            
    return df[target_columns]

def init_sqlite_schema(latest_companies_df):
    """建置關聯式資料庫 (Star Schema)"""
    print("\n[DB] 正在初始化 SQLite 資料庫與維度表...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Company_Dim (股票總覽表)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Company_Dim (
            證券代號 TEXT PRIMARY KEY,
            證券名稱 TEXT,
            產業類別 TEXT,
            狀態 TEXT DEFAULT '上市',
            更新時間 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Tag_Dim (標籤表)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Tag_Dim (
            Tag_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Tag_Name TEXT UNIQUE
        )
    ''')

    # 3. Company_Tag_Map (股票與標籤多對多映射表)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Company_Tag_Map (
            證券代號 TEXT,
            Tag_ID INTEGER,
            PRIMARY KEY (證券代號, Tag_ID),
            FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號),
            FOREIGN KEY (Tag_ID) REFERENCES Tag_Dim(Tag_ID)
        )
    ''')

    # 4. Dividend_Fact (除權息事件表)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Dividend_Fact (
            事件_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            證券代號 TEXT,
            除權息日期 TEXT,
            現金股利 REAL DEFAULT 0.0,
            股票股利 REAL DEFAULT 0.0,
            FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號)
        )
    ''')

    # 寫入最新股票清單到 Company_Dim
    # 使用 INSERT OR REPLACE 確保名稱如果有更動會自動更新
    latest_companies_df = latest_companies_df[['證券代號', '證券名稱']].drop_duplicates()
    for _, row in latest_companies_df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO Company_Dim (證券代號, 證券名稱) 
            VALUES (?, ?)
        ''', (str(row['證券代號']).strip(), str(row['證券名稱']).strip()))

    conn.commit()
    conn.close()
    print(f"[DB] 成功寫入 {len(latest_companies_df)} 檔股票資料至 Company_Dim。")

def main():
    json_files = sorted(list(STAGING_DIR.glob("*.json")))
    if not json_files:
        print("沒有找到 JSON 暫存檔，請先執行 step1_fetcher.py")
        return

    print(f"開始處理 {len(json_files)} 個 JSON 檔案...")
    all_dfs = []
    
    # 用於捕捉最新一天的資料，以建立 Company_Dim
    latest_day_df = None 

    for file_path in tqdm(json_files, desc="讀取與清洗資料"):
        # 從檔名取得日期，例如 20060102.json -> 2006-01-02
        raw_date = file_path.stem
        date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_json = json.load(f)
            
        target_data, target_fields = None, None
        
        target_data, target_fields = None, None
        
        # 🌟 第一軌：嘗試解析新版 TWSE API 結構 ('tables' 陣列)
        if 'tables' in raw_json and isinstance(raw_json['tables'], list):
            for table in raw_json['tables']:
                if 'fields' in table and 'data' in table:
                    clean_fields = [str(col).replace(' ', '').replace('　', '').replace('\n', '').strip() for col in table['fields']]
                    if '證券代號' in clean_fields:
                        target_data = table['data']
                        target_fields = clean_fields
                        break

        # 🌟 第二軌：如果新版沒找到，嘗試解析舊版 TWSE API 結構 (fields9 / data9)
        if not target_data:
            for key, val in raw_json.items():
                if key.startswith('fields') and isinstance(val, list):
                    clean_fields = [str(col).replace(' ', '').replace('　', '').replace('\n', '').strip() for col in val]
                    if '證券代號' in clean_fields:
                        data_key = key.replace('fields', 'data')
                        if data_key in raw_json:
                            target_data = raw_json[data_key]
                            target_fields = clean_fields
                            break
                            
        # 最終防線 Debug
        if not target_data:
            print(f"\n[Debug] {date_str} 完全找不到證券代號！檔案 Keys: {list(raw_json.keys())}")
            continue
        
        if target_data and target_fields:
            df = pd.DataFrame(target_data, columns=target_fields)
            cleaned_df = clean_and_transform(df, date_str)
            all_dfs.append(cleaned_df)
            latest_day_df = cleaned_df # 迴圈跑完時，這會是最新一天的資料

    print("\n資料清洗完成，正在進行記憶體大合併 (The Great Pivot)...")
    # 將所有日期的資料合併成一個超級大表 (8百萬筆資料在 pandas 大約幾秒鐘)
    master_df = pd.concat(all_dfs, ignore_index=True)
    
    # 初始化資料庫 (傳入最後一天的資料來建立股票清單)
    if latest_day_df is not None:
        init_sqlite_schema(latest_day_df)

    print("\n正在按證券代號分割並寫入 Parquet...")
    # 將不要的 "證券名稱" 從 Parquet 準備名單中踢掉 (它已經存在 SQLite 了)
    master_df = master_df.drop(columns=['證券名稱'])
    
    # 按照證券代號分組並存檔
    groups = master_df.groupby('證券代號')
    for stock_id, group_df in tqdm(groups, desc="寫入 Parquet"):
        clean_stock_id = str(stock_id).strip()
        # 剔除可能造成檔名異常的字元
        clean_stock_id = re.sub(r'[\\/*?:"<>|]', "", clean_stock_id)
        if not clean_stock_id:
            continue
            
        # 確保資料依照日期排序
        group_df = group_df.sort_values(by='日期').reset_index(drop=True)
        save_path = PARQUET_DIR / f"{clean_stock_id}.parquet"
        group_df.to_parquet(save_path, index=False)

    print("\n✅ ETL 流程與資料庫建置大功告成！")

if __name__ == "__main__":
    main()