# api_client.py - 統一的 API 客戶端 (解耦 fetch_data.py)
"""
api_client.py - 統一的股票資料 API 客戶端

提供結構化的 API 呼叫介面，讓 fetch_data.py 不再硬 import step1_fetcher.py。

用法:
    from api_client import TWSEClient, TPExClient
    client = TWSEClient()
    status, data = client.fetch(date_str)
"""

import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional


# ================== 設定 ==================

STAGING_DIR = Path("staging")
DB_PATH = "task_status.db"

TWSE_API_BASE = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
TWSE_URL_TEMPLATE = (
    f"{TWSE_API_BASE}"
    f"?response=json&date={{date_str}}&type=ALLBUT0999"
)

TPEx_URL_TEMPLATE = (
    "https://www.tpex.org.tw/web/stock/aftertrading/"
    "daily_close_quotes/stk_quote_result.php"
    "?l=zh-tw&d={{year}}/{{month:02d}}/{{day:02d}}&stk=ALL&s=0,asc,1"
)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
REQUEST_TIMEOUT = 30

# ================== 通用重試機制 ==================

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY = 3
DEFAULT_BACKOFF = 2
DEFAULT_MAX_DELAY = 30


def fetch_with_retry(url: str, max_retries: int = DEFAULT_MAX_RETRIES,
                     base_delay: int = DEFAULT_BASE_DELAY, backoff: int = DEFAULT_BACKOFF,
                     max_delay: int = DEFAULT_MAX_DELAY,
                     headers: dict = None, timeout: int = REQUEST_TIMEOUT) -> Tuple[Optional[requests.Response], int]:
    """
    帶指數退避重試的 HTTP 請求。

    Args:
        url: 請求 URL
        max_retries: 最大重試次數
        base_delay: 基礎等待秒數
        backoff: 每次重試的倍數
        max_delay: 最大等待秒數
        headers: HTTP headers
        timeout: 請求超時秒數

    Returns:
        (response, status_code) tuple
    """
    if headers is None:
        headers = {'User-Agent': USER_AGENT}

    for attempt in range(max_retries + 1):
        try:
            res = requests.get(url, headers=headers, timeout=timeout)
            return res, res.status_code
        except Exception as e:
            if attempt == max_retries:
                print(f"[Error] 請求失敗: {url[:60]}... ({e})")
                return None, -1
            wait = min(base_delay * (backoff ** attempt), max_delay)
            print(f"[Retry {attempt+1}/{max_retries}] 等待 {wait} 秒後重試...")
            time.sleep(wait)

    return None, -1


# ================== TWSE 客戶端 ==================

class TWSEClient:
    """台灣證券交易所 API 客戶端"""

    def fetch(self, date_str: str) -> Tuple[str, Optional[dict]]:
        """
        抓取指定日期的上市股票資料。

        Returns:
            (status, data) - status: 'success'/'error'/'no_data'
        """
        url = TWSE_URL_TEMPLATE.format(date_str=date_str)

        res, status_code = fetch_with_retry(url, max_retries=DEFAULT_MAX_RETRIES,
                                            base_delay=DEFAULT_BASE_DELAY,
                                            backoff=DEFAULT_BACKOFF,
                                            max_delay=DEFAULT_MAX_DELAY,
                                            timeout=REQUEST_TIMEOUT)

        if res is None:
            return "error", None

        if status_code != 200:
            print(f"[Error] TWSE 回傳 HTTP {status_code}")
            return "error", None

        if 'application/json' not in res.headers.get('Content-Type', ''):
            return "no_data", None

        try:
            res_json = res.json()
        except Exception:
            return "error", None

        if res_json.get('stat') != 'OK':
            return "no_data", None

        return "success", res_json


# ================== TPEx 客戶端 ==================

class TPExClient:
    """台灣證券交易所 (櫃買中心) API 客戶端"""

    def fetch(self, date_str: str, max_retries: int = DEFAULT_MAX_RETRIES,
              base_delay: int = DEFAULT_BASE_DELAY, backoff: int = DEFAULT_BACKOFF,
              max_delay: int = DEFAULT_MAX_DELAY) -> Tuple[str, Optional[dict]]:
        """
        抓取指定日期的上櫃股票資料。

        Returns:
            (status, data) - status: 'success'/'error'/'no_data'
        """
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        year = dt.year
        month = dt.month
        day = dt.day
        url = TPEx_URL_TEMPLATE.format(year=year, month=month, day=day)

        res, status_code = fetch_with_retry(url, max_retries=max_retries,
                                            base_delay=base_delay,
                                            backoff=backoff,
                                            max_delay=max_delay,
                                            timeout=REQUEST_TIMEOUT)

        if res is None or status_code != 200:
            return "error", None

        if 'application/json' not in res.headers.get('Content-Type', ''):
            return "no_data", None

        try:
            raw = res.json()
        except Exception:
            return "error", None

        if str(raw.get('stat', '')).lower() != 'ok':
            return "no_data", None

        tables = raw.get('tables', [])
        if not tables:
            return "no_data", None

        # 找第一個有 代號/名稱 欄位的 table
        for tbl in tables:
            raw_fields = [str(c).strip() for c in tbl.get('fields', [])]
            if not any('代號' in f for f in raw_fields):
                continue
            all_rows = tbl.get('data', [])
            if not all_rows:
                continue

            # 建立欄位對應: TPEx 原生欄位 → 標準欄位
            remap = {
                '代號': '證券代號', '名稱': '證券名稱',
                '收盤': '收盤價', '開盤': '開盤價',
                '最高': '最高價', '最低': '最低價',
                '漲跌': '漲跌價差',
                '成交股數': '成交股數', '成交金額(元)': '成交金額',
                '成交金額': '成交金額', '成交筆數': '成交筆數',
                '本益比': '本益比',
            }
            mapped_fields = []
            for f in raw_fields:
                mapped = next((v for k, v in remap.items() if k in f), f)
                if mapped not in mapped_fields:
                    mapped_fields.append(mapped)

            result = {'fields9': mapped_fields, 'data9': all_rows}
            return "success", result

        return "no_data", None
