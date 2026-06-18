# 🚀 快速入門指南

## 📋 前置條件

✅ 已完成 **Phase 1 & 2**:
- 數據已從 TWSE 取得並入庫 (staging/ 中有 JSON 檔)
- 已執行 `python step2_etl_and_db.py` 完成 ETL 與建庫

## 🎯 5分鐘快速開始

### 1️⃣ 安裝新依賴

```bash
pip install streamlit plotly
```

### 2️⃣ 啟動 Web 儀表板

```bash
python main.py web
```

自動打開瀏覽器: `http://localhost:8501`

### 3️⃣ 探索功能

#### 🏠 首頁
- 市場概覽
- 漲跌榜

#### 📈 單檔分析
```
選擇股票 → 查看 K線圖 → 分析技術指標
```

**支持的指標**:
- K線圖 + SMA20/50
- RSI、MACD、布林帶
- 波動率、隨機指標

#### 🏢 族群比較
```
選擇產業 → 查看領頭股 → 比較績效
```

**分析內容**:
- 產業平均表現
- 成交量領頭股
- 漲跌排行
- 股票相關性

#### 🔍 選股篩選
```
選擇條件 → 執行篩選 → 查看結果
```

**預定義篩選** (一鍵執行):
- 看漲信號 (SMA20 > SMA50)
- 超賣股票 (RSI < 30)
- 超買股票 (RSI > 70)
- 成交量大漲股

**自訂篩選** (組合條件):
```
價格範圍 + 成交量 + 技術指標 + 產業
```

#### 🎯 回測策略
```
選擇股票 → 選擇策略 → 設定參數 → 執行回測
```

**可用策略**:
- SMA 交叉 (20日 vs 50日)
- RSI 超買超賣
- MACD

**查看指標**:
- 總報酬率、年化報酬率
- 最大虧損、勝率
- 交易清單、淨值曲線

---

## 💻 命令行使用

### 查詢單檔股票

```bash
python main.py stock 2330
```

**輸出**:
```
📈 台積電 (2330)
   產業: 半導體
──────────────────────────────────────────
   收盤價: $995.00
   漲跌: -5.00
   成交股數: 8,234,000
   成交金額: $8,192,345,000

   技術指標:
   - RSI(14): 45.23
   - MACD: 0.0523
   - SMA20: $980.50
   - SMA50: $970.30
   - 波動率: 12.45%
```

### 查詢產業

```bash
python main.py industry 半導體
```

### 執行篩選

```bash
python main.py filter bullish        # 看漲信號
python main.py filter oversold       # 超賣股票
python main.py filter overbought     # 超買股票
python main.py filter high_volume    # 成交量大漲
```

### 列出所有產業

```bash
python main.py list_industries
```

### 列出所有股票

```bash
python main.py list_stocks
```

---

## 🐍 Python API 使用

### 1. 分析單檔股票

```python
from core.analysis import StockAnalyzer

analyzer = StockAnalyzer("2330")
indicators = analyzer.get_latest_indicators()

print(f"收盤價: ${indicators['收盤價']}")
print(f"RSI: {indicators['RSI_14']}")
print(f"SMA20: ${indicators['SMA_20']}")
```

### 2. 查詢產業數據

```python
from core.analysis import IndustryComparison

# 產業績效統計
stats = IndustryComparison.compare_industry_performance("半導體")
print(f"上漲股數: {stats['上漲股數']}")

# 領頭股
leaders = IndustryComparison.get_industry_leaders("半導體", '成交金額', 10)
print(leaders)

# 漲跌排行
gainers, losers = IndustryComparison.get_industry_gainers_losers("半導體", 5)
print("漲幅最大:")
print(gainers)
```

### 3. 篩選股票

```python
from core.filters import StockFilter, PredefinedFilters

# 使用預定義篩選
bullish_stocks = PredefinedFilters.bullish_signal()
print(f"找到 {len(bullish_stocks)} 檔看漲信號股票")

# 自訂篩選（method chaining）
result = (StockFilter()
    .filter_by_price_range(100, 500)
    .filter_by_volume(5000000)
    .filter_by_rsi(max_rsi=70)
    .filter_by_industry("半導體")
    .execute())

print(result)
```

### 4. 回測策略

