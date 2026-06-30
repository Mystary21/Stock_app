#!/usr/bin/env python3
"""
core/database.py - SQLAlchemy 資料庫引擎與會話
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_PATH = os.getenv("STOCK_DB_PATH", "stock_warehouse.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

SessionLocal = sessionmaker(bind=engine)


def init_indexes():
    """初始化資料庫索引，提升查詢效能"""
    indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_company_industry ON Company_Dim(產業類別);
        CREATE INDEX IF NOT EXISTS idx_company_status ON Company_Dim(狀態);
        CREATE INDEX IF NOT EXISTS idx_stock_fact_date ON Stock_Fact(證券代號, 日期);
        CREATE INDEX IF NOT EXISTS idx_dividend_stock ON Dividend_Fact(證券代號);
        CREATE INDEX IF NOT EXISTS idx_revenue_stock ON Revenue_Fact(證券代號);
        CREATE INDEX IF NOT EXISTS idx_revenue_date ON Revenue_Fact(年月);
        CREATE INDEX IF NOT EXISTS idx_tag_name ON Tag_Dim(Tag_Name);
        CREATE INDEX IF NOT EXISTS idx_tag_category ON Tag_Dim(Category_ID);
        CREATE INDEX IF NOT EXISTS idx_company_tag_map ON Company_Tag_Map(證券代號);
        CREATE INDEX IF NOT EXISTS idx_etl_status_date ON ETL_Status(日期);
        CREATE INDEX IF NOT EXISTS idx_etl_status_validation ON ETL_Status(驗證狀態);
        CREATE INDEX IF NOT EXISTS idx_catalyst_stock ON Catalyst_Event(證券代號);
        CREATE INDEX IF NOT EXISTS idx_catalyst_date ON Catalyst_Event(日期);
    """
    with engine.connect() as conn:
        conn.execute(text(indexes_sql))
        conn.commit()


# 初始化索引
init_indexes()

def get_db_session():
    return SessionLocal()
