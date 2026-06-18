#!/usr/bin/env python3
"""
股市觀察工具 - 主入口

功能：
1. 單檔股票分析 (K線、技術指標)
2. 族群比較分析 (產業內對比)
3. 選股篩選 (多條件篩選)
4. 量化策略回測

用法:
    python main.py web      # 啟動 Web 儀表板
    python main.py stock 2330        # 查詢單檔股票
    python main.py industry 半導體   # 查詢產業數據
    python main.py filter [條件]     # 執行股票篩選
"""

import sys
import argparse
from pathlib import Path

from core.data import data_query
from core.analysis import StockAnalyzer, IndustryComparison
from core.filters import StockFilter, PredefinedFilters
from backtesting.engine import BacktestEngine, StrategyLibrary

def print_stock_analysis(stock_id: str):
    """打印單檔股票分析結果"""
    stock_info = data_query.get_stock_by_id(stock_id)
    if not stock_info:
        print(f"❌ 找不到股票: {stock_id}")
        return
    
    print(f"\n📈 {stock_info['證券名稱']} ({stock_id})")
    print(f"   產業: {stock_info.get('產業類別', 'N/A')}")
    print("-" * 50)
    
    latest = data_query.get_latest_price(stock_id)
    if latest:
        print(f"   收盤價: ${latest['收盤價']:.2f}")
        print(f"   漲跌: {latest['漲跌']:+.2f}")
        print(f"   成交股數: {latest['成交股數']:,.0f}")
        print(f"   成交金額: ${latest['成交金額']:,.0f}")
    
    analyzer = StockAnalyzer(stock_id)
    indicators = analyzer.get_latest_indicators()
    
    print("\n   技術指標:")
    print(f"   - RSI(14): {indicators.get('RSI_14', 'N/A')}")
    print(f"   - MACD: {indicators.get('MACD', 'N/A')}")
    print(f"   - SMA20: ${indicators.get('SMA_20', 'N/A'):.2f}")
    print(f"   - SMA50: ${indicators.get('SMA_50', 'N/A'):.2f}")
    print(f"   - 波動率: {indicators.get('Volatility', 'N/A')}%")

def print_industry_analysis(industry: str):
    """打印產業分析結果"""
    stocks = data_query.get_stocks_by_industry(industry)
    if stocks.empty:
        print(f"❌ 找不到產業: {industry}")
        return
    
    print(f"\n🏢 {industry} (共 {len(stocks)} 檔股票)")
    print("-" * 50)
    
    stats = IndustryComparison.compare_industry_performance(industry)
    print(f"   平均收盤價: ${stats.get('平均收盤價', 0):.2f}")
    print(f"   平均漲跌: {stats.get('平均漲跌', 0):+.2f}")
    print(f"   上漲股數: {stats.get('上漲股數', 0)}")
    print(f"   下跌股數: {stats.get('下跌股數', 0)}")
    
    print("\n   領頭股 (按成交金額):")
    leaders = IndustryComparison.get_industry_leaders(industry, '成交金額', 5)
    for _, row in leaders.iterrows():
        print(f"   - {row['證券代號']} {row['證券名稱']}: ${row['收盤價']:.2f} ({row['漲跌']:+.2f})")

def print_filter_results(filter_type: str = "bullish"):
    """打印篩選結果"""
    print(f"\n🔍 執行篩選: {filter_type}")
    print("-" * 50)
    
    if filter_type == "bullish":
        result = PredefinedFilters.bullish_signal()
        print("看漲信號 (黃金交叉 + 價格 > SMA20)")
    elif filter_type == "oversold":
        result = PredefinedFilters.oversold_stocks()
        print("超賣股票 (RSI < 30)")
    elif filter_type == "overbought":
        result = PredefinedFilters.overbought_stocks()
        print("超買股票 (RSI > 70)")
    else:
        result = PredefinedFilters.high_volume_gainers()
        print("成交量大漲股")
    
    print(f"\n找到 {len(result)} 檔符合條件的股票:\n")
    
    for _, row in result.head(10).iterrows():
        print(f"   {row['證券代號']} {row['證券名稱']:<15} 收: ${row['收盤價']:>8.2f} 漲: {row['漲跌']:>+7.2f}")

def main():
    parser = argparse.ArgumentParser(
        description="股市觀察工具 - 量化分析與選股篩選平台",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
    python main.py web                      # 啟動 Web 儀表板
    python main.py stock 2330               # 分析單檔股票
    python main.py industry 半導體          # 分析產業數據
    python main.py filter bullish           # 執行看漲篩選
    python main.py list_industries          # 列出所有產業
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # Web 命令
    web_parser = subparsers.add_parser('web', help='啟動 Web 儀表板')
    web_parser.add_argument('--port', type=int, default=8502, help='指定 port (預設: 8502)')
    
    # Stock 命令
    stock_parser = subparsers.add_parser('stock', help='分析單檔股票')
    stock_parser.add_argument('stock_id', help='股票代號 (e.g., 2330)')
    
    # Industry 命令
    industry_parser = subparsers.add_parser('industry', help='分析產業')
    industry_parser.add_argument('industry', help='產業名稱 (e.g., 半導體)')
    
    # Filter 命令
    filter_parser = subparsers.add_parser('filter', help='執行篩選')
    filter_parser.add_argument(
        'filter_type',
        choices=['bullish', 'oversold', 'overbought', 'high_volume'],
        help='篩選類型'
    )
    
    # List 命令
    subparsers.add_parser('list_industries', help='列出所有產業')
    subparsers.add_parser('list_stocks', help='列出所有股票')
    
    args = parser.parse_args()
    
    if args.command == 'web':
        print("🚀 啟動 Web 儀表板...")
        print(f"   請訪問: http://localhost:{args.port}")
        print("\n   按 Ctrl+C 停止")
        
        import subprocess
        import sys
        subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'ui/app.py', '--server.port', str(args.port)])
    
    elif args.command == 'stock':
        print_stock_analysis(args.stock_id)
    
    elif args.command == 'industry':
        print_industry_analysis(args.industry)
    
    elif args.command == 'filter':
        print_filter_results(args.filter_type)
    
    elif args.command == 'list_industries':
        print("\n📚 所有產業類別:")
        print("-" * 50)
        industries = data_query.get_all_industries()
        for i, ind in enumerate(industries, 1):
            print(f"   {i:2d}. {ind}")
    
    elif args.command == 'list_stocks':
        print("\n📚 所有股票:")
        print("-" * 50)
        stocks = data_query.get_all_stocks()
        for _, row in stocks.head(20).iterrows():
            print(f"   {row['證券代號']} {row['證券名稱']:<15} ({row.get('產業類別', 'N/A')})")
        if len(stocks) > 20:
            print(f"   ... 還有 {len(stocks) - 20} 檔股票")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

