# portfolio.py - 投資組合管理模組
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from core.data import data_query
from core.analysis import StockAnalyzer


class Portfolio:
    """投資組合管理"""
    
    def __init__(self, stock_ids: List[str], weights: Optional[List[float]] = None,
                 initial_capital: float = 100000):
        """
        初始化投資組合
        
        Args:
            stock_ids: 股票代號列表
            weights: 各股票權重 (預設均等分配)
            initial_capital: 初始資本額
        """
        if not stock_ids:
            raise ValueError("股票列表不能為空")
        
        self.stock_ids = stock_ids
        self.initial_capital = initial_capital
        
        if weights is None:
            self.weights = [1.0 / len(stock_ids)] * len(stock_ids)
        else:
            # 驗證權重總和為 1
            total_weight = sum(weights)
            if abs(total_weight - 1.0) > 0.01:
                raise ValueError("權重總和必須為 1")
            self.weights = weights
        
        self.stock_names = []
        self.stock_prices = {}
        self.stock_weights = []
        
        # 取得各股票資訊
        for i, stock_id in enumerate(stock_ids):
            info = data_query.get_stock_by_id(stock_id)
            if info:
                self.stock_names.append(info.get('證券名稱', stock_id))
            else:
                self.stock_names.append(stock_id)
            
            latest = data_query.get_latest_price(stock_id)
            if latest:
                self.stock_prices[stock_id] = {
                    '價格': latest['收盤價'],
                    '日期': latest['日期'],
                }
            else:
                self.stock_prices[stock_id] = {'價格': None, '日期': None}
            
            self.stock_weights.append(self.weights[i])
        
    def get_portfolio_value(self) -> Dict:
        """
        取得投資組合總值
        
        Returns:
            dict: 包含總值、各股票價值、現金等資訊
        """
        total_value = 0
        stock_values = []
        
        for i, stock_id in enumerate(self.stock_ids):
            price = self.stock_prices[stock_id]['價格']
            if price:
                value = price * self.weights[i]
                total_value += value
                stock_values.append({
                    '股票': self.stock_names[i],
                    '代號': stock_id,
                    '價格': price,
                    '價值': value,
                    '權重%': round(self.weights[i] * 100, 2),
                })
            else:
                stock_values.append({
                    '股票': self.stock_names[i],
                    '代號': stock_id,
                    '價格': None,
                    '價值': 0,
                    '權重%': round(self.weights[i] * 100, 2),
                })
        
        return {
            '總值': round(total_value, 2),
            '初始資本': self.initial_capital,
            '股票數': len(self.stock_ids),
            '股票列表': stock_values,
        }
    
    def get_allocation_summary(self) -> Dict:
        """
        取得投資分配摘要
        
        Returns:
            dict: 包含各股票權重、平均價格等
        """
        avg_price = sum(p['價格'] for p in self.stock_prices.values() if p['價格']) / len(self.stock_prices)
        
        return {
            '股票數': len(self.stock_ids),
            '初始資本': self.initial_capital,
            '平均價格': round(avg_price, 2),
            '權重分配': {
                '股票': self.stock_names,
                '代號': self.stock_ids,
                '權重': [round(w * 100, 2) for w in self.weights],
            },
        }
    
    def rebalance(self, new_weights: List[float] = None) -> Dict:
        """
        重新平衡投資組合
        
        Args:
            new_weights: 新的權重列表 (預設均等分配)
        
        Returns:
            dict: 重新平衡結果
        """
        if new_weights:
            total_weight = sum(new_weights)
            if abs(total_weight - 1.0) > 0.01:
                raise ValueError("權重總和必須為 1")
            self.weights = new_weights
        
        current_value = self.get_portfolio_value()
        
        return {
            '操作': '重新平衡',
            '股票數': len(self.stock_ids),
            '新資本': current_value['總值'],
            '股票列表': current_value['股票列表'],
            '新權重': [round(w * 100, 2) for w in self.weights],
        }
    
    def get_performance(self, start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> Dict:
        """
        取得投資組合績效
        
        Returns:
            dict: 績效指標
        """
        if not self.stock_prices:
            return {'error': '沒有股票數據'}
        
        # 取得所有股票的價格歷史
        price_data = {}
        for stock_id in self.stock_ids:
            df = data_query.get_stock_price_history(stock_id, start_date, end_date)
            if not df.empty:
                price_data[stock_id] = df['收盤價'].values
        
        if not price_data:
            return {'error': '沒有足夠的歷史數據'}
        
        # 計算組合報酬率
        combined_returns = []
        for date_idx in range(min(len(df) for df in [pd.DataFrame(d) for d in price_data.values()])):
            prices = []
            for stock_id, prices_list in price_data.items():
                if date_idx < len(prices_list):
                    prices.append(prices_list[date_idx])
            
            if len(prices) > 0:
                weighted_return = sum(w * (p - prices[0]) / prices[0] * 100 
                                     for w, p in zip(self.weights, prices))
                combined_returns.append(weighted_return)
        
        if not combined_returns:
            return {'error': '無法計算績效'}
        
        # 計算績效指標
        combined_series = pd.Series(combined_returns)
        mean_return = combined_series.mean()
        std_return = combined_series.std()
        max_return = combined_series.max()
        min_return = combined_series.min()
        
        # 最大回撤
        cummax = combined_series.cummax()
        drawdown = (combined_series - cummax) / cummax * 100
        max_drawdown = drawdown.min()
        
        return {
            '平均報酬率%': round(mean_return, 2),
            '最大報酬率%': round(max_return, 2),
            '最小報酬率%': round(min_return, 2),
            '標準差%': round(std_return, 2),
            '最大回撤%': round(max_drawdown, 2),
            '回測天數': len(combined_returns),
        }
