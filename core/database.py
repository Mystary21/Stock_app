#!/usr/bin/env python3
"""
core/database.py - SQLAlchemy 資料庫引擎與會話
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_PATH = "stock_warehouse.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

SessionLocal = sessionmaker(bind=engine)

def get_db_session():
    return SessionLocal()
