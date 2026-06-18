# 📐 架構設計文檔

## 🏗️ 整體架構

```
┌─────────────────────────────────────────────────────────────────┐
│                      Web 儀表板 (Streamlit UI)                   │
│  ┌─────────────┬──────────────┬──────────────┬──────────────┐   │
│  │  單檔分析   │  族群比較    │  選股篩選    │  回測策略    │   │
│  └─────────────┴──────────────┴──────────────┴──────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                     核心業務邏輯層 (Core)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Analysis Layer (core/analysis.py)                         │   │
│  │ - TechnicalAnalysis: 7 大技術指標                        │   │
│  │ - StockAnalyzer: 單檔分析                               │   │
│  │ - IndustryComparison: 族群對比                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Filter Layer (core/filters.py)                           │   │
│  │ - StockFilter: 靈活篩選引擎                             │   │
│  │ - PredefinedFilters: 預定義組合                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Data Access Layer (core/data.py)                         │   │
│  │ - StockDataQuery: 統一數據查詢 API                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│              Backtesting Layer (backtesting/engine.py)           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ BacktestEngine: 完整的回測系統                          │   │
│  │ StrategyLibrary: 3 種預定義策略                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                  數據持久化層 (Data Storage)                     │
│  ┌─────────────┐          ┌──────────────────────────────────┐  │
│  │   SQLite    │          │       Parquet 檔案               │  │
│  │             │          │                                  │  │
│  │ ✓ Company   │          │ ✓ 按股票代號分檔                │  │
│  │ ✓ Tags      │          │ ✓ 高效壓縮                      │  │
│  │ ✓ Dividends │          │ ✓ 快速查詢                      │  │
│  └─────────────┘          └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 模塊分層

### 第 1 層：數據訪問層 (Data Access)

**文件**: `core/data.py`

**職責**: 統一的數據查詢接口

**主要類**:
- `StockDataQuery` - 單例模式全局對象

**主要方法**:
```
get_all_stocks()                  → 所有股票清單
get_stock_by_id(stock_id)         → 股票信息
get_stock_price_history(...)      → 歷史價格
get_latest_price(stock_id)        → 最新價格
get_stocks_by_industry(industry)  → 產業股票
get_all_industries()              → 所有產業
get_industry_snapshot(...)        → 產業快照
get_dividend_history(stock_id)    → 除權息歷史
```

**設計特點**:
- 屏蔽底層數據存儲細節 (SQLite + Parquet)
- 日期範圍篩選
- 批量查詢優化
- 標籤功能支持

---

### 第 2 層：分析層 (Analysis)

**文件**: `core/analysis.py`

**職責**: 技術指標計算和族群分析

**主要類**:

#### TechnicalAnalysis
```python
moving_average(prices, window)        # 簡單移動平均
exponential_moving_average(...)       # 指數移動平均
macd(prices)                          # MACD 指標
rsi(prices, window)                   # 相對強度指標
bollinger_bands(prices)               # 布林帶
atr(high, low, close)                 # 平均真實波幅
stochastic(high, low, close)          # 隨機指標
calculate_returns(prices)             # 報酬率
calculate_volatility(prices)          # 波動率
```

#### StockAnalyzer
```python
__init__(stock_id)                    # 初始化並計算指標
get_latest_indicators()               # 最新指標值
get_analysis_summary()                # 分析摘要
```

#### IndustryComparison
```python
compare_industry_performance(...)     # 產業績效統計
get_industry_leaders(...)             # 領頭股排序
get_industry_gainers_losers(...)      # 漲跌排行
get_sector_correlation(...)           # 相關性分析
```

**支援的技術指標**:
| 指標 | 說明 | 參數 |
|------|------|------|
| SMA | 簡單移動平均 | 20, 50, 200 |
| EMA | 指數移動平均 | 12, 26 |
| RSI | 相對強度指標 | 14 |
| MACD | 動量指標 | 12, 26, 9 |
| BB | 布林帶 | 20, 2.0 |
| ATR | 平均真實波幅 | 14 |
| Stoch | 隨機指標 | 14, 3 |

---

### 第 3 層：篩選層 (Filters)

**文件**: `core/filters.py`

**職責**: 靈活的股票篩選系統

**主要類**:

#### StockFilter (Builder 模式)
```python
# Method Chaining 示例
(StockFilter()
 .filter_by_price_range(100, 500)
 .filter_by_volume(1000000)
 .filter_by_rsi(30, 70)
 .filter_by_industry("半導體")
 .execute())
