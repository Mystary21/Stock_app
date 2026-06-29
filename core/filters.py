# core/filters.py - 股票篩選引擎
import pandas as pd
import numpy as np
from typing import List, Optional, Callable
from core.data import data_query
from core.analysis import StockAnalyzer

class StockFilter:
    """股票篩選器 - 支持多條件篩選"""
    
    def __init__(self):
        self.conditions = []
    
    def add_condition(self, condition_func: Callable[[str], bool], name: str = None) -> 'StockFilter':
        """添加篩選條件 (支持 method chaining)"""
        self.conditions.append((condition_func, name or "Custom"))
        return self
    
    def filter_by_price_range(self, min_price: float = None, max_price: float = None) -> 'StockFilter':
        """按價格範圍篩選"""
        def condition(stock_id):
            latest = data_query.get_latest_price(stock_id)
            if not latest:
                return False
            price = latest['收盤價']
            if min_price and price < min_price:
                return False
            if max_price and price > max_price:
                return False
            return True
        
        self.add_condition(condition, f"Price Range: {min_price}-{max_price}")
        return self
    
    def filter_by_volume(self, min_volume: int = None) -> 'StockFilter':
        """按成交量篩選"""
        def condition(stock_id):
            latest = data_query.get_latest_price(stock_id)
            if not latest:
                return False
            return latest['成交股數'] >= (min_volume or 0)
        
        self.add_condition(condition, f"Min Volume: {min_volume}")
        return self
    
    def filter_by_change_percent(self, min_change: float = None, max_change: float = None) -> 'StockFilter':
        """按漲跌幅篩選"""
        def condition(stock_id):
            latest = data_query.get_latest_price(stock_id)
            if not latest:
                return False
            change = latest['漲跌']
            if min_change is not None and change < min_change:
                return False
            if max_change is not None and change > max_change:
                return False
            return True
        
        self.add_condition(condition, f"Change: {min_change}-{max_change}")
        return self
    
    def filter_by_industry(self, industry: str) -> 'StockFilter':
        """按產業篩選"""
        valid_stocks = set(data_query.get_stocks_by_industry(industry)['證券代號'].tolist())
        
        def condition(stock_id):
            return stock_id in valid_stocks
        
        self.add_condition(condition, f"Industry: {industry}")
        return self
    
    def filter_by_tag(self, tag_name: str) -> 'StockFilter':
        """按標籤篩選"""
        valid_stocks = set(data_query.get_stocks_by_tag(tag_name)['證券代號'].tolist())
        
        def condition(stock_id):
            return stock_id in valid_stocks
        
        self.add_condition(condition, f"Tag: {tag_name}")
        return self
    
    def filter_by_rsi(self, min_rsi: float = None, max_rsi: float = None) -> 'StockFilter':
        """按 RSI 指標篩選"""
        def condition(stock_id):
            analyzer = StockAnalyzer(stock_id)
            if analyzer.df.empty:
                return False
            
            latest_rsi = analyzer.get_latest_indicators().get('RSI_14')
            if latest_rsi is None:
                return False
            
            if min_rsi is not None and latest_rsi < min_rsi:
                return False
            if max_rsi is not None and latest_rsi > max_rsi:
                return False
            return True
        
        self.add_condition(condition, f"RSI: {min_rsi}-{max_rsi}")
    
    def filter_by_pe_ratio(self, min_pe: float = None, max_pe: float = None) -> 'StockFilter':
        """按 P/E 比率篩選"""
        def condition(stock_id):
            try:
                fundamentals = data_query.get_fundamentals(stock_id)
                if fundamentals.empty:
                    return False
                pe = fundamentals.iloc[0].get('P/E', None)
                if pe is None:
                    return False
                if min_pe is not None and pe < min_pe:
                    return False
                if max_pe is not None and pe > max_pe:
                    return False
                return True
            except:
                return False
        
        self.add_condition(condition, f"P/E: {min_pe}-{max_pe}")
        return self
    
    def filter_by_roe(self, min_roe: float = None, max_roe: float = None) -> 'StockFilter':
        """按 ROE 篩選"""
        def condition(stock_id):
            try:
                fundamentals = data_query.get_fundamentals(stock_id)
                if fundamentals.empty:
                    return False
                roe = fundamentals.iloc[0].get('ROE(%)', None)
                if roe is None:
                    return False
                if min_roe is not None and roe < min_roe:
                    return False
                if max_roe is not None and roe > max_roe:
                    return False
                return True
            except:
                return False
        
        self.add_condition(condition, f"ROE: {min_roe}-{max_roe}")
        return self
    
    def filter_by_market_cap(self, min_cap: float = None, max_cap: float = None) -> 'StockFilter':
        """按市值篩選"""
        def condition(stock_id):
            try:
                fundamentals = data_query.get_fundamentals(stock_id)
                if fundamentals.empty:
                    return False
                bps = fundamentals.iloc[0].get('BPS', None)
                latest_price = data_query.get_latest_price(stock_id)
                if bps is None or latest_price is None:
                    return False
                market_cap = latest_price['收盤價'] * bps
                if min_cap is not None and market_cap < min_cap:
                    return False
                if max_cap is not None and market_cap > max_cap:
                    return False
                return True
            except:
                return False
        
        self.add_condition(condition, f"Market Cap: {min_cap}-{max_cap}")
        return self
    
    def filter_by_dividend_yield(self, min_yield: float = None, max_yield: float = None) -> 'StockFilter':
        """按殖利率篩選"""
        def condition(stock_id):
            try:
                fundamentals = data_query.get_fundamentals(stock_id)
                if fundamentals.empty:
                    return False
                pe = fundamentals.iloc[0].get('P/E', None)
                if pe is None:
                    return False
                # 簡易殖利率估算
                dividend_yield = 100 / pe if pe > 0 else 0
                if min_yield is not None and dividend_yield < min_yield:
                    return False
                if max_yield is not None and dividend_yield > max_yield:
                    return False
                return True
            except:
                return False
        
        self.add_condition(condition, f"Dividend Yield: {min_yield}-{max_yield}")
        return self
    
    def filter_with_batch(self, stock_ids: List[str]) -> List[str]:
        """批量篩選 - 一次性篩選所有股票"""
        if not self.conditions:
            return stock_ids
        
        results = []
        for stock_id in stock_ids:
            try:
                matches = all(cond_func(stock_id) for cond_func, _ in self.conditions)
                if matches:
                    results.append(stock_id)
            except:
                continue
        
        return results
        return self
    
    def filter_by_moving_average_cross(self) -> 'StockFilter':
        """黃金交叉篩選 (SMA_20 > SMA_50)"""
        def condition(stock_id):
            analyzer = StockAnalyzer(stock_id)
            if analyzer.df.empty:
                return False
            
            indicators = analyzer.get_latest_indicators()
            sma_20 = indicators.get('SMA_20')
            sma_50 = indicators.get('SMA_50')
            
            if sma_20 is None or sma_50 is None:
                return False
            
            return sma_20 > sma_50
        
        self.add_condition(condition, "Golden Cross (SMA20 > SMA50)")
        return self
    
    def filter_by_price_above_ma(self, ma_days: int = 20) -> 'StockFilter':
        """價格高於 N 日均線篩選"""
        def condition(stock_id):
            analyzer = StockAnalyzer(stock_id)
            if analyzer.df.empty:
                return False
            
            latest = analyzer.df.iloc[-1]
            close = latest['收盤價']
            
            if ma_days == 20:
                ma = latest.get('SMA_20')
            elif ma_days == 50:
                ma = latest.get('SMA_50')
            elif ma_days == 200:
                ma = latest.get('SMA_200')
            else:
                return False
            
            if ma is None or pd.isna(ma):
                return False
            
            return close > ma
        
        self.add_condition(condition, f"Price > SMA{ma_days}")
        return self
    
    def execute(self) -> pd.DataFrame:
        """執行篩選，返回符合所有條件的股票"""
        all_stocks = data_query.get_all_stocks()
        stock_ids = all_stocks['證券代號'].tolist()
        
        result_stocks = []
        
        for stock_id in stock_ids:
            # 所有條件都必須滿足
            if all(cond(stock_id) for cond, _ in self.conditions):
                stock_info = data_query.get_stock_by_id(stock_id)
                latest = data_query.get_latest_price(stock_id)
                
                if stock_info and latest:
                    result_stocks.append({
                        '證券代號': stock_id,
                        '證券名稱': stock_info.get('證券名稱'),
                        '產業類別': stock_info.get('產業類別'),
                        '收盤價': latest['收盤價'],
                        '漲跌': latest['漲跌'],
                        '成交金額': latest['成交金額'],
                    })
        
        return pd.DataFrame(result_stocks) if result_stocks else pd.DataFrame()


