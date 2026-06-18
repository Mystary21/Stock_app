# backtesting/engine.py - 簡易回測引擎
import pandas as pd
import numpy as np
from typing import Callable, Optional, List, Dict
from core.data import data_query
from core.analysis import StockAnalyzer

class BacktestEngine:
    """簡易的股票策略回測引擎"""
    
    def __init__(self, stock_id: str, start_date: Optional[str] = None, 
                 end_date: Optional[str] = None, initial_capital: float = 100000):
        """
        初始化回測引擎
        
        Args:
            stock_id: 股票代號
            start_date: 回測開始日期 (YYYY-MM-DD)
            end_date: 回測結束日期 (YYYY-MM-DD)
            initial_capital: 初始資本額
        """
        self.stock_id = stock_id
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        
        # 取得股票數據
        self.df = data_query.get_stock_price_history(stock_id, start_date, end_date)
        
        if self.df.empty:
            raise ValueError(f"無法取得 {stock_id} 的數據")
        
        # 計算技術指標
        self._prepare_data()
        
        # 回測結果
        self.trades = []
        self.daily_returns = []
        self.portfolio_values = []
    
    def _prepare_data(self):
        """準備回測數據（計算指標）"""
        analyzer = StockAnalyzer(self.stock_id)
        
        # 複製技術指標
        for col in ['SMA_20', 'SMA_50', 'RSI_14', 'MACD', 'MACD_Signal']:
            if col in analyzer.df.columns:
                self.df[col] = analyzer.df[col].values
    
    def add_signal(self, signal_func: Callable[[pd.DataFrame, int], Dict]) -> 'BacktestEngine':
        """
        添加交易信號函數
        
        signal_func 應該返回 {'action': 'BUY'|'SELL'|'HOLD', 'confidence': 0-1}
        """
        self.signal_func = signal_func
        return self
    
    def backtest(self) -> Dict:
        """執行回測"""
        position = None  # None: 無持倉, 'LONG': 持多
        entry_price = None
        entry_date = None
        
        portfolio_value = self.initial_capital
        cash = self.initial_capital
        shares = 0
        
        for i in range(len(self.df)):
            row = self.df.iloc[i]
            current_price = row['收盤價']
            current_date = row['日期']
            
            # 生成信號
            signal = self.signal_func(self.df, i)
            action = signal.get('action', 'HOLD')
            
            # 執行交易邏輯
            if action == 'BUY' and position is None:
                # 買進：用所有現金買入
                shares = int(cash / current_price)
                if shares > 0:
                    cash -= shares * current_price
                    position = 'LONG'
                    entry_price = current_price
                    entry_date = current_date
                    
                    self.trades.append({
                        '日期': current_date,
                        '操作': 'BUY',
                        '價格': current_price,
                        '股數': shares,
                        '成本': shares * current_price,
                    })
            
            elif action == 'SELL' and position == 'LONG':
                # 賣出：賣掉所有持股
                proceeds = shares * current_price
                profit = proceeds - (entry_price * shares)
                profit_pct = (profit / (entry_price * shares)) * 100 if entry_price else 0
                
                cash += proceeds
                
                self.trades.append({
                    '日期': current_date,
                    '操作': 'SELL',
                    '價格': current_price,
                    '股數': shares,
                    '收益': proceeds,
                    '獲利': profit,
                    '獲利率%': profit_pct,
                    '持倉天數': (current_date - entry_date).days,
                })
                
                position = None
                shares = 0
                entry_price = None
            
            # 計算組合價值
            portfolio_value = cash + (shares * current_price if shares > 0 else 0)
            self.portfolio_values.append({
                '日期': current_date,
                '現金': cash,
                '持股價值': shares * current_price,
                '組合總值': portfolio_value,
            })
        
        # 如果還持倉，強制賣出
        if position == 'LONG' and len(self.df) > 0:
            final_price = self.df.iloc[-1]['收盤價']
            final_date = self.df.iloc[-1]['日期']
            proceeds = shares * final_price
            profit = proceeds - (entry_price * shares)
            profit_pct = (profit / (entry_price * shares)) * 100 if entry_price else 0
            
            self.trades.append({
                '日期': final_date,
                '操作': 'SELL (强平)',
                '價格': final_price,
                '股數': shares,
                '收益': proceeds,
                '獲利': profit,
                '獲利率%': profit_pct,
                '持倉天數': (final_date - entry_date).days,
            })
        
        return self._calculate_metrics()
    
    def _calculate_metrics(self) -> Dict:
        """計算回測指標"""
        if not self.portfolio_values:
            return {}
        
        portfolio_df = pd.DataFrame(self.portfolio_values)
        initial_value = self.initial_capital
        final_value = portfolio_df.iloc[-1]['組合總值']
        
        # 總報酬率
        total_return = ((final_value - initial_value) / initial_value) * 100
        
        # 最大虧損 (Drawdown)
        portfolio_series = portfolio_df['組合總值']
        cummax = portfolio_series.cummax()
        drawdown = (portfolio_series - cummax) / cummax * 100
        max_drawdown = drawdown.min()
        
        # 交易統計
        trades_df = pd.DataFrame(self.trades)
        if not trades_df.empty:
            sell_trades = trades_df[trades_df['操作'].str.contains('SELL', na=False)]
            win_trades = len(sell_trades[sell_trades['獲利'] > 0]) if not sell_trades.empty else 0
            total_trades = len(sell_trades)
            win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        else:
            win_trades = 0
            total_trades = 0
            win_rate = 0
        
        # 年化報酬率 (假設 252 個交易日)
        days = (self.df.iloc[-1]['日期'] - self.df.iloc[0]['日期']).days
        annual_return = (total_return / max(days, 1) * 365) if days > 0 else 0
        
        return {
            '股票代號': self.stock_id,
            '初始資本': initial_value,
            '最終價值': round(final_value, 2),
            '總報酬率%': round(total_return, 2),
            '年化報酬率%': round(annual_return, 2),
            '最大虧損%': round(max_drawdown, 2),
            '總交易次數': total_trades,
            '獲利交易': win_trades,
            '虧損交易': total_trades - win_trades,
            '勝率%': round(win_rate, 2),
            '回測天數': days,
            '交易清單': self.trades,
            '組合淨值曲線': portfolio_df,
        }