```

**支援的篩選條件**:
- `filter_by_price_range()` - 價格範圍
- `filter_by_volume()` - 成交量
- `filter_by_change_percent()` - 漲跌幅
- `filter_by_industry()` - 產業
- `filter_by_tag()` - 自訂標籤
- `filter_by_rsi()` - RSI 指標
- `filter_by_moving_average_cross()` - 黃金交叉
- `filter_by_price_above_ma()` - 價格高於均線

#### PredefinedFilters (靜態方法)
```python
bullish_signal()           # 看漲信號
oversold_stocks()          # 超賣股票
overbought_stocks()        # 超買股票
high_volume_gainers()      # 成交量大漲股
industry_leaders()         # 產業領頭股
```

**設計特點**:
- Builder 模式支持 method chaining
- 所有條件為 AND 邏輯
- 條件複用與組合
- 性能優化（集合運算）

---

### 第 4 層：回測層 (Backtesting)

**文件**: `backtesting/engine.py`

**職責**: 量化策略回測

**主要類**:

#### BacktestEngine
```python
__init__(stock_id, start_date, end_date, initial_capital)
add_signal(signal_func)                # 添加策略
backtest()                             # 執行回測
```

**回測流程**:
1. 讀取股票歷史數據
2. 逐日遍歷，調用信號函數生成買賣信號
3. 執行交易（模擬成交）
4. 計算組合淨值與交易績效

**支援的策略**:

#### StrategyLibrary
```python
sma_crossover_strategy()   # SMA20 vs SMA50 交叉
rsi_strategy()             # RSI 超買超賣反轉
macd_strategy()            # MACD 線交叉
```

**回測指標**:
```python
results = {
    '初始資本': 100000,
    '最終價值': 125000,
    '總報酬率%': 25.0,
    '年化報酬率%': 12.5,
    '最大虧損%': -15.2,
    '總交易次數': 10,
    '獲利交易': 7,
    '虧損交易': 3,
    '勝率%': 70.0,
    '交易清單': [...],
    '組合淨值曲線': DataFrame,
}
```

**設計特點**:
- 信號函數抽象化（支持自訂策略）
- 完整的交易模擬
- 詳細的績效指標
- 組合淨值曲線追蹤

---

### 第 5 層：表示層 (UI)

**文件**: `ui/app.py`

**框架**: Streamlit

**頁面結構**:

```
首頁
├─ 市場概覽
└─ 漲跌榜

單檔分析
├─ K線圖 + 移動平均線
└─ 技術指標面板

族群比較
├─ 產業績效統計
├─ 領頭股排序
├─ 漲跌排行
└─ 相關性分析

選股篩選
├─ 預定義篩選 (4種)
└─ 自訂篩選 (多條件)

回測策略
├─ 策略選擇
├─ 參數設定
└─ 結果展示
```

**技術棧**:
- Streamlit: 快速開發 Web 應用
- Plotly: 交互式圖表
- Pandas: 數據處理
- NumPy: 數值計算

---

## 🔄 數據流向

### 場景 1: 用戶查詢單檔股票分析

```
User Input: 股票代號 (2330)
    ↓
StockAnalyzer.__init__("2330")
    ↓
data_query.get_stock_price_history("2330")  [Parquet 讀取]
    ↓
TechnicalAnalysis.calculate_indicators()
    ↓
Display: K線圖 + 技術指標
```

### 場景 2: 用戶執行篩選

```
User Input: 篩選條件組合
    ↓
