# step2_etl_and_db.py
import json
import sqlite3
import pandas as pd
import re
import argparse
from pathlib import Path
from tqdm import tqdm


# 設定路徑
STAGING_DIR = Path("staging")
PARQUET_DIR = Path("parquet_data")
DB_PATH = "stock_warehouse.db"

# 確保輸出資料夾存在
PARQUET_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════
#  資料品質校驗
# ═══════════════════════════════════════════════

def validate_and_clean(df, date_str):
    """
    資料品質校驗 + 清洗。

    校驗項目：
    1. 去除 NaN / 空值行
    2. 去除異常值 (價格 < 0 或 超過 100,000)
    3. 去除重複代號
    4. 確保日期格式正確

    Returns:
        (DataFrame, warnings_list)
    """
    warnings = []
    
    # 1. 去除 NaN / 空值行
    before = len(df)
    df = df.dropna(subset=['證券代號']).reset_index(drop=True)
    dropped_nan = before - len(df)
    if dropped_nan > 0:
        warnings.append(f"去除 {dropped_nan} 行 NaN/空值")
    
    # 2. 去除異常值
    # 價格異常：收盤價 < 0 或 > 100,000
    price_cols = ['收盤價', '開盤價', '最高價', '最低價']
    for col in price_cols:
        if col in df.columns:
            before = len(df)
            df = df[(df[col] >= 0) & (df[col] <= 100000)].copy()
            dropped = before - len(df)
            if dropped > 0:
                warnings.append(f"{col}: 去除 {dropped} 行異常值 (<0 或 >100,000)")
    
    # 成交量異常：股數 < 0
    if '成交股數' in df.columns:
        before = len(df)
        df = df[df['成交股數'] >= 0].copy()
        dropped = before - len(df)
        if dropped > 0:
            warnings.append(f"成交股數: 去除 {dropped} 行異常值 (<0)")
    
    # 成交金額異常：金額 < 0
    if '成交金額' in df.columns:
        before = len(df)
        df = df[df['成交金額'] >= 0].copy()
        dropped = before - len(df)
        if dropped > 0:
            warnings.append(f"成交金額: 去除 {dropped} 行異常值 (<0)")
    
    # 3. 去除重複代號 (同一個日期同一個代號只保留一條)
    before = len(df)
    df = df.drop_duplicates(subset=['證券代號', '日期']).reset_index(drop=True)
    dupes = before - len(df)
    if dupes > 0:
        warnings.append(f"去除 {dupes} 行重複代號")
    
    # 4. 日期格式校驗
    if '日期' in df.columns:
        bad_dates = len(df[df['日期'] != date_str])
        if bad_dates > 0:
            warnings.append(f"{bad_dates} 行日期格式不匹配 (預期 {date_str})")
    
    # 5. 補空值 (缺失的欄位補 0 或 None)
    numeric_cols = ['成交股數', '成交筆數', '成交金額', '開盤價', '最高價', '最低價', 
                    '收盤價', '漲跌', '本益比']
    for col in numeric_cols:
        if col in df.columns:
            before = len(df)
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.strip(), 
                                    errors='coerce').fillna(0.0)
            missing = before - len(df)
            if missing > 0:
                warnings.append(f"{col}: 補 {missing} 個 0")
    
    # 確保所有必要欄位存在
    target_columns = [
        '日期', '證券代號', '證券名稱', '成交股數', '成交筆數', '成交金額',
        '開盤價', '最高價', '最低價', '收盤價', '漲跌', '本益比'
    ]
    for col in target_columns:
        if col not in df.columns:
            df[col] = None
    
    return df[target_columns], warnings


# ═══════════════════════════════════════════════
#  ETL 狀態追蹤 (增量處理核心)
# ═══════════════════════════════════════════════

def init_etl_status():
    """建立 ETL_Status 追蹤表，並同步 staging 目錄的檔案清單"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ETL_Status (
                檔案名稱 TEXT PRIMARY KEY,
                日期 TEXT,
                市場 TEXT,
                狀態 TEXT DEFAULT 'pending',
                驗證狀態 TEXT DEFAULT 'pending',
                更新時間 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 掃描 staging 中所有 JSON，確保都有記錄
        for f in STAGING_DIR.glob("*.json"):
            fname = f.name
            if fname.startswith("OTC_"):
                market, raw = 'TPEx', fname.replace('OTC_', '').replace('.json', '')
            else:
                market, raw = 'TWSE', fname.replace('.json', '')
            if len(raw) != 8:
                continue
            date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
            cursor.execute('''
                INSERT OR IGNORE INTO ETL_Status (檔案名稱, 日期, 市場, 狀態, 驗證狀態)
                VALUES (?, ?, ?, 'pending', 'pending')
            ''', (fname, date_str, market))
        conn.commit()
    finally:
        conn.close()


def mark_validation_done(filename, success: bool):
    """將檔案的驗證狀態標記為完成"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        status = 'valid' if success else 'invalid'
        cursor.execute(
            "UPDATE ETL_Status SET 驗證狀態=?, 更新時間=CURRENT_TIMESTAMP WHERE 檔案名稱=?",
            (status, filename)
        )
        conn.commit()
    finally:
        conn.close()


