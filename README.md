#  股市觀察工具

量化分析與選股篩選平台 — 支援上市（TWSE）+ 上櫃（TPEx）超過 11,700 檔商品

##  核心功能

### 1.  單檔股票分析
- **K 線圖與移動平均線**: MA20/MA50/MA200，支援買賣訊號標記
- **技術指標**: RSI、MACD、布林帶、隨機指標、ATR
- **歷史數據**: 上市 10 年 + 上櫃近 6 個月完整日資料

### 2.  族群比較分析
- **產業內對比**: 比較同產業不同股票表現
- **產業領頭股**: 按成交金額、價格等排序
- **漲跌排行**: 快速掌握贏家與輸家
- **相關性分析**: 計算產業內股票相關係數

### 3.  選股篩選
- **預定義篩選**:
  - 看漲信號（黃金交叉 + 價格 > SMA20）
  - 超賣股票（RSI < 30）
  - 超買股票（RSI > 70）
  - 成交量大漲股
- **自訂篩選**: 組合多個條件進行複雜篩選
  - 價格範圍、成交量、技術指標、產業類別

### 4.  族群分析（標籤系統）
- **自訂標籤**: 任意建立/刪除族群標籤（如「AI 概念股」、「高股息」）
- **多對多映射**: 一檔股票可打多個標籤，一個標籤可含多檔股票
- **即時持久化**: 所有標籤異動立即寫入 SQLite，頁面重整不遺失
- **批次操作**: 支援全選、批次貼標/去標
- **搜尋式股票選擇器**: 支援文字搜尋（如輸入「穩懋」過濾清單）

### 5.  量化策略回測
- **SMA 交叉策略**: 20 日線與 50 日線交叉
- **RSI 策略**: 超買超賣反轉策略
- **MACD 策略**: 動量指標策略
- **完整指標**:
  - 總報酬率、年化報酬率、最大虧損、勝率
  - 交易清單與組合淨值曲線

---

##  數據流水線

```
   TWSE (上市)           TPEx (上櫃)
  API daily       API daily (verify=False)
     │                    │
     ▼                    ▼
  20260619.json    OTC_20260619.json
     │                    │
     └────────┬───────────┘
              ▼
    step2_etl_and_db.py (增量/完整重建)
              │
     ┌────────┴────────┐
     ▼                  ▼
  stock_warehouse.db   parquet_data/
  ┌─────────────────┐  └─ 2330.parquet
  │ Company_Dim      │  └─ 3105.parquet
  │ Tag_Dim          │  └─ ...
  │ Company_Tag_Map  │
  │ ETL_Status       │
  │ Dividend_Fact    │
  └─────────────────┘
     │
     ▼
  [Web 儀表板 / CLI]
```

### 增量處理

```
每日更新: fetch_data.py
  1. 檢查 task_status.db → 只抓 pending 日期
  2. 抓取 TWSE + OTC（新 API）
  3. 增量 ETL → 只處理新 JSON，附加到既有 Parquet
  4. 完成（通常 < 5 秒）

完整重建: fetch_data.py --rebuild
  重新處理 staging/ 中所有 JSON，完整寫入 DB + Parquet
```

---

##  快速開始

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 一鍵更新資料 + 啟動

```bash
# 日常更新（增量模式）
python fetch_data.py

# 啟動儀表板
python main.py web --port 8503
```

瀏覽器自動打開: `http://localhost:8503`

### fetch_data.py 完整用法

```bash
python fetch_data.py                              # 抓取 + 增量 ETL
python fetch_data.py --end 2026-06-17             # 到指定日期
python fetch_data.py --start 2025-01-01           # 指定開始日期
python fetch_data.py --etl-only                   # 只跑 ETL（增量）
python fetch_data.py --fetch-only                 # 只抓取
python fetch_data.py --rebuild                    # 增量 ETL（完整重建）
python fetch_data.py --with-fundamentals          # 含基本面（產業/營收/法說）
python fetch_data.py --fundamentals-only          # 只抓基本面
```

或分步驟執行:

```bash
python step1_fetcher.py                           # Step 1: 抓取
python step2_etl_and_db.py                        # Step 2: 增量 ETL（預設）
python step2_etl_and_db.py --rebuild              # Step 2: 完整重建
python step3_fundamentals.py --industry-only      # Step 3: 產業別
python step3_fundamentals.py                      # Step 3: 營收 + 法說
```

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

---

