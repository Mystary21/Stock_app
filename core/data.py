# core/data.py - 統一的數據查詢 API 層
import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
from contextlib import contextmanager

# 設定路徑
DB_PATH = "stock_warehouse.db"
PARQUET_DIR = Path("parquet_data")

class StockDataQuery:
    """統一的股票數據查詢引擎"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.parquet_dir = PARQUET_DIR
        self._connection_pool = None
    
    def _get_connection_pool(self):
        """Lazy 初始化連線池"""
        if self._connection_pool is None:
            self._connection_pool = sqlite3.ConnectionPool()
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection_pool.register(conn)
        return self._connection_pool
    
    def _get_connection(self):
        """
        獲得 SQLite 連接。
        
        若已建立連線池，則從池中取出；否則建立新連線。
        """
        pool = self._get_connection_pool()
        try:
            return pool.acquire()
        except Exception:
            # 連線池異常時回退到直接連線
            return sqlite3.connect(self.db_path)
    
    def _return_connection(self, conn):
        """將連線歸還連線池"""
        pool = self._get_connection_pool()
        try:
            pool.release(conn)
        except Exception:
            pass  # 連線池異常時忽略
    
    # ================== 基礎查詢 ==================
    
    def get_all_stocks(self) -> pd.DataFrame:
        """取得所有股票的基本資訊"""
        conn = self._get_connection()
        try:
            query = "SELECT 證券代號, 證券名稱, 產業類別, 狀態 FROM Company_Dim"
            df = pd.read_sql_query(query, conn)
        finally:
            self._return_connection(conn)
        return df
    
    def get_stock_by_id(self, stock_id: str) -> Optional[dict]:
        """根據股票代號取得該股票資訊"""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM Company_Dim WHERE 證券代號 = ?"
            df = pd.read_sql_query(query, conn, params=(stock_id,))
        finally:
            self._return_connection(conn)
        
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    
    def get_stocks_by_industry(self, industry: str) -> pd.DataFrame:
        """根據產業類別取得所有股票"""
        conn = self._get_connection()
        try:
            query = "SELECT 證券代號, 證券名稱, 產業類別 FROM Company_Dim WHERE 產業類別 = ?"
            df = pd.read_sql_query(query, conn, params=(industry,))
        finally:
            self._return_connection(conn)
        return df
    
    def get_all_industries(self) -> List[str]:
        """取得所有產業類別"""
        conn = self._get_connection()
        try:
            query = "SELECT DISTINCT 產業類別 FROM Company_Dim WHERE 產業類別 IS NOT NULL ORDER BY 產業類別"
            df = pd.read_sql_query(query, conn)
        finally:
            self._return_connection(conn)
        return df['產業類別'].tolist()
    
    # ================== 歷史價格數據 ==================
    
    def get_stock_price_history(self, stock_id: str, start_date: Optional[str] = None, 
                               end_date: Optional[str] = None) -> pd.DataFrame:
        """
        取得單檔股票的歷史價格數據
        
        Args:
            stock_id: 股票代號 (e.g., "2330")
            start_date: 開始日期 (格式: YYYY-MM-DD, 可選)
            end_date: 結束日期 (格式: YYYY-MM-DD, 可選)
        
        Returns:
            DataFrame: 包含日期、開盤、高、低、收、成交股數、成交金額的資料
        """
        parquet_path = self.parquet_dir / f"{stock_id}.parquet"
        
        if not parquet_path.exists():
            return pd.DataFrame()
        
        try:
            df = pd.read_parquet(parquet_path)
            
            # 轉換日期為 datetime
            df['日期'] = pd.to_datetime(df['日期'])
            
            # 篩選日期範圍
            if start_date:
                df = df[df['日期'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['日期'] <= pd.to_datetime(end_date)]
            
            # 按日期升序排列
            df = df.sort_values('日期').reset_index(drop=True)
            
            return df
        except Exception as e:
            print(f"讀取 {stock_id} 的 Parquet 檔案失敗: {e}")
            return pd.DataFrame()
    
    def get_latest_price(self, stock_id: str) -> Optional[dict]:
        """取得最新一天的股票價格"""
        df = self.get_stock_price_history(stock_id)
        
        if df.empty:
            return None
        
        latest = df.iloc[-1]
        return {
            '日期': str(latest['日期'].date()),
            '開盤價': latest['開盤價'],
            '最高價': latest['最高價'],
            '最低價': latest['最低價'],
            '收盤價': latest['收盤價'],
            '漲跌': latest['漲跌'],
            '成交股數': latest['成交股數'],
            '成交金額': latest['成交金額'],
        }
    
    # ================== 基本面分析 ==================
    
    def get_fundamentals(self, stock_id: str) -> Optional[dict]:
        """
        取得股票的基本面指標 (P/E, P/B, ROE, ROA 等)
        
        Args:
            stock_id: 股票代號 (e.g., "2330")
        
        Returns:
            dict: 基本面指標，或 None
        """
        try:
            conn = self._get_connection()
            try:
                query = """
                    SELECT 
                        f.證券代號,
                        c.證券名稱,
                        f.pe_ratio,
                        f.pb_ratio,
                        f.roe,
                        f.roa,
                        f.debt_ratio,
                        f.gross_margin,
                        f.net_margin,
                        f.eps,
                        f.bps,
                        f.close_price
                    FROM Company_Dim c
                    LEFT JOIN (
                        SELECT 
                            證券代號,
                            pe_ratio,
                            pb_ratio,
                            roe,
                            roa,
                            debt_ratio,
                            gross_margin,
                            net_margin,
                            eps,
                            bps,
                            close_price
                        FROM Stock_Fact
                        WHERE 證券代號 IN (SELECT 證券代號 FROM Company_Dim)
                        ORDER BY 日期 DESC
                        LIMIT 1
                    ) f ON c.證券代號 = f.證券代號
                    WHERE f.證券代號 = ?
                """
                df = pd.read_sql_query(query, conn, params=(stock_id,))
            finally:
                self._return_connection(conn)
            
            if df.empty:
                return None
            
            row = df.iloc[0]
            return {
                '證券代號': row['證券代號'],
                '證券名稱': row['證券名稱'],
                'pe_ratio': row['pe_ratio'],
                'pb_ratio': row['pb_ratio'],
                'roe': row['roe'],
                'roa': row['roa'],
                'debt_ratio': row['debt_ratio'],
                'gross_margin': row['gross_margin'],
                'net_margin': row['net_margin'],
                'eps': row['eps'],
                'bps': row['bps'],
                'close_price': row['close_price'],
            }
        except Exception:
            return None
    
    # ================== 批量查詢 ==================
    
    def get_multi_stock_prices(self, stock_ids: List[str], 
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> dict:
        """
        批量取得多檔股票的歷史價格
        
        Returns:
            {stock_id: DataFrame, ...}
        """
        result = {}
        for stock_id in stock_ids:
            df = self.get_stock_price_history(stock_id, start_date, end_date)
            if not df.empty:
                result[stock_id] = df
        return result
    
    def get_industry_snapshot(self, industry: str, date: Optional[str] = None) -> pd.DataFrame:
        """
        取得某個產業在特定日期的快照
        
        如果未指定日期，取得最新一天的資料
        """
        # 先取得該產業的所有股票
        stocks_df = self.get_stocks_by_industry(industry)
        stock_ids = stocks_df['證券代號'].tolist()
        
        results = []
        
        for stock_id in stock_ids:
            df = self.get_stock_price_history(stock_id)
            
            if df.empty:
                continue
            
            # 如果指定日期，就篩選該日期；否則取最新一天
            if date:
                df = df[df['日期'] == date]
            else:
                df = df.tail(1)
            
            if not df.empty:
                row = df.iloc[0].to_dict()
                row['證券代號'] = stock_id
                row['證券名稱'] = stocks_df[stocks_df['證券代號'] == stock_id]['證券名稱'].values[0]
                results.append(row)
        
        return pd.DataFrame(results) if results else pd.DataFrame()
    
    # ================== 除權息事件 ==================
    
    def get_dividend_history(self, stock_id: str) -> pd.DataFrame:
        """取得股票的除權息歷史"""
        conn = self._get_connection()
        try:
            query = """
                SELECT 除權息日期, 現金股利, 股票股利 
                FROM Dividend_Fact 
                WHERE 證券代號 = ? 
                ORDER BY 除權息日期
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
        finally:
            self._return_connection(conn)
        return df
    
    # ================== 標籤功能 ==================
    
    def add_tag(self, tag_name: str) -> int:
        """新增標籤，返回 Tag_ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO Tag_Dim (Tag_Name) VALUES (?)", (tag_name,))
                conn.commit()
                tag_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                # 標籤已存在，取得其 ID
                cursor.execute("SELECT Tag_ID FROM Tag_Dim WHERE Tag_Name = ?", (tag_name,))
                tag_id = cursor.fetchone()[0]
            finally:
                self._return_connection(conn)
            return tag_id
        except Exception:
            self._return_connection(conn)
            raise
    
    def tag_stock(self, stock_id: str, tag_name: str):
        """為股票添加標籤"""
        tag_id = self.add_tag(tag_name)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO Company_Tag_Map (證券代號, Tag_ID) VALUES (?, ?)",
                    (stock_id, tag_id)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # 標籤已存在
            finally:
                self._return_connection(conn)
        except Exception:
            self._return_connection(conn)
            raise
    
    def get_stocks_by_tag(self, tag_name: str) -> pd.DataFrame:
        """取得擁有特定標籤的所有股票"""
        conn = self._get_connection()
        try:
            query = """
                SELECT DISTINCT c.證券代號, c.證券名稱, c.產業類別
                FROM Company_Dim c
                JOIN Company_Tag_Map m ON c.證券代號 = m.證券代號
                JOIN Tag_Dim t ON m.Tag_ID = t.Tag_ID
                WHERE t.Tag_Name = ?
            """
            df = pd.read_sql_query(query, conn, params=(tag_name,))
        finally:
            self._return_connection(conn)
        return df
    
    def get_all_tags(self) -> List[str]:
        """取得所有標籤"""
        conn = self._get_connection()
        try:
            query = "SELECT DISTINCT Tag_Name FROM Tag_Dim ORDER BY Tag_Name"
            df = pd.read_sql_query(query, conn)
        finally:
            self._return_connection(conn)
        return df['Tag_Name'].tolist() if not df.empty else []

    # ================== 族群 (主題標籤) 進階查詢 ==================

    def get_tag_categories(self) -> pd.DataFrame:
        """取得所有標籤分類維度"""
        conn = self._get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT Category_ID, Category_Name, 排序 FROM Tag_Category ORDER BY 排序",
                conn
            )
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    def get_tags_with_category(self) -> pd.DataFrame:
        """取得所有族群標籤 (含分類與股票數量)"""
        conn = self._get_connection()
        try:
            query = """
                SELECT t.Tag_ID, t.Tag_Name, t.描述,
                       c.Category_Name AS 分類,
                       COUNT(m.證券代號) AS 股票數
                FROM Tag_Dim t
                LEFT JOIN Tag_Category c ON t.Category_ID = c.Category_ID
                LEFT JOIN Company_Tag_Map m ON t.Tag_ID = m.Tag_ID
                GROUP BY t.Tag_ID
                ORDER BY c.排序, 股票數 DESC
            """
            df = pd.read_sql_query(query, conn)
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    def get_tags_by_category(self, category_name: str) -> list:
        """取得某分類維度下的所有族群名稱"""
        conn = self._get_connection()
        try:
            query = """
                SELECT t.Tag_Name
                FROM Tag_Dim t
                JOIN Tag_Category c ON t.Category_ID = c.Category_ID
                WHERE c.Category_Name = ?
                ORDER BY t.Tag_Name
            """
            df = pd.read_sql_query(query, conn, params=(category_name,))
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df['Tag_Name'].tolist() if not df.empty else []

    def get_stocks_by_tag_detailed(self, tag_name: str) -> pd.DataFrame:
        """取得某族群的股票 (含關聯強度與資料來源)"""
        conn = self._get_connection()
        try:
            query = """
                SELECT c.證券代號, c.證券名稱, c.產業類別,
                       m.關聯強度, m.資料來源
                FROM Company_Dim c
                JOIN Company_Tag_Map m ON c.證券代號 = m.證券代號
                JOIN Tag_Dim t ON m.Tag_ID = t.Tag_ID
                WHERE t.Tag_Name = ?
                ORDER BY m.關聯強度 DESC
            """
            df = pd.read_sql_query(query, conn, params=(tag_name,))
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    def get_stocks_by_multiple_tags(self, tag_names: list, mode: str = "AND") -> pd.DataFrame:
        """
        多族群交叉篩選

        Args:
            tag_names: 族群名稱清單
            mode: 'AND' (同時屬於所有族群) 或 'OR' (屬於任一族群)
        """
        if not tag_names:
            return pd.DataFrame()

        conn = self._get_connection()
        try:
            placeholders = ','.join('?' * len(tag_names))

            if mode == "AND":
                query = f"""
                    SELECT c.證券代號, c.證券名稱, c.產業類別,
                           COUNT(DISTINCT t.Tag_Name) AS 命中族群數,
                           GROUP_CONCAT(DISTINCT t.Tag_Name) AS 所屬族群
                    FROM Company_Dim c
                    JOIN Company_Tag_Map m ON c.證券代號 = m.證券代號
                    JOIN Tag_Dim t ON m.Tag_ID = t.Tag_ID
                    WHERE t.Tag_Name IN ({placeholders})
                    GROUP BY c.證券代號
                    HAVING 命中族群數 = ?
                    ORDER BY 命中族群數 DESC
                """
                params = tag_names + [len(tag_names)]
            else:  # OR
                query = f"""
                    SELECT c.證券代號, c.證券名稱, c.產業類別,
                           COUNT(DISTINCT t.Tag_Name) AS 命中族群數,
                           GROUP_CONCAT(DISTINCT t.Tag_Name) AS 所屬族群
                    FROM Company_Dim c
                    JOIN Company_Tag_Map m ON c.證券代號 = m.證券代號
                    JOIN Tag_Dim t ON m.Tag_ID = t.Tag_ID
                    WHERE t.Tag_Name IN ({placeholders})
                    GROUP BY c.證券代號
                    ORDER BY 命中族群數 DESC
                """
                params = tag_names

            df = pd.read_sql_query(query, conn, params=params)
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    def get_tags_of_stock(self, stock_id: str) -> pd.DataFrame:
        """取得某股票所屬的所有族群 (含分類與強度)"""
        conn = self._get_connection()
        try:
            query = """
                SELECT t.Tag_Name AS 族群, c.Category_Name AS 分類,
                       m.關聯強度, m.資料來源
                FROM Company_Tag_Map m
                JOIN Tag_Dim t ON m.Tag_ID = t.Tag_ID
                LEFT JOIN Tag_Category c ON t.Category_ID = c.Category_ID
                WHERE m.證券代號 = ?
                ORDER BY m.關聯強度 DESC
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    def set_stock_tag(self, stock_id: str, tag_name: str,
                      strength: float = 0.9, source: str = "manual"):
        """手動為股票設定族群標籤 (含強度與來源)"""
        from datetime import datetime
        tag_id = self.add_tag(tag_name)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO Company_Tag_Map
                (證券代號, Tag_ID, 關聯強度, 資料來源, 更新時間)
                VALUES (?, ?, ?, ?, ?)
            ''', (stock_id, tag_id, strength, source, datetime.now().isoformat()))
            conn.commit()
        finally:
            self._return_connection(conn)

    def remove_stock_tag(self, stock_id: str, tag_name: str):
        """移除股票的族群標籤"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM Company_Tag_Map
                WHERE 證券代號 = ? AND Tag_ID = (SELECT Tag_ID FROM Tag_Dim WHERE Tag_Name = ?)
            ''', (stock_id, tag_name))
            conn.commit()
        finally:
            self._return_connection(conn)

    # ================== 月營收查詢 ==================

    def get_revenue_history(self, stock_id: str, limit: int = 24) -> pd.DataFrame:
        """取得股票的月營收歷史 (最近 N 個月)"""
        conn = self._get_connection()
        try:
            query = """
                SELECT 年月, 當月營收, 去年同月營收, 月增率, 年增率,
                       當月累計營收, 累計年增率
                FROM Revenue_Fact
                WHERE 證券代號 = ?
                ORDER BY 年月 DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(stock_id, limit))
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        if not df.empty:
            df = df.sort_values('年月').reset_index(drop=True)
        return df

    def get_latest_revenue(self, stock_id: str) -> dict:
        """取得最新一筆月營收"""
        df = self.get_revenue_history(stock_id, limit=1)
        if df.empty:
            return {}
        return df.iloc[-1].to_dict()

    def get_group_revenue_ranking(self, tag_name: str, by: str = "年增率") -> pd.DataFrame:
        """
        取得某族群內各股票的最新營收排名

        Args:
            tag_name: 族群名稱
            by: 排序依據 ('年增率', '月增率', '當月營收')
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT c.證券代號, c.證券名稱, r.年月,
                       r.當月營收, r.月增率, r.年增率, m.關聯強度
                FROM Company_Dim c
                JOIN Company_Tag_Map m ON c.證券代號 = m.證券代號
                JOIN Tag_Dim t ON m.Tag_ID = t.Tag_ID
                JOIN Revenue_Fact r ON c.證券代號 = r.證券代號
                WHERE t.Tag_Name = ?
                  AND r.年月 = (SELECT MAX(年月) FROM Revenue_Fact WHERE 證券代號 = c.證券代號)
                ORDER BY r.{} DESC
            """.format(by if by in ('年增率', '月增率', '當月營收') else '年增率')
            df = pd.read_sql_query(query, conn, params=(tag_name,))
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    # ================== 重大事件查詢 ==================

    def get_events_of_stock(self, stock_id: str) -> pd.DataFrame:
        """取得股票的重大事件 (法說會等)"""
        conn = self._get_connection()
        try:
            query = """
                SELECT 日期, 類型, 標題, 內容摘要, 來源連結
                FROM Catalyst_Event
                WHERE 證券代號 = ?
                ORDER BY 日期 DESC
            """
            df = pd.read_sql_query(query, conn, params=(stock_id,))
        except Exception:
            df = pd.DataFrame()
        finally:
            self._return_connection(conn)
        return df

    # ================== 系統狀態 ==================

    def get_data_freshness(self) -> dict:
        """
        取得資料新鮮度資訊。

        Returns:
            dict:
                latest_date: 最新有效資料日期 (YYYY-MM-DD)
                total_stocks: 總股票數
                total_industries: 總產業數
                latest_update_time: 最新更新時間
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 最新有效資料日期
            cursor.execute(
                "SELECT MAX(日期) FROM ETL_Status WHERE 驗證狀態='valid'"
            )
            latest_date = cursor.fetchone()[0]

            # 總股票數
            cursor.execute(
                "SELECT COUNT(*) FROM Company_Dim"
            )
            total_stocks = cursor.fetchone()[0]

            # 總產業數
            cursor.execute(
                "SELECT COUNT(DISTINCT 產業類別) FROM Company_Dim WHERE 產業類別 IS NOT NULL"
            )
            total_industries = cursor.fetchone()[0]

            # 最新更新時間
            cursor.execute(
                "SELECT MAX(更新時間) FROM ETL_Status WHERE 驗證狀態='valid'"
            )
            latest_update_time = cursor.fetchone()[0]

            self._return_connection(conn)
            return {
                'latest_date': latest_date,
                'total_stocks': total_stocks,
                'total_industries': total_industries,
                'latest_update_time': latest_update_time,
            }
        except Exception:
            return {
                'latest_date': None,
                'total_stocks': 0,
                'total_industries': 0,
                'latest_update_time': None,
            }

    def get_pending_fetch_count(self) -> int:
        """取得待抓取的日期數量"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM fetch_status WHERE status IN ('pending', 'error')"
            )
            count = cursor.fetchone()[0]
            self._return_connection(conn)
            return count
        except Exception:
            return 0


# 創建全局實例
data_query = StockDataQuery()