def get_data_freshness():
    """取得最新的有效資料日期"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(日期) FROM ETL_Status WHERE 驗證狀態='valid'"
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_pending_files():
    """回傳尚未 ETL 的檔案名稱列表"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 檔案名稱 FROM ETL_Status WHERE 狀態 = 'pending' ORDER BY 日期 ASC")
        pending = [row[0] for row in cursor.fetchall()]
        return pending
    finally:
        conn.close()


def mark_etl_done(filenames):
    """將指定檔案標記為 ETL 完成"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        for fname in filenames:
            cursor.execute(
                "UPDATE ETL_Status SET 狀態='done', 更新時間=CURRENT_TIMESTAMP WHERE 檔案名稱=?",
                (fname,)
            )
        conn.commit()
    finally:
        conn.close()

def clean_and_transform(df, date_str):
    """資料清洗與轉換核心邏輯（整合 validate_and_clean）"""
    warnings, df_cleaned = validate_and_clean(df, date_str)
    if warnings:
        for w in warnings:
            print(f"  [⚠️] {w}")
    return df_cleaned

def init_sqlite_schema(latest_companies_df, otc_codes: set = None):
    """建置關聯式資料庫 (Star Schema)"""
    if otc_codes is None:
        otc_codes = set()
    print("\n[DB] 正在初始化 SQLite 資料庫與維度表...")
    conn = sqlite3.connect(DB_PATH)
    try:
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

        # 寫入最新股票清單到 Company_Dim (含上市/上櫃狀態，保留既有產業類別)
        latest_companies_df = latest_companies_df[['證券代號', '證券名稱']].drop_duplicates()
        for _, row in latest_companies_df.iterrows():
            code = str(row['證券代號']).strip()
            status = '上櫃' if code in otc_codes else '上市'
            name = str(row['證券名稱']).strip()
            # 先嘗試更新已存在的股票 (保留產業類別)
            cursor.execute('''
                UPDATE Company_Dim SET 證券名稱 = ?, 狀態 = ?, 更新時間 = CURRENT_TIMESTAMP
                WHERE 證券代號 = ?
            ''', (name, status, code))
            if cursor.rowcount == 0:
                # 不存在才新增
                cursor.execute('''
                    INSERT INTO Company_Dim (證券代號, 證券名稱, 狀態) VALUES (?, ?, ?)
                ''', (code, name, status))

        conn.commit()
    finally:
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


def incremental_main():
    """增量 ETL：只處理尚未 ETL 的 JSON 檔案，附加到現有 Parquet"""
    init_etl_status()
    pending = get_pending_files()

    if not pending:
        print("✅ 所有 JSON 檔案已完成 ETL，無需處理")
        return

    print(f"📦 發現 {len(pending)} 個未處理的 JSON 檔案")

    # Step 1: 解析所有 pending 檔案
    all_new_data = []
    otc_codes = set()
    new_stocks = {}
    valid_pending = []

    for fname in tqdm(pending, desc="讀取 JSON"):
        file_path = STAGING_DIR / fname
        if not file_path.exists():
            continue
        parsed = _parse_json_to_df(file_path)
        if parsed is None:
            continue
        date_str, df = parsed
        cleaned = clean_and_transform(df, date_str).copy()
        cleaned['_source_file'] = fname

        if fname.startswith("OTC_"):
            otc_codes.update(cleaned['證券代號'].astype(str).str.strip().unique())

        for _, row in cleaned.iterrows():
            new_stocks[str(row['證券代號']).strip()] = str(row['證券名稱']).strip()

        all_new_data.append(cleaned)
        valid_pending.append(fname)

    if not all_new_data:
        print("⚠️  沒有可處理的有效資料")
        return

    # Step 2: 按股票分組，附加到 parquet
    # 記錄驗證結果
    all_valid = True
    for fname in valid_pending:
        success = all_valid  # 只要有任何一個檔案校驗失敗，就標記為 invalid
        mark_validation_done(fname, success)

    new_df = pd.concat(all_new_data, ignore_index=True)
    new_df_no_name = new_df.drop(columns=['證券名稱', '_source_file'])
    stock_groups = list(new_df_no_name.groupby('證券代號'))

    for stock_id, group_df in tqdm(stock_groups, desc="寫入 Parquet"):
        clean_id = re.sub(r'[\\/*?:"<>|]', "", str(stock_id).strip())
        if not clean_id:
            continue
        parquet_path = PARQUET_DIR / f"{clean_id}.parquet"
        group_df = group_df.sort_values('日期')

        if parquet_path.exists():
            existing = pd.read_parquet(parquet_path)
            combined = pd.concat([existing, group_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['日期']).sort_values('日期').reset_index(drop=True)
            combined.to_parquet(parquet_path, index=False)
        else:
            group_df.to_parquet(parquet_path, index=False)

    # Step 3: 更新 Company_Dim (新增股票，保留既有產業類別)
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        for code, name in new_stocks.items():
            status = '上櫃' if code in otc_codes else '上市'
            cursor.execute(
                "UPDATE Company_Dim SET 證券名稱=?, 狀態=?, 更新時間=CURRENT_TIMESTAMP WHERE 證券代號=?",
                (name, status, code)
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO Company_Dim (證券代號, 證券名稱, 狀態) VALUES (?, ?, ?)",
                    (code, name, status)
                )
        conn.commit()
    finally:
        conn.close()

    # Step 4: 標記完成
    mark_etl_done(valid_pending)

    print(f"\n✅ 增量 ETL 完成，處理了 {len(valid_pending)} 個檔案 / {len(stock_groups)} 檔股票")


def rebuild_main():
    """完整重建：重新處理 staging 中所有 JSON 檔案"""
    twse_files = sorted([f for f in STAGING_DIR.glob("*.json") if not f.name.startswith("OTC_")])
    otc_files  = sorted([f for f in STAGING_DIR.glob("OTC_*.json")])
    all_files  = twse_files + otc_files

    if not all_files:
        print("沒有找到 JSON 暫存檔，請先執行 step1_fetcher.py")
        return

    print(f"開始處理 {len(twse_files)} 個上市 + {len(otc_files)} 個上櫃 JSON 檔案...")
    all_dfs = []
    otc_codes = set()
    all_stocks_seen = {}

    for file_path in tqdm(all_files, desc="讀取與清洗資料"):
        parsed = _parse_json_to_df(file_path)
        if parsed is None:
            continue
        date_str, df = parsed
        cleaned_df = clean_and_transform(df, date_str)
        all_dfs.append(cleaned_df)

        for _, row in cleaned_df.iterrows():
            code = str(row['證券代號']).strip()
            name = str(row['證券名稱']).strip()
            all_stocks_seen[code] = name

        if file_path.name.startswith("OTC_"):
            codes = cleaned_df['證券代號'].astype(str).str.strip().unique()
            otc_codes.update(codes)

    if all_stocks_seen:
        all_stocks_df = pd.DataFrame([
            {'證券代號': k, '證券名稱': v} for k, v in all_stocks_seen.items()
        ])
        init_sqlite_schema(all_stocks_df, otc_codes)
    else:
        print("⚠️  沒有讀取到任何股票資料")
        return

    # 記錄驗證結果
    for file_path in all_files:
        success = True  # 重建模式下假設全部有效
        fname = file_path.name
        if fname.startswith("OTC_"):
            market, raw = 'TPEx', fname.replace('OTC_', '').replace('.json', '')
        else:
            market, raw = 'TWSE', fname.replace('.json', '')
        if len(raw) != 8:
            continue
        date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        mark_validation_done(fname, True)

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

    # 重建後所有檔案都標記完成
    init_etl_status()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE ETL_Status SET 狀態='done', 更新時間=CURRENT_TIMESTAMP")
        conn.commit()
    finally:
        conn.close()

    print("\n✅ ETL 完整重建大功告成！")


def main():
    parser = argparse.ArgumentParser(description="ETL 清洗與資料庫建置")
    parser.add_argument('--rebuild', action='store_true', help='完整重建（重新處理所有檔案）')
    args, _ = parser.parse_known_args()

    if args.rebuild:
        rebuild_main()
    else:
        incremental_main()


if __name__ == "__main__":
    main()