StockFilter.filter_by_xxx()  [條件堆積]
    ↓
StockFilter.execute()
    ↓
For each stock_id in all_stocks:
    ├─ 檢查所有條件
    └─ 符合則加入結果集
    ↓
Display: 篩選結果表格
```

### 場景 3: 用戶回測策略

```
User Input: 股票、策略、時間範圍
    ↓
BacktestEngine(stock_id, dates, capital)
    ↓
For each day in date_range:
    ├─ 讀取 OHLC 數據
    ├─ 調用信號函數
    ├─ 執行買賣邏輯
    └─ 更新組合價值
    ↓
計算績效指標
    ↓
Display: 返回率、勝率、淨值曲線
```

---

## 🎯 設計原則

### 1. **分層隔離** (Layering)
- 數據訪問層屏蔽存儲細節
- 分析層獨立於 UI
- 易於單元測試和替換

### 2. **單一職責** (Single Responsibility)
- 每個類有明確的職責
- 方法功能單一
- 易於維護和擴展

### 3. **開放封閉** (Open-Closed)
- 對擴展開放（新指標、策略、篩選條件）
- 對修改封閉（通過繼承和抽象）
- 新策略無需修改核心代碼

### 4. **DRY** (Don't Repeat Yourself)
- 統一的數據查詢 API
- 共享的技術指標計算
- 復用的篩選邏輯

### 5. **依賴注入** (Dependency Injection)
- 策略作為參數傳入
- 信號函數作為回調

---

## 🔧 擴展指南

### 添加新技術指標

在 `TechnicalAnalysis` 中添加方法：

```python
@staticmethod
def new_indicator(prices, param1, param2):
    """新指標說明"""
    # 實現邏輯
    return result_series
```

在 `StockAnalyzer._calculate_indicators()` 中計算：

```python
self.df['New_Indicator'] = self.ta.new_indicator(close, param1, param2)
```

### 添加新篩選條件

在 `StockFilter` 中添加方法：

```python
def filter_by_new_condition(self, threshold):
    def condition(stock_id):
        # 篩選邏輯
        return True/False
    
    self.add_condition(condition, f"New Condition: {threshold}")
    return self
```

### 添加新策略

在 `StrategyLibrary` 中添加方法：

```python
@staticmethod
def new_strategy(df, current_idx):
    """策略說明"""
    # 計算信號
    return {'action': 'BUY'|'SELL'|'HOLD', 'confidence': 0-1}
```

在 `main.py` 中集成：

```python
engine.add_signal(StrategyLibrary.new_strategy)
```

---

## 📊 性能優化

### 1. 數據結構
- Parquet: 列式存儲，壓縮率高，查詢快
- SQLite: 輕量級關係數據庫，便於複雜查詢

### 2. 查詢優化
- 篩選時使用集合運算
- 批量讀取 Parquet 檔案
- 日期範圍預過濾

### 3. 計算優化
- 技術指標使用向量化操作 (Pandas/NumPy)
- 避免 Python 循環
- 緩存常用計算結果

### 4. 可視化優化
- Plotly 交互式圖表
- 客戶端渲染，減輕服務器負擔

---

## 🔐 安全與可靠性

### 數據驗證
- 股票代號檢查
- 日期範圍驗證
- 空值處理

### 錯誤處理
- 檔案不存在
- 無效的技術指標參數
- 策略信號異常

### 測試建議
- 單元測試：指標計算、篩選邏輯
- 集成測試：數據流向、完整工作流
- 回歸測試：策略回測結果

---

## 📈 未來擴展方向

1. **實時數據**: WebSocket 連接 TWSE 實時行情
2. **高級指標**: 期貨指數、融資融券數據
3. **機器學習**: 價格預測、異常檢測
4. **投資組合**: 多檔資產配置、風險管理
5. **社群功能**: 策略分享、討論區
6. **API 服務**: REST API 供第三方調用
7. **行動應用**: iOS/Android 應用

---

這就是整個系統的完整設計！ 🎉
