#!/usr/bin/env python3
"""驗證測試腳本"""

import sys
import os

print("=" * 50)
print("🔍 股市觀察工具 - 完整驗證測試")
print("=" * 50)

print("\n📋 環境信息:")
print(f"  Python 版本: {sys.version}")
print(f"  Python 路徑: {sys.executable}")
print(f"  當前目錄: {os.getcwd()}")

# 驗證模塊導入
print("\n📦 模塊導入驗證:")

success_count = 0
total_count = 0

test_imports = [
    ("core.data", "from core.data import data_query"),
    ("core.analysis", "from core.analysis import StockAnalyzer, IndustryComparison"),
    ("core.filters", "from core.filters import StockFilter, PredefinedFilters"),
    ("backtesting.engine", "from backtesting.engine import BacktestEngine, StrategyLibrary"),
    ("streamlit", "import streamlit as st"),
    ("plotly", "import plotly.graph_objects as go"),
    ("pandas", "import pandas as pd"),
    ("numpy", "import numpy as np"),
]

for module_name, import_stmt in test_imports:
    total_count += 1
    try:
        exec(import_stmt)
        print(f"  ✅ {module_name:<25} 導入成功")
        success_count += 1
    except Exception as e:
        print(f"  ❌ {module_name:<25} 導入失敗: {str(e)[:50]}")

# 驗證數據
print(f"\n📊 數據驗證:")

try:
    from core.data import data_query
    
    all_stocks = data_query.get_all_stocks()
    print(f"  ✅ 股票數據: {len(all_stocks)} 檔")
    success_count += 1
    total_count += 1
    
    industries = data_query.get_all_industries()
    print(f"  ✅ 產業數據: {len(industries)} 個產業")
    success_count += 1
    total_count += 1
    
    # 測試單檔分析
    if len(all_stocks) > 0:
        first_stock = all_stocks.iloc[0]['證券代號']
        latest = data_query.get_latest_price(first_stock)
        if latest:
            print(f"  ✅ 股票查詢: {first_stock} 可正常查詢")
            success_count += 1
            total_count += 1
        else:
            print(f"  ⚠️  股票查詢: {first_stock} 無最新價格")
            total_count += 1
            
except Exception as e:
    print(f"  ❌ 數據驗證失敗: {e}")
    total_count += 3

# 驗證技術指標計算
print(f"\n🔬 技術指標驗證:")

try:
    from core.analysis import StockAnalyzer
    
    if len(all_stocks) > 0:
        test_stock = all_stocks.iloc[0]['證券代號']
        analyzer = StockAnalyzer(test_stock)
        
        if not analyzer.df.empty:
            indicators = analyzer.get_latest_indicators()
            if indicators:
                print(f"  ✅ 指標計算: {test_stock} 的指標計算成功")
                print(f"     - RSI: {indicators.get('RSI_14', 'N/A')}")
                print(f"     - MACD: {indicators.get('MACD', 'N/A')}")
                success_count += 1
            else:
                print(f"  ⚠️  指標計算: {test_stock} 的指標值為空")
        else:
            print(f"  ⚠️  指標計算: {test_stock} 無歷史數據")
    
    total_count += 1
    
except Exception as e:
    print(f"  ❌ 指標計算失敗: {e}")
    total_count += 1

# 驗證篩選功能
print(f"\n🔍 篩選功能驗證:")

try:
    from core.filters import PredefinedFilters
    
    # 測試預定義篩選
    print(f"  ⏳ 執行看漲信號篩選...")
    bullish = PredefinedFilters.bullish_signal()
    print(f"  ✅ 看漲信號篩選: 找到 {len(bullish)} 檔股票")
    success_count += 1
    total_count += 1
    
except Exception as e:
    print(f"  ❌ 篩選功能失敗: {e}")
    total_count += 1

# 驗證回測功能
print(f"\n🎯 回測功能驗證:")

try:
    from backtesting.engine import BacktestEngine, StrategyLibrary
    
    if len(all_stocks) > 0:
        test_stock = all_stocks.iloc[0]['證券代號']
        
        try:
            engine = BacktestEngine(test_stock, "2024-01-01", "2024-12-31", 100000)
            engine.add_signal(StrategyLibrary.sma_crossover_strategy)
            results = engine.backtest()
            
            if results:
                print(f"  ✅ 回測功能: {test_stock} 的 SMA 策略回測成功")
                print(f"     - 報酬率: {results['總報酬率%']}%")
                print(f"     - 勝率: {results['勝率%']}%")
                success_count += 1
            else:
                print(f"  ⚠️  回測功能: {test_stock} 回測結果為空")
            
        except ValueError as e:
            if "無法取得" in str(e):
                print(f"  ⚠️  回測功能: {test_stock} 無足夠的歷史數據")
            else:
                raise
        
        total_count += 1
        
except Exception as e:
    print(f"  ❌ 回測功能失敗: {e}")
    total_count += 1

# 驗證 Streamlit App
print(f"\n🌐 Web 應用驗證:")

try:
    import streamlit
    print(f"  ✅ Streamlit 版本: {streamlit.__version__}")
    
    # 檢查 ui/app.py 是否存在
    app_path = "ui/app.py"
    if os.path.exists(app_path):
        print(f"  ✅ Web 應用文件: ui/app.py 存在")
        success_count += 1
    else:
        print(f"  ❌ Web 應用文件: ui/app.py 不存在")
    
    total_count += 1
    
except Exception as e:
    print(f"  ❌ Streamlit 驗證失敗: {e}")
    total_count += 1

# 總結
print("\n" + "=" * 50)
print(f"📊 驗證結果: {success_count}/{total_count} 通過")
print("=" * 50)

if success_count == total_count:
    print("\n✅ 所有驗證通過！系統已準備就緒。")
    print("\n🚀 可以使用以下命令啟動 Web 儀表板:")
    print("   python main.py web")
    print("\n或直接執行:")
    print("   python -m streamlit run ui/app.py")
    sys.exit(0)
else:
    print(f"\n⚠️  有 {total_count - success_count} 項驗證失敗，請檢查上述錯誤。")
    sys.exit(1)
