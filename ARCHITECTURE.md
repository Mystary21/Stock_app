#  架構設計文檔

##  整體架構

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Web 儀表板 (Streamlit UI)                         │
│  ┌─────────────┬──────────────┬──────────────┬──────────────┬──────────┐  │
│  │  單檔分析   │  族群比較    │  選股篩選    │  回測策略    │ 族群分析  │  │
│  └─────────────┴──────────────┴──────────────┴──────────────┴──────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────────────┐
│                        核心業務邏輯層 (Core)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Analysis Layer (core/analysis.py)                                   │  │
│  │ - TechnicalAnalysis: 7 大技術指標                                   │  │
│  │ - StockAnalyzer: 單檔分析                                          │  │
│  │ - IndustryComparison: 族群對比                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Filter Layer (core/filters.py)                                      │  │
│  │ - StockFilter: 靈活篩選引擎 (Builder 模式)                          │  │
│  │ - PredefinedFilters: 預定義組合                                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Tag / Theme Layer (core/themes.py)                                  │  │
│  │ - auto_tag_all_companies(): 基於公司名關鍵字自動貼標                 │  │
│  │ - get_stocks_by_tag(), add_tag() ...                                │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Fundamental Analysis Layer (core/fundamentals.py)                   │  │
│  │ - FundamentalAnalyzer: 基本面分析器                                 │  │
│  │ - calculate_metrics(): P/E, P/B, ROE, ROA, 負債比，毛利率，淨利率  │  │
│  │ - get_all_stocks_metrics(): 批量取得所有股票基本面指標              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Data Access Layer (core/data.py)                                    │  │
│  │ - StockDataQuery: 統一數據查詢 API (SQLite + Parquet 雙存儲)        │  │
│  │ + core/database.py: SQLAlchemy engine (供 init_db.py 使用)          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────────────┐
│                  Backtesting Layer (backtesting/engine.py)                 │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ BacktestEngine: 完整的回測系統                                     │  │
│  │ StrategyLibrary: 3 種預定義策略 (SMA/RSI/MACD)                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴────────────────────────────────────────────┐
│                       數據持久化層 (Data Storage)                          │
│  ┌──────────────────────────────────────────────────────┐                │
│  │                 SQLite (stock_warehouse.db)           │                │
│  │  ┌──────────────┐  ┌──────────────────┐              │                │
│  │  │ Company_Dim  │  │ Tag_Dim          │              │                │
│  │  │ 11,718 檔    │  │ 族群標籤         │              │                │
│  │  ├──────────────┤  ├──────────────────┤              │                │
│  │  │ Dividend_Fact│  │ Company_Tag_Map  │              │                │
│  │  │ 除權息事件   │  │ 股票↔標籤多對多  │              │                │
│  │  └──────────────┘  └──────────────────┘              │                │
│  │  ┌──────────────────────────────────────┐            │                │
│  │  │ ETL_Status                           │            │                │
│  │  │ JSON 檔案 ETL 處理狀態 (9,810 筆)    │            │                │
│  │  └──────────────────────────────────────┘            │                │
│  └──────────────────────────────────────────────────────┘                │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐         │
│  │     Parquet 檔案 (parquet_data/)                             │         │
│  │     ┌──────────┐ ┌──────────┐ ┌──────────┐                 │         │
│  │     │2330.pq   │ │3105.pq   │ │...       │  (11,718 檔)    │         │
│  │     └──────────┘ └──────────┘ └──────────┘                 │         │
│  │     按股票代號分檔 · 高效壓縮 · 快速查詢                     │         │
│  └─────────────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────────┘
```

---

##  數據流水線（Pipeline）

### 雙源頭數據擷取

```
TWSE API (上市)                TPEx API (上櫃)
https://www.twse.com.tw/        https://www.tpex.org.tw/
     │                               │
     │ verify=True                    │ verify=False (SSL 憑證問題)
     │                               │
     ▼                               ▼
 20260619.json                  OTC_20260619.json
 (fields9/data9 格式)           (tables[0].fields/data 格式)
     │                               │
     └───────────┬───────────────────┘
                 ▼
       step2_etl_and_db.py
```

### ETL 處理模式

#### 模式 A：增量處理（預設，推薦）

```
步驟:
  1. 檢查 ETL_Status 表 → 找出 status=pending 的 JSON 檔案
  2. 只讀取 pending 檔案，解析 + 清洗
  3. 按股票代號分組
  4. 對每檔股票:
     a. 讀取現有 parquet（若存在）
     b. 附加新資料行
     c. 去重 + 排序 → 回寫
  5. 更新 Company_Dim（新股票才 INSERT）
  6. 標記檔案為 done

