#  快速入門指南

##  前置條件

✅ 已完成 **數據初始化**:
- 已執行 `python fetch_data.py` 完成資料抓取與入庫
- 或已執行分步驟:
  ```bash
  python step1_fetcher.py                      # 抓取原始數據
  python step2_etl_and_db.py                   # ETL 入庫（增量模式）
  python step3_fundamentals.py --industry-only # 產業別（選擇性）
  ```

---

##  一分鐘快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 啟動儀表板

```bash
python main.py web --port 8503
```

瀏覽器自動打開: `http://localhost:8503`

---

##  儀表板功能導覽

###  側邊欄

| 頁面 | 說明 |
|------|------|
| **首頁** | 市場概覽、漲跌榜（支援所有上市 + 上櫃股票） |
| **單檔分析** | K 線圖、技術指標（RSI/MACD/布林帶）+ 基本面分析（P/E/P/B/ROE 等） |
| **族群比較** | 產業績效統計、領頭股、漲跌排行、相關性 |
| **族群分析** | 自訂標籤管理（建立/刪除/批次貼標） |
| **選股篩選** | 預定義篩選 + 自訂多條件篩選 |
| **回測策略** | SMA/RSI/MACD 策略回測 |

###  族群分析（新功能）

```
操作步驟:
  1. 在輸入框輸入族群名稱 → 按 Enter 建立
  2. 搜尋框打關鍵字（如「穩懋」、「半導體」）過濾股票
  3. 勾選股票 → 按「批次設定標籤」完成貼標
  4. 按 ✕ 刪除標籤

特色:
  - 即時持久化（重整頁面不遺失）
  - 搜尋式股票選擇器（支援文字搜尋）
  - 全選 / 批次操作
  - 涵蓋所有上市 + 上櫃股票
```

### 📊 基本面分析（新功能）

在「單檔分析」頁面新增了基本面分析功能：

```
操作步驟:
  1. 選擇股票代號（如 2330）
  2. 頁面自動顯示基本面指標卡
  3. 包含：本益比、市帳率、ROE、ROA、淨利率、負債比、毛利率、EPS、BPS

特色:
  - 自動計算（無需額外 API 呼叫）
  - 即時顯示（選擇股票後立即更新）
  - 資料來源：MOPS 財務報表 + 最新收盤價
  - 涵蓋所有上市 + 上櫃股票
```

### 🎯 選擇股票小技巧

所有股票選擇器都支援**文字搜尋**，不需要 scroll 慢慢找：

```
輸入「2330」→ 顯示台積電
輸入「穩懋」→ 顯示 3105 穩懋
輸入「台積」→ 模糊匹配
```

---

##  數據更新

### 日常更新（推薦）

```bash
python fetch_data.py
```

自動完成:
1. 檢查缺少的日期
2. 抓取 TWSE + TPEx 新資料
3. 增量 ETL（只處理新資料，< 5 秒）

### 完整重建（修復用）

```bash
python fetch_data.py --rebuild
```

重新處理所有歷史資料，約 10-12 分鐘。

### 分步驟執行

```bash
# 只抓取
python fetch_data.py --fetch-only

# 只跑 ETL
python fetch_data.py --etl-only

# 抓取 + ETL + 基本面
python fetch_data.py --with-fundamentals

# 只跑基本面（產業/營收/法說）
python fetch_data.py --fundamentals-only
```

---

##  CLI 使用

### 查詢單檔股票

```bash
python main.py stock 2330
```

輸出範例:

```
📈 台積電 (2330)
    產業: 半導體
    收盤價: $995.00
    漲跌: -5.00
    技術指標:
    - RSI(14): 45.23
    - MACD: 0.0523
    - SMA20: $980.50
    - SMA50: $970.30
    - 波動率: 12.45%
```

### 其他 CLI 命令

```bash
# 分析產業
python main.py industry 半導體

# 執行篩選
python main.py filter bullish        # 看漲信號
python main.py filter oversold       # 超賣股票
python main.py filter overbought     # 超買股票
python main.py filter high_volume    # 成交量大漲

# 查詢清單
python main.py list_industries       # 所有產業
python main.py list_stocks           # 所有股票 (11,718 檔)
```

---

##  Python API 使用

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