```python
from backtesting.engine import BacktestEngine, StrategyLibrary

engine = BacktestEngine(
    stock_id="2330",
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000
)

# 添加 SMA 交叉策略
engine.add_signal(StrategyLibrary.sma_crossover_strategy)

# 執行回測
results = engine.backtest()

print(f"初始資本: ${results['初始資本']:,.0f}")
print(f"最終價值: ${results['最終價值']:,.0f}")
print(f"總報酬率: {results['總報酬率%']}%")
print(f"勝率: {results['勝率%']}%")
print(f"交易次數: {results['總交易次數']}")
```

---

## 📊 核心類速查

### data.py - 數據查詢

```python
from core.data import data_query

# 取得股票信息
stock_info = data_query.get_stock_by_id("2330")

# 取得歷史價格
df = data_query.get_stock_price_history("2330")

# 取得最新價格
latest = data_query.get_latest_price("2330")

# 取得產業股票
stocks = data_query.get_stocks_by_industry("半導體")

# 取得所有產業
industries = data_query.get_all_industries()
```

### analysis.py - 技術指標

```python
from core.analysis import StockAnalyzer, IndustryComparison, TechnicalAnalysis

analyzer = StockAnalyzer("2330")
analyzer.get_latest_indicators()      # 所有指標
analyzer.get_analysis_summary()       # 分析摘要

# 族群分析
IndustryComparison.compare_industry_performance("半導體")
IndustryComparison.get_industry_leaders("半導體", '成交金額', 10)
IndustryComparison.get_industry_gainers_losers("半導體", 5)
```

### filters.py - 篩選引擎

```python
from core.filters import StockFilter, PredefinedFilters

# 預定義
PredefinedFilters.bullish_signal()
PredefinedFilters.oversold_stocks(30)
PredefinedFilters.overbought_stocks(70)
PredefinedFilters.high_volume_gainers()

# 自訂
StockFilter()
    .filter_by_price_range(100, 500)
    .filter_by_volume(1000000)
    .filter_by_rsi(min_rsi=30, max_rsi=70)
    .execute()
```

### backtesting.engine - 回測

```python
from backtesting.engine import BacktestEngine, StrategyLibrary

engine = BacktestEngine("2330")
engine.add_signal(StrategyLibrary.sma_crossover_strategy)
results = engine.backtest()
```

---

## 🎓 常見使用場景

### 場景 1: 找尋現在的看漲股票

```python
from core.filters import PredefinedFilters

bullish = PredefinedFilters.bullish_signal()
print(bullish[['證券代號', '證券名稱', '收盤價']])
```

### 場景 2: 在某個產業中篩選超賣股

```python
from core.filters import StockFilter

oversold = (StockFilter()
    .filter_by_industry("半導體")
    .filter_by_rsi(max_rsi=30)
    .execute())
```

### 場景 3: 比較電子零組件產業

```python
from core.analysis import IndustryComparison

# 產業績效
stats = IndustryComparison.compare_industry_performance("電子零組件")

# 領頭股
leaders = IndustryComparison.get_industry_leaders("電子零組件")

# 漲跌排行
gainers, losers = IndustryComparison.get_industry_gainers_losers("電子零組件")
```

### 場景 4: 回測策略效果

```python
from backtesting.engine import BacktestEngine, StrategyLibrary

stocks = ["2330", "3008", "2308"]
for stock in stocks:
    engine = BacktestEngine(stock, initial_capital=100000)
    engine.add_signal(StrategyLibrary.rsi_strategy)
    results = engine.backtest()
    print(f"{stock}: {results['勝率%']}%")
```

---

## ⚠️ 注意事項

1. **數據需求**: 需先執行 `step1_fetcher.py` 和 `step2_etl_and_db.py` 完成數據入庫
2. **技術指標需要歷史數據**: RSI、MACD 等需要足夠的歷史數據才能計算
3. **回測結果**: 基於歷史數據，過往表現不代表未來結果
4. **投資免責聲明**: 本工具僅供分析參考，不構成投資建議

---

## 🔧 故障排除

### 找不到股票/產業?
```bash
# 確認數據是否已入庫
python main.py list_stocks
python main.py list_industries
```

### 技術指標為 NaN?
- 檢查歷史數據是否充足（至少 200 天以上）
- 新上市股票可能沒有足夠數據

### 回測結果為空?
- 確認日期範圍內有交易數據
- 檢查策略是否產生信號

---

## 📚 進階閱讀

- [README.md](README.md) - 完整文檔
- `core/data.py` - 數據查詢 API
- `core/analysis.py` - 技術指標實現
- `ui/app.py` - Streamlit 儀表板代碼

---

祝你探索愉快！📈
