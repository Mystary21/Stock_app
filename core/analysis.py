# core/analysis.py - 技術指標與族群分析
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from core.data import data_query

class TechnicalAnalysis:
    """技術指標分析類"""
    
    @staticmethod
    def moving_average(prices: pd.Series, window: int = 20) -> pd.Series:
        """簡單移動平均 (SMA)"""
        return prices.rolling(window=window).mean()
    
    @staticmethod
    def exponential_moving_average(prices: pd.Series, window: int = 20) -> pd.Series:
        """指數移動平均 (EMA)"""
        return prices.ewm(span=window, adjust=False).mean()
    
    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACD 指標 (動量指標)
        
        Returns:
            (MACD線, Signal線, Histogram)
        """
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
        """
        相對強度指標 (RSI)
        
        RSI = 100 - (100 / (1 + RS))
        其中 RS = 平均上漲幅度 / 平均下跌幅度
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def bollinger_bands(prices: pd.Series, window: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        布林帶 (Bollinger Bands)
        
        Returns:
            (上軌, 中軌, 下軌)
        """
        middle_band = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        
        upper_band = middle_band + (std * num_std)
        lower_band = middle_band - (std * num_std)
        
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """
        平均真實波幅 (Average True Range)
        
        用於衡量波動性
        """
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()
        
        return atr
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                  k_window: int = 14, d_window: int = 3) -> Tuple[pd.Series, pd.Series]:
        """
        隨機指標 (Stochastic Oscillator)
        
        Returns:
            (%K, %D)
        """
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return k_percent, d_percent
    
    @staticmethod
    def calculate_returns(prices: pd.Series, period: int = 1) -> pd.Series:
        """計算報酬率"""
        return prices.pct_change(periods=period) * 100
    
    @staticmethod
    def calculate_volatility(prices: pd.Series, window: int = 20) -> pd.Series:
        """計算波動率 (標準差)"""
        returns = prices.pct_change()
        return returns.rolling(window=window).std() * 100


class StockAnalyzer:
    """單檔股票分析"""
    
    def __init__(self, stock_id: str):
        self.stock_id = stock_id
        self.df = data_query.get_stock_price_history(stock_id)
        self.ta = TechnicalAnalysis()
        
        if not self.df.empty:
            self._calculate_indicators()
    
    def _calculate_indicators(self):
        """計算所有技術指標"""
        close = self.df['收盤價']
        high = self.df['最高價']
        low = self.df['最低價']
        
        # SMA
        self.df['SMA_20'] = self.ta.moving_average(close, 20)
        self.df['SMA_50'] = self.ta.moving_average(close, 50)
        self.df['SMA_200'] = self.ta.moving_average(close, 200)
        
        # EMA
        self.df['EMA_12'] = self.ta.exponential_moving_average(close, 12)
        self.df['EMA_26'] = self.ta.exponential_moving_average(close, 26)
        
        # MACD
        macd, signal, hist = self.ta.macd(close)
        self.df['MACD'] = macd
        self.df['MACD_Signal'] = signal
        self.df['MACD_Hist'] = hist
        
        # RSI
        self.df['RSI_14'] = self.ta.rsi(close, 14)
        
        # 布林帶
        upper, middle, lower = self.ta.bollinger_bands(close, 20, 2.0)
        self.df['BB_Upper'] = upper
        self.df['BB_Middle'] = middle
        self.df['BB_Lower'] = lower
        
        # ATR
        self.df['ATR_14'] = self.ta.atr(high, low, close, 14)
        
        # Stochastic
        k, d = self.ta.stochastic(high, low, close)
        self.df['Stoch_K'] = k
        self.df['Stoch_D'] = d
        
        # 報酬率與波動率
        self.df['Daily_Return%'] = self.ta.calculate_returns(close, 1)
        self.df['Volatility'] = self.ta.calculate_volatility(close, 20)
    
    def get_latest_indicators(self) -> dict:
        """取得最新的技術指標"""
        if self.df.empty:
            return {}
        
        latest = self.df.iloc[-1]
        
        return {
            '日期': str(latest['日期'].date()),
            '收盤價': round(latest['收盤價'], 2),
            '漲跌': round(latest['漲跌'], 2),
            'SMA_20': round(latest['SMA_20'], 2) if pd.notna(latest['SMA_20']) else None,
            'SMA_50': round(latest['SMA_50'], 2) if pd.notna(latest['SMA_50']) else None,
            'RSI_14': round(latest['RSI_14'], 2) if pd.notna(latest['RSI_14']) else None,
            'MACD': round(latest['MACD'], 4) if pd.notna(latest['MACD']) else None,
            'MACD_Signal': round(latest['MACD_Signal'], 4) if pd.notna(latest['MACD_Signal']) else None,
            'Volatility': round(latest['Volatility'], 2) if pd.notna(latest['Volatility']) else None,
            'Stoch_K': round(latest['Stoch_K'], 2) if pd.notna(latest['Stoch_K']) else None,
        }
    
    def get_analysis_summary(self) -> dict:
        """取得分析總結"""
        if self.df.empty:
            return {}
        
        latest = self.df.iloc[-1]
        price_history = self.df['收盤價'].tail(20)
        
        return {
            '股票代號': self.stock_id,
            '股票名稱': data_query.get_stock_by_id(self.stock_id).get('證券名稱', 'N/A'),
            '最新收盤': round(latest['收盤價'], 2),
            '20日最高': round(price_history.max(), 2),
            '20日最低': round(price_history.min(), 2),
            '20日均價': round(price_history.mean(), 2),
            '波動率': round(latest['Volatility'], 2) if pd.notna(latest['Volatility']) else 0,
            'RSI': round(latest['RSI_14'], 2) if pd.notna(latest['RSI_14']) else 0,
        }


class IndustryComparison:
    """產業族群分析"""
    
    @staticmethod
    def get_industry_leaders(industry: str, metric: str = '成交金額', top_n: int = 10) -> pd.DataFrame:
        """
        取得某產業的領導企業
        
        Args:
            industry: 產業名稱
            metric: 指標 ('成交金額', '成交股數', '收盤價', '漲跌')
            top_n: 取前幾名
        
        Returns:
            排序後的 DataFrame
        """
        snapshot = data_query.get_industry_snapshot(industry)
        
        if snapshot.empty:
            return pd.DataFrame()
        
        # 按指標排序
        if metric == '成交金額':
            snapshot = snapshot.sort_values('成交金額', ascending=False)
        elif metric == '成交股數':
            snapshot = snapshot.sort_values('成交股數', ascending=False)
        elif metric == '收盤價':
            snapshot = snapshot.sort_values('收盤價', ascending=False)
        elif metric == '漲跌':
            snapshot = snapshot.sort_values('漲跌', ascending=False)
        
        return snapshot.head(top_n)
    
    @staticmethod
    def compare_industry_performance(industry: str) -> dict:
        """比較產業內各股票的表現"""
        snapshot = data_query.get_industry_snapshot(industry)
        
        if snapshot.empty:
            return {}
        
        return {
            '平均收盤價': round(snapshot['收盤價'].mean(), 2),
            '平均漲跌': round(snapshot['漲跌'].mean(), 2),
            '平均成交金額': round(snapshot['成交金額'].mean(), 2),
            '上漲股數': len(snapshot[snapshot['漲跌'] > 0]),
            '下跌股數': len(snapshot[snapshot['漲跌'] < 0]),
            '平盤股數': len(snapshot[snapshot['漲跌'] == 0]),
            '總股票數': len(snapshot),
        }
    
    @staticmethod
    def get_sector_correlation(industry: str, start_date: Optional[str] = None, 
                             end_date: Optional[str] = None) -> pd.DataFrame:
        """
        計算產業內股票的價格相關性
        
        Returns:
            相關係數矩陣
        """
        stocks_df = data_query.get_stocks_by_industry(industry)
        stock_ids = stocks_df['證券代號'].tolist()
        
        # 取得所有股票的價格數據
        price_data = {}
        for stock_id in stock_ids:
            df = data_query.get_stock_price_history(stock_id, start_date, end_date)
            if not df.empty:
                price_data[stock_id] = df['收盤價'].values
        
        if not price_data:
            return pd.DataFrame()
        
        # 構建相關係數矩陣
        prices_df = pd.DataFrame(price_data)
        correlation = prices_df.corr()
        
        return correlation
    
    @staticmethod
    def get_industry_gainers_losers(industry: str, top_n: int = 5) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        取得產業內的漲幅最大與跌幅最大的股票
        
        Returns:
            (Gainers DataFrame, Losers DataFrame)
        """
        snapshot = data_query.get_industry_snapshot(industry)
        
        if snapshot.empty:
            return pd.DataFrame(), pd.DataFrame()
        
        gainers = snapshot.nlargest(top_n, '漲跌')
        losers = snapshot.nsmallest(top_n, '漲跌')
        
        return gainers, losers


class GroupAnalysis:
    """主題族群分析 (基於 Tag / 營收 / 事件)"""

    @staticmethod
    def get_group_overview() -> pd.DataFrame:
        """所有族群總覽 (含分類與股票數)"""
        return data_query.get_tags_with_category()

    @staticmethod
    def get_group_members(tag_name: str) -> pd.DataFrame:
        """取得族群成員 (含關聯強度)"""
        return data_query.get_stocks_by_tag_detailed(tag_name)

    @staticmethod
    def cross_filter(tag_names: list, mode: str = "AND") -> pd.DataFrame:
        """多族群交叉篩選"""
        return data_query.get_stocks_by_multiple_tags(tag_names, mode)

    @staticmethod
    def group_revenue_performance(tag_name: str) -> dict:
        """
        族群整體營收表現 (彙總族群內所有股票最新月營收)
        """
        ranking = data_query.get_group_revenue_ranking(tag_name, by='年增率')

        if ranking.empty:
            return {}

        valid_yoy = ranking['年增率'].dropna()
        valid_mom = ranking['月增率'].dropna()

        return {
            '族群': tag_name,
            '成員數': len(ranking),
            '有營收資料數': len(valid_yoy),
            '平均年增率': round(valid_yoy.mean(), 2) if not valid_yoy.empty else None,
            '平均月增率': round(valid_mom.mean(), 2) if not valid_mom.empty else None,
            '年增成長家數': int((valid_yoy > 0).sum()),
            '年增衰退家數': int((valid_yoy < 0).sum()),
            '族群總營收(千元)': round(ranking['當月營收'].sum(), 0),
            '最新月份': ranking['年月'].iloc[0] if not ranking.empty else None,
        }

    @staticmethod
    def group_price_performance(tag_name: str) -> pd.DataFrame:
        """
        族群內各股票的股價表現 (最新收盤、漲跌、近20日報酬)
        """
        members = data_query.get_stocks_by_tag_detailed(tag_name)
        if members.empty:
            return pd.DataFrame()

        results = []
        for _, m in members.iterrows():
            stock_id = m['證券代號']
            df = data_query.get_stock_price_history(stock_id)
            if df.empty:
                continue

            latest = df.iloc[-1]
            # 近20日報酬
            ret_20d = None
            if len(df) >= 21:
                old_price = df.iloc[-21]['收盤價']
                if old_price and old_price > 0:
                    ret_20d = round((latest['收盤價'] - old_price) / old_price * 100, 2)

            results.append({
                '證券代號': stock_id,
                '證券名稱': m['證券名稱'],
                '關聯強度': m['關聯強度'],
                '收盤價': round(latest['收盤價'], 2) if pd.notna(latest['收盤價']) else None,
                '漲跌': round(latest['漲跌'], 2) if pd.notna(latest['漲跌']) else None,
                '近20日報酬%': ret_20d,
                '成交金額': latest['成交金額'],
            })

        return pd.DataFrame(results)

    @staticmethod
    def compare_groups(tag_names: list) -> pd.DataFrame:
        """
        比較多個族群的整體表現 (營收 + 股價)
        """
        rows = []
        for tag in tag_names:
            rev = GroupAnalysis.group_revenue_performance(tag)
            price = GroupAnalysis.group_price_performance(tag)

            avg_ret = None
            if not price.empty and '近20日報酬%' in price.columns:
                valid = price['近20日報酬%'].dropna()
                avg_ret = round(valid.mean(), 2) if not valid.empty else None

            rows.append({
                '族群': tag,
                '成員數': rev.get('成員數', 0),
                '平均年增率%': rev.get('平均年增率'),
                '年增成長家數': rev.get('年增成長家數'),
                '平均近20日報酬%': avg_ret,
            })

        return pd.DataFrame(rows)

