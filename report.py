# report.py - 自動化報告生成模組
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from core.data import data_query
from core.analysis import StockAnalyzer, IndustryComparison, GroupAnalysis
from core.filters import PredefinedFilters


class ReportGenerator:
    """自動化報告生成器"""
    
    def __init__(self, title: str = "股市分析報告"):
        self.title = title
        self.report_date = datetime.now().strftime('%Y-%m-%d')
        self.sections = []
    
    def add_section(self, title: str, content: str):
        """添加報告段落"""
        self.sections.append({'title': title, 'content': content})
    
    def generate_market_summary(self) -> Dict:
        """
        生成市場摘要報告
        
        Returns:
            dict: 市場摘要
        """
        # 取得所有股票的最新價格
        all_stocks = data_query.get_all_stocks()
        stock_prices = {}
        
        for _, stock in all_stocks.iterrows():
            latest = data_query.get_latest_price(stock['證券代號'])
            if latest:
                stock_prices[stock['證券代號']] = latest
        
        if not stock_prices:
            return {'error': '沒有市場數據'}
        
        # 計算市場統計
        all_prices = list(stock_prices.values())
        all_changes = [s['漲跌'] for s in all_prices]
        
        gainers = [s for s in all_prices if s['漲跌'] > 0]
        losers = [s for s in all_prices if s['漲跌'] < 0]
        flat = [s for s in all_prices if s['漲跌'] == 0]
        
        # 計算成交量
        total_volume = sum(s['成交股數'] for s in all_prices)
        total_amount = sum(s['成交金額'] for s in all_prices)
        
        # 最大漲跌幅
        max_gainer = max(all_prices, key=lambda x: x['漲跌'])
        max_loser = min(all_prices, key=lambda x: x['漲跌'])
        
        # 成交量最大
        max_volume = max(all_prices, key=lambda x: x['成交股數'])
        
        return {
            '報告日期': self.report_date,
            '市場總覽': {
                '總股票數': len(stock_prices),
                '上漲股數': len(gainers),
                '下跌股數': len(losers),
                '平盤股數': len(flat),
                '上漲比例%': round(len(gainers) / len(all_prices) * 100, 2),
                '下跌比例%': round(len(losers) / len(all_prices) * 100, 2),
            },
            '成交量': {
                '總成交股數': total_volume,
                '總成交金額': total_amount,
            },
            '極端值': {
                '漲幅最大': {
                    '股票': max_gainer['證券代號'],
                    '名稱': max_gainer['證券名稱'],
                    '漲跌幅': max_gainer['漲跌'],
                },
                '跌幅最大': {
                    '股票': max_loser['證券代號'],
                    '名稱': max_loser['證券名稱'],
                    '漲跌幅': max_loser['漲跌'],
                },
                '成交量最大': {
                    '股票': max_volume['證券代號'],
                    '名稱': max_volume['證券名稱'],
                    '成交量': max_volume['成交股數'],
                },
            },
        }
    
    def generate_stock_report(self, stock_id: str) -> Dict:
        """
        生成單檔股票報告
        
        Returns:
            dict: 股票報告
        """
        # 取得股票資訊
        stock_info = data_query.get_stock_by_id(stock_id)
        if not stock_info:
            return {'error': f'找不到股票 {stock_id}'}
        
        # 取得最新價格
        latest = data_query.get_latest_price(stock_id)
        if not latest:
            return {'error': f'找不到股票 {stock_id} 的資料'}
        
        # 取得技術指標
        analyzer = StockAnalyzer(stock_id)
        indicators = analyzer.get_latest_indicators()
        
        # 取得基本面
        fundamentals = data_query.get_fundamentals(stock_id)
        
        # 取得營收
        revenue = data_query.get_revenue_history(stock_id, limit=12)
        
        # 取得族群
        current_tags = data_query.get_tags_of_stock(stock_id)
        
        # 計算技術面訊號
        technical_signals = {}
        
        rsi = indicators.get('RSI_14')
        if rsi is not None:
            if rsi >= 70:
                technical_signals['RSI'] = '超買'
            elif rsi <= 30:
                technical_signals['RSI'] = '超賣'
            else:
                technical_signals['RSI'] = '中性'
        
        macd = indicators.get('MACD')
        macd_sig = indicators.get('MACD_Signal')
        if macd is not None and macd_sig is not None:
            if macd > macd_sig:
                technical_signals['MACD'] = '偏多'
            else:
                technical_signals['MACD'] = '偏空'
        
        sma20 = indicators.get('SMA_20')
        sma50 = indicators.get('SMA_50')
        close = latest['收盤價']
        if sma20 is not None and sma50 is not None:
            if close > sma20 > sma50:
                technical_signals['均線'] = '多頭排列'
            elif close < sma20 < sma50:
                technical_signals['均線'] = '空頭排列'
            else:
                technical_signals['均線'] = '中性'
        
        return {
            '股票代號': stock_id,
            '股票名稱': stock_info.get('證券名稱'),
            '產業類別': stock_info.get('產業類別'),
            '報告日期': self.report_date,
            '最新收盤價': latest['收盤價'],
            '漲跌': latest['漲跌'],
            '成交量': latest['成交股數'],
            '成交金額': latest['成交金額'],
            '技術指標': indicators,
            '基本面': fundamentals,
            '營收資料': revenue,
            '技術面訊號': technical_signals,
            '所屬族群': current_tags['族群'].tolist() if not current_tags.empty else [],
        }
    
    def generate_industry_report(self, industry: str) -> Dict:
        """
        生成產業報告
        
        Returns:
            dict: 產業報告
        """
        # 取得產業資訊
        stocks = data_query.get_stocks_by_industry(industry)
        if stocks.empty:
            return {'error': f'找不到產業 {industry}'}
        
        # 取得產業快照
        snapshot = data_query.get_industry_snapshot(industry)
        
        # 計算產業績效
        stats = IndustryComparison.compare_industry_performance(industry)
        
        # 取得領頭股
        leaders = IndustryComparison.get_industry_leaders(industry, '成交金額', 10)
        
        # 取得漲跌幅排行
        gainers, losers = IndustryComparison.get_industry_gainers_losers(industry, 5)
        
        return {
            '產業': industry,
            '報告日期': self.report_date,
            '總股票數': len(stocks),
            '產業績效': stats,
            '領頭股': leaders,
            '漲幅前5': gainers,
            '跌幅前5': losers,
        }
    
    def generate_filter_report(self, filter_type: str) -> Dict:
        """
        生成篩選報告
        
        Returns:
            dict: 篩選報告
        """
        # 執行篩選
        if filter_type == "bullish":
            result = PredefinedFilters.bullish_signal()
        elif filter_type == "oversold":
            result = PredefinedFilters.oversold_stocks(30)
        elif filter_type == "overbought":
            result = PredefinedFilters.overbought_stocks(70)
        else:
            result = PredefinedFilters.high_volume_gainers(10000000, 0)
        
        return {
            '篩選類型': filter_type,
            '報告日期': self.report_date,
            '符合條件股票數': len(result),
            '結果': result,
        }
    
    def generate_weekly_report(self) -> Dict:
        """
        生成週報
        
        Returns:
            dict: 週報
        """
        # 市場摘要
        market = self.generate_market_summary()
        
        # 選漲超賣股票報告
        oversold = self.generate_filter_report("oversold")
        
        # 超買股票報告
        overbought = self.generate_filter_report("overbought")
        
        # 看漲信號報告
        bullish = self.generate_filter_report("bullish")
        
        return {
            '報告類型': '週報',
            '報告日期': self.report_date,
            '市場摘要': market,
            '超賣股票': oversold,
            '超買股票': overbought,
            '看漲信號': bullish,
        }
    
    def generate_monthly_report(self) -> Dict:
        """
        生成月報
        
        Returns:
            dict: 月報
        """
        # 市場摘要
        market = self.generate_market_summary()
        
        # 各產業報告
        all_industries = data_query.get_all_industries()
        industry_reports = {}
        
        for industry in all_industries[:10]:  # 限制為前 10 個產業
            try:
                industry_reports[industry] = self.generate_industry_report(industry)
            except:
                continue
        
        # 篩選報告
        oversold = self.generate_filter_report("oversold")
        overbought = self.generate_filter_report("overbought")
        bullish = self.generate_filter_report("bullish")
        
        return {
            '報告類型': '月報',
            '報告日期': self.report_date,
            '市場摘要': market,
            '產業報告': industry_reports,
            '超賣股票': oversold,
            '超買股票': overbought,
            '看漲信號': bullish,
        }
    
    def generate_report_to_csv(self, report: Dict, filename: str) -> str:
        """
        將報告保存為 CSV
        
        Args:
            report: 報告數據
            filename: 檔案名稱
        
        Returns:
            str: 保存的路徑
        """
        # 根據報告類型決定保存方式
        if '市場摘要' in report:
            # 市場摘要報告
            df = pd.DataFrame([report['市場摘要']])
            filepath = f"reports/{self.report_date}_{filename}.csv"
            df.to_csv(filepath, index=False)
        elif '結果' in report and not report['結果'].empty:
            # 篩選報告
            filepath = f"reports/{self.report_date}_{filename}.csv"
            report['結果'].to_csv(filepath, index=False)
        elif '股票代號' in report:
            # 單檔報告
            filepath = f"reports/{self.report_date}_{report['股票代號']}.csv"
            df = pd.DataFrame([report])
            df.to_csv(filepath, index=False)
        else:
            filepath = f"reports/{self.report_date}_{filename}.csv"
            df = pd.DataFrame([report])
            df.to_csv(filepath, index=False)
        
        return filepath
    
    def generate_report_to_html(self, report: Dict, filename: str) -> str:
        """
        將報告保存為 HTML
        
        Args:
            report: 報告數據
            filename: 檔案名稱
        
        Returns:
            str: 保存的路徑
        """
        import os
        
        # 確保目錄存在
        os.makedirs("reports", exist_ok=True)
        
        filepath = f"reports/{self.report_date}_{filename}.html"
        
        # 生成 HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.title} - {self.report_date}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #1f77b4; }}
                h2 {{ color: #ff7f0e; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>{self.title}</h1>
            <p>報告日期：{self.report_date}</p>
            
            <h2>市場摘要</h2>
            <p>總股票數：{report.get('市場摘要', {}).get('總股票數', 'N/A')}</p>
            <p>上漲股數：{report.get('市場摘要', {}).get('上漲股數', 'N/A')}</p>
            <p>下跌股數：{report.get('市場摘要', {}).get('下跌股數', 'N/A')}</p>
        </body>
        </html>
        """
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return filepath