##  項目結構

```
stock_app/
├── core/
│   ├── data.py           # 統一數據查詢 API（SQLite + Parquet）
│   ├── analysis.py       # 技術指標與族群分析
│   ├── filters.py        # 股票篩選引擎
│   ├── themes.py         # 族群自動標籤（基於關鍵字）
│   ├── database.py       # SQLAlchemy engine + session（供 init_db 使用）
│   └── schema.py         # DB schema 升級（migrate）
├── ui/
│   └── app.py            # Streamlit Web 應用（含 族群分析 頁面）
├── backtesting/
│   └── engine.py         # 回測框架
├── step1_fetcher.py       # 數據獲取（TWSE + TPEx API）
├── step2_etl_and_db.py    # ETL 清洗入庫（增量/重建雙模式）
├── step3_fundamentals.py  # 基本面抓取（產業/營收/法說會）
├── fetch_data.py          # 一鍵更新腳本
├── main.py                # CLI 主入口
├── init_db.py             # DB 初始化
├── stock_warehouse.db     # 主要資料庫
├── task_status.db         # 抓取狀態追蹤
├── pyproject.toml         # 項目配置
├── requirements.txt       # 依賴清單
├── README.md
├── ARCHITECTURE.md
└── QUICKSTART.md
```

---

##  資料庫架構

### stock_warehouse.db

| 表 | 說明 | 筆數 |
|-----|------|------|
| `Company_Dim` | 股票維度（含上市/上櫃狀態） | 11,718 |
| `Tag_Dim` | 族群標籤 | 動態 |
| `Company_Tag_Map` | 股票 ↔ 標籤多對多 | 動態 |
| `Dividend_Fact` | 除權息事件 | 動態 |
| `ETL_Status` | JSON 檔案處理狀態追蹤 | 9,810 |

### task_status.db

| 表 | 說明 |
|-----|------|
| `fetch_status` | 每日期抓取狀態（pending/success/error） |

---

##  技術棧

- **後端**: Python 3.12+
- **數據處理**: Pandas, NumPy
- **可視化**: Plotly, Streamlit
- **數據存儲**: SQLite, Parquet（按股票代號分檔）
- **數據源**:
  - 台灣證券交易所 (TWSE) — 上市股票
  - 櫃買中心 (TPEx) — 上櫃股票

---

##  技術指標

| 指標 | 說明 | 用途 |
|-----|------|------|
| **SMA** | 簡單移動平均 | 趨勢判斷 |
| **EMA** | 指數移動平均 | 快速反應 |
| **RSI** | 相對強度指標 | 超買/超賣 |
| **MACD** | 動量指標 | 買賣信號 |
| **BB** | 布林帶 | 波動範圍 |
| **ATR** | 平均真實波幅 | 波動率 |
| **Stochastic** | 隨機指標 | 超買/超賣 |

---

##  API 速查

```python
from core.data import data_query

stock = data_query.get_stock_by_id("2330")
df = data_query.get_stock_price_history("2330", "2024-01-01", "2024-12-31")
stocks = data_query.get_stocks_by_industry("半導體")

from core.analysis import StockAnalyzer
analyzer = StockAnalyzer("2330")
indicators = analyzer.get_latest_indicators()

from core.filters import StockFilter, PredefinedFilters
results = (StockFilter()
    .filter_by_price_range(100, 500)
    .filter_by_rsi(max_rsi=70)
    .filter_by_industry("半導體")
    .execute())

from core.themes import auto_tag_all_companies, get_stocks_by_tag
tech_stocks = get_stocks_by_tag("半導體")

from backtesting.engine import BacktestEngine, StrategyLibrary
engine = BacktestEngine("2330", "2024-01-01", "2024-12-31")
engine.add_signal(StrategyLibrary.sma_crossover_strategy)
results = engine.backtest()
```

---

## ⚠️ 免責聲明

本工具僅供分析參考，**不構成投資建議**。股票投資存在風險，應進行充分的風險評估。

##  數據來源

- **上市**: 台灣證券交易所 (TWSE) — `https://www.twse.com.tw/`
- **上櫃**: 櫃買中心 (TPEx) — `https://www.tpex.org.tw/`
- **更新頻率**: 每個交易日（增量模式）
- **歷史數據**: 上市 2016 年至今，上櫃 2016 年至今（99.9% 覆蓋率）

---

**版本**: 2.0.0  
**最後更新**: 2026-06-23