stats = IndustryComparison.compare_industry_performance("半導體")
print(f"上漲股數: {stats['上漲股數']}")

leaders = IndustryComparison.get_industry_leaders("半導體", '成交金額', 10)
gainers, losers = IndustryComparison.get_industry_gainers_losers("半導體", 5)
```

### 3. 篩選股票

```python
from core.filters import StockFilter, PredefinedFilters

# 預定義篩選
bullish = PredefinedFilters.bullish_signal()
print(f"找到 {len(bullish)} 檔看漲信號股票")

# 自訂篩選（method chaining）
result = (StockFilter()
    .filter_by_price_range(100, 500)
    .filter_by_volume(5000000)
    .filter_by_rsi(max_rsi=70)
    .filter_by_industry("半導體")
    .execute())
```

### 4. 操作族群標籤

```python
from core.data import data_query
from core.themes import auto_tag_all_companies, get_stocks_by_tag

# 建立標籤
data_query.create_tag("AI 概念股", "2330")
data_query.create_tag("AI 概念股", "2454")

# 查詢標籤下的股票
stocks = get_stocks_by_tag("AI 概念股")

# 自動貼標（基於公司名稱關鍵字）
auto_tag_all_companies()

# 刪除標籤
data_query.delete_tag("AI 概念股", "2330")
```

### 5. 基本面分析

```python
from core.data import data_query
from core.themes import auto_tag_all_companies, get_stocks_by_tag

# 建立標籤
data_query.create_tag("AI 概念股", "2330")
data_query.create_tag("AI 概念股", "2454")

# 查詢標籤下的股票
stocks = get_stocks_by_tag("AI 概念股")

# 自動貼標（基於公司名稱關鍵字）
auto_tag_all_companies()

# 刪除標籤
data_query.delete_tag("AI 概念股", "2330")
```

### 5. 基本面分析

```python
from core.data import data_query

# 取得基本面指標
fundamentals = data_query.get_fundamentals("2330")
if fundamentals:
    print(f"本益比：{fundamentals['pe_ratio']}")
    print(f"市帳率：{fundamentals['pb_ratio']}")
    print(f"ROE: {fundamentals['roe']}%")
    print(f"ROA: {fundamentals['roa']}%")
    print(f"淨利率：{fundamentals['net_margin']}%")
    print(f"負債比：{fundamentals['debt_ratio']}%")
    print(f"毛利率：{fundamentals['gross_margin']}%")
    print(f"EPS: {fundamentals['eps']}")
    print(f"BPS: {fundamentals['bps']}")
```

### 6. 回測策略

```python
from backtesting.engine import BacktestEngine, StrategyLibrary

engine = BacktestEngine(
    stock_id="2330",
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000
)

engine.add_signal(StrategyLibrary.sma_crossover_strategy)
results = engine.backtest()

print(f"初始資本：${results['初始資本']:,.0f}")
print(f"最終價值：${results['最終價值']:,.0f}")
print(f"總報酬率：{results['總報酬率%']}%")
print(f"勝率：{results['勝率%']}%")
```

---

##  核心類速查

### data_query — 數據查詢

```python
from core.data import data_query

data_query.get_stock_by_id("2330")
data_query.get_stock_price_history("2330")
data_query.get_latest_price("2330")
data_query.get_stocks_by_industry("半導體")
data_query.get_all_industries()
data_query.get_fundamentals("2330")  # 基本面分析（P/E, P/B, ROE 等）
data_query.create_tag("族群名", "股票代號")     # 新增標籤
data_query.delete_tag("族群名", "股票代號")     # 刪除標籤
```

### StockAnalyzer — 技術指標

```python
from core.analysis import StockAnalyzer, IndustryComparison, TechnicalAnalysis

analyzer = StockAnalyzer("2330")
analyzer.get_latest_indicators()
analyzer.get_analysis_summary()

IndustryComparison.compare_industry_performance("半導體")
IndustryComparison.get_industry_leaders("半導體", '成交金額', 10)
```

### StockFilter — 篩選引擎

```python
from core.filters import StockFilter, PredefinedFilters

PredefinedFilters.bullish_signal()
PredefinedFilters.oversold_stocks(30)
PredefinedFilters.overbought_stocks(70)
PredefinedFilters.high_volume_gainers()

