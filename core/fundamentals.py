#!/usr/bin/env python3
"""
core/fundamentals.py - 財務比率計算與基本面分析

提供計算以下財務指標的函式:
- P/E (本益比)
- P/B (市帳率)
- ROE (淨利權益報酬率)
- ROA (淨利資產報酬率)
- 負債比
- 毛利率
- 淨利率
- EPS (每股盈餘)
- BPS (每股淨值)

用法:
    from core.fundamentals import FundamentalAnalyzer

    analyzer = FundamentalAnalyzer()
    metrics = analyzer.analyze(stock_id, latest_price, financial_data)
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List


class FundamentalAnalyzer:
    """基本面分析器"""

    def __init__(self):
        self.db_path = "stock_warehouse.db"

    def _get_connection(self):
        """獲得 SQLite 連接"""
        return sqlite3.connect(self.db_path)

    def _return_connection(self, conn):
        """將連線歸還"""
        try:
            conn.close()
        except Exception:
            pass

    def get_latest_price(self, stock_id: str) -> Optional[dict]:
        """取得最新一天股票價格"""
        try:
            conn = self._get_connection()
            try:
                query = """
                    SELECT 日期, 開盤價, 最高價, 最低價, 收盤價, 成交股數, 成交金額
                    FROM Stock_Fact
                    WHERE 證券代號 = ?
                    ORDER BY 日期 DESC
                    LIMIT 1
                """
                df = pd.read_sql_query(query, conn, params=(stock_id,))
            finally:
                self._return_connection(conn)

            if df.empty:
                return None

            row = df.iloc[0]
            return {
                'date': row['日期'],
                'close': row['收盤價'],
                'open': row['開盤價'],
                'high': row['最高價'],
                'low': row['最低價'],
                'volume': row['成交股數'],
                'value': row['成交金額'],
            }
        except Exception:
            return None

    def get_financial_data(self, stock_id: str) -> Optional[dict]:
        """取得最新財務資料 (從 MOPS API 抓取)"""
        try:
            conn = self._get_connection()
            try:
                query = """
                    SELECT 年月, 淨利, 營業利益, 稅前淨利, 營業外淨利,
                           股東權益, 總資產, 負債, 營收, 毛利率
                    FROM Financial_Fact
                    WHERE 證券代號 = ?
                    ORDER BY 年月 DESC
                    LIMIT 1
                """
                df = pd.read_sql_query(query, conn, params=(stock_id,))
            finally:
                self._return_connection(conn)

            if df.empty:
                return None

            row = df.iloc[0]
            return {
                'year': row['年月'],
                'net_income': row['淨利'],
                'operating_income': row['營業利益'],
                'income_before_tax': row['稅前淨利'],
                'other_income': row['營業外淨利'],
                'shareholders_equity': row['股東權益'],
                'total_assets': row['總資產'],
                'liabilities': row['負債'],
                'revenue': row['營收'],
                'gross_margin': row['毛利率'],
            }
        except Exception:
            return None

    def analyze(self, stock_id: str) -> Optional[Dict[str, float]]:
        """
        計算所有基本面指標。

        Returns:
            dict: {
                'pe_ratio': 本益比,
                'pb_ratio': 市帳率,
                'roe': ROE,
                'roa': ROA,
                'debt_ratio': 負債比,
                'gross_margin': 毛利率,
                'net_margin': 淨利率,
                'eps': 每股盈餘,
                'bps': 每股淨值,
                'close_price': 最新收盤價,
                'analysis_date': 分析日期,
            }
        """
        latest_price = self.get_latest_price(stock_id)
        financial_data = self.get_financial_data(stock_id)

        if latest_price is None or financial_data is None:
            return None

        close_price = latest_price['close']
        net_income = financial_data['net_income']
        shareholders_equity = financial_data['shareholders_equity']
        total_assets = financial_data['total_assets']
        liabilities = financial_data['liabilities']
        revenue = financial_data['revenue']
        gross_margin = financial_data['gross_margin']

        # 計算各指標
        metrics = {}

        # P/E (本益比)
        if net_income and net_income > 0:
            eps = net_income / close_price
            metrics['pe_ratio'] = round(close_price / eps, 2) if eps > 0 else None
            metrics['eps'] = round(eps, 2)
        else:
            metrics['pe_ratio'] = None
            metrics['eps'] = None

        # P/B (市帳率)
        if shareholders_equity and shareholders_equity > 0:
            bps = shareholders_equity / close_price
            metrics['pb_ratio'] = round(close_price / bps, 2) if bps > 0 else None
            metrics['bps'] = round(bps, 2)
        else:
            metrics['pb_ratio'] = None
            metrics['bps'] = None

        # ROE
        if shareholders_equity and shareholders_equity > 0 and net_income:
            metrics['roe'] = round((net_income / shareholders_equity) * 100, 2)
        else:
            metrics['roe'] = None

        # ROA
        if total_assets and total_assets > 0 and net_income:
            metrics['roa'] = round((net_income / total_assets) * 100, 2)
        else:
            metrics['roa'] = None

        # 負債比
        if total_assets and total_assets > 0:
            metrics['debt_ratio'] = round((liabilities / total_assets) * 100, 2)
        else:
            metrics['debt_ratio'] = None

        # 毛利率
        if revenue and revenue > 0:
            metrics['gross_margin'] = round((gross_margin / revenue) * 100, 2) if gross_margin else None
        else:
            metrics['gross_margin'] = None

        # 淨利率
        if revenue and revenue > 0 and net_income:
            metrics['net_margin'] = round((net_income / revenue) * 100, 2)
        else:
            metrics['net_margin'] = None

        metrics['close_price'] = round(close_price, 2)
        metrics['analysis_date'] = datetime.now().strftime('%Y-%m-%d')

        return metrics

    def get_all_stocks_metrics(self) -> pd.DataFrame:
        """取得所有股票的基本面指標"""
        try:
            conn = self._get_connection()
            try:
                query = """
                    SELECT c.證券代號, c.證券名稱,
                           pe_ratio, pb_ratio, roe, roa,
                           debt_ratio, gross_margin, net_margin,
                           eps, bps, close_price
                    FROM Company_Dim c
                    LEFT JOIN (
                        SELECT 證券代號,
                               pe_ratio, pb_ratio, roe, roa,
                               debt_ratio, gross_margin, net_margin,
                               eps, bps, close_price
                        FROM Stock_Fact
                        WHERE 證券代號 IN (SELECT 證券代號 FROM Company_Dim)
                        ORDER BY 日期 DESC
                        LIMIT 1
                    ) f ON c.證券代號 = f.證券代號
                    WHERE pe_ratio IS NOT NULL
                """
                df = pd.read_sql_query(query, conn)
            finally:
                self._return_connection(conn)
            return df
        except Exception:
            return pd.DataFrame()