優點: 只處理新資料，秒級完成
```

#### 模式 B：完整重建

```
python step2_etl_and_db.py --rebuild
python fetch_data.py --rebuild

步驟:
  1. 讀取 staging/ 中所有 JSON（上市 + 上櫃）
  2. 全部合併 → 按股票代號分組
  3. 重新寫入所有 parquet 檔案
  4. 更新 Company_Dim
  5. 全部標記為 done

優點: 修復資料一致性
缺點: 約 10-12 分鐘
```

### 抓取流程（fetch_data.py）

```
                      fetch_data.py
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
  --fetch-only        --etl-only         預設（抓取+ETL）
     │                   │                   │
     ▼                   ▼                   │
  step1_fetcher      step2_etl_db           │
  ┌──────────┐      ┌────────────┐          │
  │ init_db  │      │ ETL_Status │          │
  │ fetch_id │      │ (增量)     │          │
  │ fetch_otc│      │ or --rebuild          │
  └──────────┘      └────────────┘          │
         └──────────────────┬────────────────┘
                            ▼
              step3_fundamentals.py
              (選擇性，--with-fundamentals)
```

---

##  資料庫 Schema

### stock_warehouse.db

```sql
-- 股票維度（含上市/上櫃）
CREATE TABLE Company_Dim (
    證券代號 TEXT PRIMARY KEY,
    證券名稱 TEXT,
    產業類別 TEXT,
    狀態 TEXT DEFAULT '上市',        -- '上市' | '上櫃'
    更新時間 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 族群標籤
CREATE TABLE Tag_Dim (
    Tag_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Tag_Name TEXT UNIQUE
);

-- 股票↔標籤多對多
CREATE TABLE Company_Tag_Map (
    證券代號 TEXT,
    Tag_ID INTEGER,
    PRIMARY KEY (證券代號, Tag_ID),
    FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號),
    FOREIGN KEY (Tag_ID) REFERENCES Tag_Dim(Tag_ID)
);

-- 除權息事件
CREATE TABLE Dividend_Fact (
    事件_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    證券代號 TEXT,
    除權息日期 TEXT,
    現金股利 REAL DEFAULT 0.0,
    股票股利 REAL DEFAULT 0.0,
    FOREIGN KEY (證券代號) REFERENCES Company_Dim(證券代號)
);