# 預定義策略
class StrategyLibrary:
    """策略函數庫"""
    
    @staticmethod
    def sma_crossover_strategy(df: pd.DataFrame, current_idx: int) -> Dict:
        """
        簡單移動平均線交叉策略
        
        買進信號：SMA20 > SMA50
        賣出信號：SMA20 < SMA50
        """
        if current_idx < 50:  # 需要足夠的數據計算 SMA50
            return {'action': 'HOLD', 'confidence': 0}
        
        current_row = df.iloc[current_idx]
        sma_20 = current_row.get('SMA_20')
        sma_50 = current_row.get('SMA_50')
        
        if pd.isna(sma_20) or pd.isna(sma_50):
            return {'action': 'HOLD', 'confidence': 0}
        
        if sma_20 > sma_50:
            return {'action': 'BUY', 'confidence': 0.7}
        elif sma_20 < sma_50:
            return {'action': 'SELL', 'confidence': 0.7}
        else:
            return {'action': 'HOLD', 'confidence': 0}
    
    @staticmethod
    def rsi_strategy(df: pd.DataFrame, current_idx: int) -> Dict:
        """
        RSI 超買超賣策略
        
        買進信號：RSI < 30 (超賣)
        賣出信號：RSI > 70 (超買)
        """
        if current_idx < 14:
            return {'action': 'HOLD', 'confidence': 0}
        
        current_row = df.iloc[current_idx]
        rsi = current_row.get('RSI_14')
        
        if pd.isna(rsi):
            return {'action': 'HOLD', 'confidence': 0}
        
        if rsi < 30:
            return {'action': 'BUY', 'confidence': 0.8}
        elif rsi > 70:
            return {'action': 'SELL', 'confidence': 0.8}
        else:
            return {'action': 'HOLD', 'confidence': 0}
    
    @staticmethod
    def macd_strategy(df: pd.DataFrame, current_idx: int) -> Dict:
        """
        MACD 策略
        
        買進信號：MACD > Signal Line
        賣出信號：MACD < Signal Line
        """
        if current_idx < 26:
            return {'action': 'HOLD', 'confidence': 0}
        
        current_row = df.iloc[current_idx]
        macd = current_row.get('MACD')
        signal = current_row.get('MACD_Signal')
        
        if pd.isna(macd) or pd.isna(signal):
            return {'action': 'HOLD', 'confidence': 0}
        
        if macd > signal:
            return {'action': 'BUY', 'confidence': 0.7}
        elif macd < signal:
            return {'action': 'SELL', 'confidence': 0.7}
        else:
            return {'action': 'HOLD', 'confidence': 0}
