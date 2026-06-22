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

def init_sqlite_schema(latest_companies_df, otc_codes: set = None):
    """建置關聯式資料庫 (Star Schema)"""
    if otc_codes is None:
        otc_codes = set()
    print("\n[DB] 正在初始化 SQLite 資料庫與維度表...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Company_Dim (股票總覽表，含上市/上櫃狀態)
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

    # 寫入最新股票清單到 Company_Dim (含上市/上櫃狀態)
    latest_companies_df = latest_companies_df[['證券代號', '證券名稱']].drop_duplicates()
    for _, row in latest_companies_df.iterrows():
        code = str(row['證券代號']).strip()
        status = '上櫃' if code in otc_codes else '上市'
        cursor.execute('''
            INSERT OR REPLACE INTO Company_Dim (證券代號, 證券名稱, 狀態) 
            VALUES (?, ?, ?)
        ''', (code, str(row['證券名稱']).strip(), status))

    conn.commit()
    conn.close()
    counts = {'上市': 0, '上櫃': 0}
    for code in latest_companies_df['證券代號'].astype(str).str.strip():
        counts['上櫃' if code in otc_codes else '上市'] += 1
    print(f"[DB] 成功寫入 {len(latest_companies_df)} 檔股票 (上市 {counts['上市']} / 上櫃 {counts['上櫃']})")

def _parse_json_to_df(file_path: Path):
    """解析單一 JSON 檔 (支援 TWSE 或 TPEx/OTC 格式) 回傳 (date_str, DataFrame) 或 None"""
    raw_date = file_path.stem.replace('OTC_', '')
    if len(raw_date) != 8:
        return None
    date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"

    with open(file_path, 'r', encoding='utf-8') as f:
        raw_json = json.load(f)

    target_data, target_fields = None, None

    # 第一軌: tables 陣列 (新 TWSE API)
    if 'tables' in raw_json and isinstance(raw_json['tables'], list):
        for table in raw_json['tables']:
            if 'fields' in table and 'data' in table:
                clean = [str(c).replace(' ', '').replace('　', '').replace('\n', '').strip() for c in table['fields']]
                if '證券代號' in clean:
                    target_data, target_fields = table['data'], clean
                    break

    # 第二軌: fields9/data9 (舊 TWSE API / TPEx 格式)
    if not target_data:
        for key, val in raw_json.items():
            if key.startswith('fields') and isinstance(val, list):
                clean = [str(c).replace(' ', '').replace('　', '').replace('\n', '').strip() for c in val]
                if '證券代號' in clean:
                    dk = key.replace('fields', 'data')
                    if dk in raw_json:
                        target_data, target_fields = raw_json[dk], clean
                        break

    if not target_data:
        print(f"\n[Debug] {file_path.name} 找不到證券代號！")
        return None

    df = pd.DataFrame(target_data, columns=target_fields)
    return date_str, df


def main():
    # 掃描所有 TWSE 與 OTC 暫存檔
    twse_files = sorted([f for f in STAGING_DIR.glob("*.json") if not f.name.startswith("OTC_")])
    otc_files  = sorted([f for f in STAGING_DIR.glob("OTC_*.json")])
    all_files  = twse_files + otc_files

    if not all_files:
        print("沒有找到 JSON 暫存檔，請先執行 step1_fetcher.py")
        return

    print(f"開始處理 {len(twse_files)} 個上市 + {len(otc_files)} 個上櫃 JSON 檔案...")
    all_dfs = []
    otc_codes = set()
    all_stocks_seen = {}  # code -> name (所有出現過的股票)
    latest_day_df = None

    for file_path in tqdm(all_files, desc="讀取與清洗資料"):
        parsed = _parse_json_to_df(file_path)
        if parsed is None:
            continue
        date_str, df = parsed
        cleaned_df = clean_and_transform(df, date_str)
        all_dfs.append(cleaned_df)

        # 收集所有出現過的股票
        for _, row in cleaned_df.iterrows():
            code = str(row['證券代號']).strip()
            name = str(row['證券名稱']).strip()
            all_stocks_seen[code] = name

        # 累計 OTC 股票代號
        if file_path.name.startswith("OTC_"):
            codes = cleaned_df['證券代號'].astype(str).str.strip().unique()
            otc_codes.update(codes)

        # 追蹤最新一天的資料 (用於 Company_Dim)
        if latest_day_df is None or date_str > latest_day_df['日期'].iloc[0]:
            latest_day_df = cleaned_df

    # 用所有出現過的股票建立 Company_Dim (而非只用最新一天)
    if all_stocks_seen:
        all_stocks_df = pd.DataFrame([
            {'證券代號': k, '證券名稱': v} for k, v in all_stocks_seen.items()
        ])
        init_sqlite_schema(all_stocks_df, otc_codes)
    elif latest_day_df is not None:
        init_sqlite_schema(latest_day_df, otc_codes)

    print("\n資料清洗完成，正在合併所有資料...")
    master_df = pd.concat(all_dfs, ignore_index=True)

    print("\n正在按證券代號分割並寫入 Parquet...")
    master_df = master_df.drop(columns=['證券名稱'])
    groups = master_df.groupby('證券代號')
    for stock_id, group_df in tqdm(groups, desc="寫入 Parquet"):
        clean_id = re.sub(r'[\\/*?:"<>|]', "", str(stock_id).strip())
        if not clean_id:
            continue
        group_df = group_df.sort_values(by='日期').reset_index(drop=True)
        group_df.to_parquet(PARQUET_DIR / f"{clean_id}.parquet", index=False)

    print("\n✅ ETL 流程與資料庫建置大功告成！")

if __name__ == "__main__":
    main()