-- ETL 狀態追蹤（增量處理核心）
CREATE TABLE ETL_Status (
    檔案名稱 TEXT PRIMARY KEY,        -- '20260619.json' | 'OTC_20260619.json'
    日期 TEXT,
    市場 TEXT,                        -- 'TWSE' | 'TPEx'
    狀態 TEXT DEFAULT 'pending',       -- 'pending' | 'done'
    更新時間 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### task_status.db

```sql
CREATE TABLE fetch_status (
    date TEXT PRIMARY KEY,
    status TEXT                       -- 'pending' | 'success' | 'error'
);
```

---

##  資料流向場景

### 場景 1：用戶查詢單檔股票分析

```
User Input: 股票代號 (2330)
    ↓
StockAnalyzer.__init__("2330")
    ↓
data_query.get_stock_price_history("2330")  → parquet_data/2330.parquet
    ↓
TechnicalAnalysis.calculate_indicators()
    ↓
FundamentalAnalyzer.analyze("2330")  → P/E, P/B, ROE, ROA 等
    ↓
Display: K 線圖 + 技術指標 + 基本面分析
```

### 場景 2：用戶執行篩選

```
User Input: 篩選條件組合（價格 + RSI + 產業）
    ↓
StockFilter.filter_by_price_range(100, 500)
    → .filter_by_rsi(max_rsi=70)
    → .filter_by_industry("半導體")
    → .execute()
    ↓
For each stock_id in result set:
    ├─ 從 Company_Dim 讀取基本資料
    ├─ 從 parquet_data/*.parquet 讀取最新行情
    └─ 檢查所有條件
    ↓
Display: 篩選結果表格
```

### 場景 3：用戶管理族群標籤

```
User Input: 選擇標籤「AI 概念股」+ 選擇股票「2330」
    ↓
ui/app.py → core.data.data_query
    ├─ add_tag("AI 概念股", "2330")     → INSERT INTO Tag_Dim + Company_Tag_Map
    └─ remove_tag("AI 概念股", "2330")  → DELETE FROM Company_Tag_Map
    ↓
Display: 即時更新標籤列表
```

### 場景 4：回測策略

```
User Input: 股票、策略、時間範圍
    ↓
BacktestEngine(stock_id, dates, capital)
    ↓
For each day in date_range:
    ├─ 讀取 OHLC 數據（從 parquet）
    ├─ 調用信號函數
    ├─ 執行買賣邏輯
    └─ 更新組合價值
    ↓
計算績效指標
    ↓
Display: 返回率、勝率、淨值曲線
```

---

##  Web UI 架構

```
ui/app.py (Streamlit multi-page)
    │
    ├─ st.sidebar
    │   ├─ 📈 單檔分析
    │   ├─ 🏢 族群比較
    │   ├─ 🏷️ 族群分析 ← NEW
    │   │   └─ 標籤建立/刪除 + 搜尋式股票選擇器
    │   ├─ 🔍 選股篩選
    │   └─ 🎯 回測策略
    │
    └─ 頁面內容
        ├─ 搜尋式股票選擇器（支援文字搜尋）
        ├─ Plotly 交互式圖表
        └─ Pandas DataFrame 表格
```

### 主要元件

| 元件 | 功能 |
|------|------|
| `searchable_stock_select()` | 文字搜尋下拉選單，過濾 11,718 檔股票 |
| `render_group_analysis_page()` | 族群分析頁面（標籤 CRUD + 批次操作） |
| Plotly `fig` | K 線圖、指標圖、淨值曲線 |
| `st.dataframe` | 篩選/回測結果表格 |

---

##  設計原則

### 1. **分層隔離** (Layering)
- 數據訪問層屏蔽存儲細節（SQLite vs Parquet）
- 分析層獨立於 UI
- 易於單元測試和替換

### 2. **增量優先** (Incremental by Default)
- 預設使用增量 ETL，秒級完成
- 完整重建作為備援選項
- ETL_Status 表追蹤每個檔案的處理狀態

### 3. **雙存儲策略** (Dual Storage)
- SQLite: 維度資料、標籤、狀態追蹤（適合關聯查詢）
- Parquet: 時間序列資料（適合分析查詢）
- 兩者透過 `data_query` API 統一暴露

### 4. **開放封閉** (Open-Closed)
- 對擴展開放（新指標、策略、篩選條件）
- 對修改封閉
- 新策略無需修改核心代碼

### 5. **DRY** (Don't Repeat Yourself)
- 統一的數據查詢 API
- 共享的技術指標計算
- 復用的篩選邏輯

---

##  擴展指南

### 添加新技術指標

在 `TechnicalAnalysis` 中添加方法：

```python
@staticmethod
def new_indicator(prices, param1, param2):
    """新指標說明"""
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
    return {'action': 'BUY'|'SELL'|'HOLD', 'confidence': 0-1}
```

```python
engine.add_signal(StrategyLibrary.new_strategy)
```

---

##  性能優化

### 1. 數據結構
- Parquet: 列式存儲，壓縮率高，查詢快
- SQLite: 輕量級關係數據庫，便於複雜查詢
- ETL_Status: 避免重複讀取所有 JSON

### 2. 增量處理
- 日常更新只處理新 JSON（1-2 個檔案）
- 不重新寫入所有 11,718 個 parquet
- ETL_Status 表追蹤已完成的工作

### 3. 查詢優化
- 篩選時使用集合運算
- 批量讀取 Parquet 檔案
- 日期範圍預過濾

### 4. 計算優化
- 技術指標使用向量化操作 (Pandas/NumPy)
- 避免 Python 循環
- 緩存常用計算結果

---

##  安全與可靠性

### TPEx SSL 處理
- 櫃買中心憑證驗證失敗 → 使用 `verify=False`
- `urllib3.disable_warnings()` 抑制警告
- DNS 錯誤自動重試（最多 3 次，指數退避）

### 數據驗證
- JSON 格式檢查（TWSE fields9/data9 vs tables 陣列）
- 欄位名稱模糊匹配（`代號` → `證券代號`）
- 空值/異常值處理

### 錯誤處理
- 連續 5 次 API 錯誤自動中斷
- 重試機制（3 次，含退避）
- 檔案不存在、格式錯誤的優雅降級

---

## 未來擴展方向

1. **完整 OTC 歷史資料** ✅ 已完成（2539/2542 交易日，99.9%）
2. **增量 ETL 流水線** ✅ 已完成
3. **族群分析（標籤系統）** ✅ 已完成
4. **基本面分析** ✅ 已完成（P/E, P/B, ROE, ROA, 負債比，毛利率，淨利率）
5. **即時數據**: WebSocket 連接 TWSE/TPEx 即時行情
6. **高級指標**: 期貨指數、融資融券數據
7. **機器學習**: 價格預測、異常檢測
8. **投資組合**: 多檔資產配置、風險管理
9. **API 服務**: REST API 供第三方調用
10. **行動應用**: iOS/Android 應用
11. **國際市場**: 美股/港股等其他交易所

---

這就是整個系統的完整設計！