(StockFilter()
    .filter_by_price_range(100, 500)
    .filter_by_rsi(min_rsi=30, max_rsi=70)
    .execute())
```

### BacktestEngine — 回測

```python
from backtesting.engine import BacktestEngine, StrategyLibrary

engine = BacktestEngine("2330")
engine.add_signal(StrategyLibrary.sma_crossover_strategy)
results = engine.backtest()
```

---

##  常見使用場景

### 場景 1: 找尋現在的看漲股票

```python
from core.filters import PredefinedFilters

bullish = PredefinedFilters.bullish_signal()
print(bullish[['證券代號', '證券名稱', '收盤價']])
```

### 場景 2: 在特定產業中篩選超賣股

```python
from core.filters import StockFilter

oversold = (StockFilter()
    .filter_by_industry("半導體")
    .filter_by_rsi(max_rsi=30)
    .execute())
```

### 場景 3: 為自己建立投資族群

```python
from core.data import data_query

# 建立「我的核心持股」族群
for code in ["2330", "2454", "3008", "2317"]:
    data_query.create_tag("核心持股", code)

# 查看族群內容
from core.themes import get_stocks_by_tag
holdings = get_stocks_by_tag("核心持股")
print(holdings)
```

### 場景 4: 比較上櫃與上市同產業股票

```python
from core.analysis import IndustryComparison

# 上櫃的 3105 穩懋 vs 上市的 2330 台積電（同為半導體）
stats = IndustryComparison.compare_industry_performance("半導體")
```

### 場景 5: 回測多檔股票

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

##  資料庫概覽

| 資料庫 | 內容 | 大小 |
|---------|------|------|
| `stock_warehouse.db` | 股票維度、標籤、除權息、ETL 狀態 | ~5 MB |
| `task_status.db` | 每日期抓取狀態 | ~0.1 MB |
| `parquet_data/` | 按股票代號分檔的日資料 | ~2 GB |

### 目前規模

```
上市:   1,613 檔（2016 年起完整歷史）
上櫃:  10,105 檔（2016 年起，99.9% 覆蓋率）
合計:  11,718 檔股票/商品
ETL:   9,810 個 JSON 檔案已處理
```

---

## ⚠️ 注意事項

1. **初次使用**: 需先執行 `python fetch_data.py` 完成數據初始化
2. **OTC SSL**: 櫃買中心憑證驗證失敗為已知問題，已使用 `verify=False` 繞過
3. **技術指標需要歷史數據**: RSI、MACD 等需要至少 50 天以上數據
4. **上櫃歷史**: 99.9% 交易日已補齊，少數 API 無法取得的日期已跳過
5. **回測結果**: 基於歷史數據，過往表現不代表未來結果
6. **免責聲明**: 本工具僅供分析參考，不構成投資建議

---

##  故障排除

### 找不到股票/產業？

```bash
# 確認數據是否已入庫
python main.py list_stocks       # 應有 11,718 筆
python main.py list_industries   # 應有 80+ 產業
```

### 技術指標為 NaN？

- 檢查歷史數據是否充足（至少 50 天以上）
- 新上市/上櫃股票可能沒有足夠數據
- 可使用 `data_query.get_stock_price_history("3105")` 確認

### 上櫃股票沒資料？

```bash
# 重新跑增量 ETL
python fetch_data.py --etl-only

# 確認股票是否有在 Company_Dim 中
python -c "from core.data import data_query; print(data_query.get_stock_by_id('3105'))"
```

### 回測結果為空？

- 確認日期範圍內有交易數據
- 檢查策略是否產生信號
- 試試 SMA 交叉策略（較常產生信號）

### UnicodeEncodeError？

```powershell
# Windows PowerShell 編碼問題
$env:PYTHONIOENCODING='utf-8'; python fetch_data.py
```

---

##  進階閱讀

- [README.md](README.md) — 完整功能文檔與架構
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系統設計與架構決策
- `core/data.py` — 數據查詢 API
- `core/analysis.py` — 技術指標實現
- `core/themes.py` — 族群自動標籤
- `ui/app.py` — Streamlit 儀表板代碼
- `step2_etl_and_db.py` — 增量 ETL 實作

---

祝你探索愉快！
