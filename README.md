# 📊 股市觀察工具

量化分析與選股篩選平台 - 支援單檔分析、族群比較、自動篩選、策略回測

## 🎯 核心功能

### 1. 📈 單檔股票分析
- **K線圖與移動平均線**: 視覺化股價走勢
- **技術指標**: RSI、MACD、布林帶、隨機指標等
- **歷史數據**: 完整的價格和成交量資訊

### 2. 🏢 族群比較分析
- **產業內對比**: 比較同產業不同股票表現
- **產業領頭股**: 按成交金額、價格等排序
- **漲跌排行**: 快速掌握贏家與輸家
- **相關性分析**: 計算產業內股票相關係數

### 3. 🔍 選股篩選
- **預定義篩選**:
  - 看漲信號 (黃金交叉 + 價格 > SMA20)
  - 超賣股票 (RSI < 30)
  - 超買股票 (RSI > 70)
  - 成交量大漲股
- **自訂篩選**: 組合多個條件進行複雜篩選
  - 價格範圍
  - 成交量
  - 技術指標
  - 產業類別

### 4. 🎯 量化策略回測
- **SMA 交叉策略**: 20日線與50日線交叉
- **RSI 策略**: 超買超賣反轉策略
- **MACD 策略**: 動量指標策略
- **完整指標**:
  - 總報酬率
  - 年化報酬率
  - 最大虧損
  - 勝率
  - 交易清單與組合淨值曲線

## 🚀 快速開始

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 啟動 Web 儀表板

```bash
python main.py web
```

瀏覽器自動打開: `http://localhost:8501`

### 命令行使用

```bash
# 分析單檔股票
python main.py stock 2330

# 分析產業
python main.py industry 半導體

# 執行篩選
python main.py filter bullish        # 看漲信號
python main.py filter oversold       # 超賣股票
python main.py filter overbought     # 超買股票
python main.py filter high_volume    # 成交量大漲

# 列出所有產業
python main.py list_industries

# 列出所有股票
python main.py list_stocks
```

## 📦 項目結構

```
stock_app/
├── core/
│   ├── data.py           # 統一數據查詢 API
│   ├── analysis.py       # 技術指標與族群分析
│   └── filters.py        # 股票篩選引擎
├── backtesting/
│   └── engine.py         # 回測框架
├── ui/
│   └── app.py           # Streamlit Web 應用
├── step1_fetcher.py      # 數據獲取（TWSE API）
├── step2_etl_and_db.py   # 數據清洗與入庫
├── main.py              # 主入口
├── pyproject.toml       # 項目配置
└── README.md
```

## 🔄 數據流

```
TWSE API → staging/ (JSON) → ETL清洗 → SQLite (Company_Dim, Tag_Dim, Dividend_Fact)
                                      → Parquet (按股票代號分檔)
                                      
↓
[Web儀表板 / 分析工具]
```

## 📊 技術棧

- **後端**: Python 3.12+
- **數據處理**: Pandas, NumPy
- **可視化**: Plotly, Streamlit
- **數據存儲**: SQLite, Parquet
- **數據源**: 台灣證券交易所 (TWSE)

## 📈 技術指標

支援以下技術指標:

| 指標 | 說明 | 用途 |
|-----|------|------|
| **SMA** | 簡單移動平均 | 趨勢判斷 |
| **EMA** | 指數移動平均 | 快速反應 |
| **RSI** | 相對強度指標 | 超買/超賣 |
| **MACD** | 動量指標 | 買賣信號 |
| **BB** | 布林帶 | 波動範圍 |
| **ATR** | 平均真實波幅 | 波動率 |
| **Stochastic** | 隨機指標 | 超買/超賣 |

## ⚙️ 核心類

### StockDataQuery
```python
from core.data import data_query

# 取得股票信息
stock = data_query.get_stock_by_id("2330")

# 取得歷史價格
df = data_query.get_stock_price_history("2330", "2024-01-01", "2024-12-31")

# 取得產業股票
stocks = data_query.get_stocks_by_industry("半導體")
```

### StockAnalyzer
```python
from core.analysis import StockAnalyzer

analyzer = StockAnalyzer("2330")
indicators = analyzer.get_latest_indicators()
summary = analyzer.get_analysis_summary()
```

### StockFilter
```python
from core.filters import StockFilter

results = (StockFilter()
    .filter_by_price_range(100, 500)
    .filter_by_rsi(max_rsi=70)
    .filter_by_industry("半導體")
    .execute())
```

### BacktestEngine
```python
from backtesting.engine import BacktestEngine, StrategyLibrary

engine = BacktestEngine("2330", "2024-01-01", "2024-12-31")
engine.add_signal(StrategyLibrary.sma_crossover_strategy)
results = engine.backtest()
```

## 📝 使用範例

### 1. 分析 TSMC (2330)

```python
from core.analysis import StockAnalyzer

analyzer = StockAnalyzer("2330")
indicators = analyzer.get_latest_indicators()
print(indicators)

# 輸出:
# {
#   '日期': '2024-12-31',
#   '收盤價': 995.0,
#   '漲跌': -5.0,
#   'SMA_20': 980.5,
#   'RSI_14': 45.2,
#   'MACD': 0.0523,
#   ...
# }
```

### 2. 比較半導體產業

```python
from core.analysis import IndustryComparison

stats = IndustryComparison.compare_industry_performance("半導體")
print(stats)

gainers, losers = IndustryComparison.get_industry_gainers_losers("半導體")
```

### 3. 篩選看漲信號

```python
from core.filters import PredefinedFilters

bullish_stocks = PredefinedFilters.bullish_signal()
print(bullish_stocks)
```

### 4. 回測 SMA 策略

```python
from backtesting.engine import BacktestEngine, StrategyLibrary

engine = BacktestEngine("2330", "2024-01-01", "2024-12-31", 100000)
engine.add_signal(StrategyLibrary.sma_crossover_strategy)
results = engine.backtest()

print(f"總報酬率: {results['總報酬率%']}%")
print(f"勝率: {results['勝率%']}%")
```

## ⚠️ 免責聲明

本工具僅供分析參考，**不構成投資建議**。股票投資存在風險，應進行充分的風險評估。

## 📄 數據來源

- **數據提供者**: 台灣證券交易所 (TWSE)
- **更新頻率**: 每個交易日
- **歷史數據**: 2016 年至今

## 📧 反饋與改進

如有任何建議或發現問題，歡迎提出。

---

**版本**: 1.0.0  
**最後更新**: 2026-06-18