class PredefinedFilters:
    """預定義的篩選組合"""
    
    @staticmethod
    def bullish_signal() -> pd.DataFrame:
        """看漲信號篩選：黃金交叉 + 價格高於 SMA20"""
        return (StockFilter()
                .filter_by_moving_average_cross()
                .filter_by_price_above_ma(20)
                .execute())
    
    @staticmethod
    def oversold_stocks(threshold: float = 30) -> pd.DataFrame:
        """超賣股票篩選 (RSI < 30)"""
        return (StockFilter()
                .filter_by_rsi(max_rsi=threshold)
                .execute())
    
    @staticmethod
    def overbought_stocks(threshold: float = 70) -> pd.DataFrame:
        """超買股票篩選 (RSI > 70)"""
        return (StockFilter()
                .filter_by_rsi(min_rsi=threshold)
                .execute())
    
    @staticmethod
    def high_volume_gainers(min_volume: int = 10000000, min_change: float = 0) -> pd.DataFrame:
        """成交量大漲股篩選"""
        return (StockFilter()
                .filter_by_volume(min_volume)
                .filter_by_change_percent(min_change=min_change)
                .execute())
    
    @staticmethod
    def industry_leaders(industry: str, min_volume: int = 5000000) -> pd.DataFrame:
        """產業領頭股篩選"""
        return (StockFilter()
                .filter_by_industry(industry)
                .filter_by_volume(min_volume)
                .execute())


# Utility function
def compare_filters(filter1_result: pd.DataFrame, filter2_result: pd.DataFrame) -> dict:
    """比較兩個篩選結果"""
    set1 = set(filter1_result['證券代號'].tolist())
    set2 = set(filter2_result['證券代號'].tolist())
    
    return {
        'Filter1 Only': list(set1 - set2),
        'Filter2 Only': list(set2 - set1),
        'Both': list(set1 & set2),
        'Filter1 Count': len(set1),
        'Filter2 Count': len(set2),
    }
