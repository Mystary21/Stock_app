#!/usr/bin/env python3
"""
core/schema.py - 族群分析資料庫 schema 升級 (Migration)

升級內容:
1. Tag_Category   - 標籤分類維度 (材料/產品/題材/客戶)
2. Tag_Dim        - 加上 Category_ID、描述
3. Company_Tag_Map - 加上 關聯強度、資料來源
4. Revenue_Fact   - 月營收事實表 (來自 MOPS)
5. Catalyst_Event - 重大事件表 (法說會/Guidance/接單)

可重複執行 (idempotent)，已存在的欄位/表不會重建。
"""

import sqlite3

DB_PATH = "stock_warehouse.db"

from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.orm import declarative_base

# 假設你專案中已有定義好的 Base，請沿用它
Base = declarative_base()

class StockThemeMapping(Base):
    """自訂族群與股票的實時映射資料表"""
    __tablename__ = 'stock_theme_mappings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True) # 股票代號 (例如: 3105)
    stock_name = Column(String(50), nullable=True)               # 股票名稱 (例如: 穩懋)
    theme_name = Column(String(50), nullable=False, index=True) # 族群標籤 (例如: 第三代半導體)
    created_at = Column(DateTime, default=func.now())

    
def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def migrate(db_path: str = DB_PATH):
    """執行 schema 升級"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("[Schema] 開始升級資料庫結構...")

    # ---- 1. Tag_Category (標籤分類維度) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Tag_Category (
            Category_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Category_Name TEXT UNIQUE,
            排序 INTEGER DEFAULT 0
        )
    ''')

    # 預設分類維度
    default_categories = [
        ("材料/製程", 1),
        ("產品/應用", 2),
        ("題材/供應鏈", 3),
        ("客戶關聯", 4),
        ("其他", 9),
    ]
    for name, order in default_categories:
        cursor.execute(
            "INSERT OR IGNORE INTO Tag_Category (Category_Name, 排序) VALUES (?, ?)",
            (name, order)
        )

    # ---- 2. Tag_Dim 升級 (確保表存在 + 補欄位) ----
    if not _table_exists(cursor, "Tag_Dim"):
        cursor.execute('''
            CREATE TABLE Tag_Dim (
                Tag_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Tag_Name TEXT UNIQUE
            )
        ''')

    if not _column_exists(cursor, "Tag_Dim", "Category_ID"):
        cursor.execute("ALTER TABLE Tag_Dim ADD COLUMN Category_ID INTEGER REFERENCES Tag_Category(Category_ID)")
        print("[Schema] Tag_Dim 新增欄位: Category_ID")
    if not _column_exists(cursor, "Tag_Dim", "描述"):
        cursor.execute("ALTER TABLE Tag_Dim ADD COLUMN 描述 TEXT")
        print("[Schema] Tag_Dim 新增欄位: 描述")

    # ---- 3. Company_Tag_Map 升級 ----
    if not _table_exists(cursor, "Company_Tag_Map"):
        cursor.execute('''
            CREATE TABLE Company_Tag_Map (
                證券代號 TEXT,
                Tag_ID INTEGER,
                PRIMARY KEY (證券代號, Tag_ID),
                FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號),
                FOREIGN KEY (Tag_ID) REFERENCES Tag_Dim(Tag_ID)
            )
        ''')

    if not _column_exists(cursor, "Company_Tag_Map", "關聯強度"):
        # 關聯強度: 0.9=主力業務, 0.6=參與, 0.3=概念沾邊
        cursor.execute("ALTER TABLE Company_Tag_Map ADD COLUMN 關聯強度 REAL DEFAULT 0.6")
        print("[Schema] Company_Tag_Map 新增欄位: 關聯強度")
    if not _column_exists(cursor, "Company_Tag_Map", "資料來源"):
        cursor.execute("ALTER TABLE Company_Tag_Map ADD COLUMN 資料來源 TEXT")
        print("[Schema] Company_Tag_Map 新增欄位: 資料來源")
    if not _column_exists(cursor, "Company_Tag_Map", "更新時間"):
        cursor.execute("ALTER TABLE Company_Tag_Map ADD COLUMN 更新時間 TIMESTAMP")
        print("[Schema] Company_Tag_Map 新增欄位: 更新時間")

    # ---- 4. Revenue_Fact (月營收事實表) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Revenue_Fact (
            證券代號 TEXT,
            年月 TEXT,
            當月營收 REAL,
            上月營收 REAL,
            去年同月營收 REAL,
            月增率 REAL,
            年增率 REAL,
            當月累計營收 REAL,
            去年累計營收 REAL,
            累計年增率 REAL,
            PRIMARY KEY (證券代號, 年月),
            FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號)
        )
    ''')

    # ---- 5. Catalyst_Event (重大事件表) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Catalyst_Event (
            事件_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            證券代號 TEXT,
            日期 TEXT,
            類型 TEXT,
            標題 TEXT,
            內容摘要 TEXT,
            來源連結 TEXT,
            FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號)
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_catalyst_stock ON Catalyst_Event(證券代號)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_revenue_stock ON Revenue_Fact(證券代號)")

    conn.commit()
    conn.close()
    print("[Schema] ✅ 資料庫結構升級完成")


if __name__ == "__main__":
    migrate()
