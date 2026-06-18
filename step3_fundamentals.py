#!/usr/bin/env python3
"""
step3_fundamentals.py - 基本面資料抓取 (MOPS 公開資訊觀測站)

抓取兩類資料:
1. 月營收 (Revenue_Fact)   - 來自 MOPS t21sc03 月營收彙總表
2. 法說會 (Catalyst_Event) - 來自 MOPS 法人說明會一覽表

用法:
    python step3_fundamentals.py                  # 抓最近 3 個月營收 + 法說會
    python step3_fundamentals.py --months 12      # 抓最近 12 個月營收
    python step3_fundamentals.py --revenue-only   # 只抓營收
    python step3_fundamentals.py --events-only    # 只抓法說會
"""

import argparse
import sqlite3
import time
import random
import io
from datetime import datetime, date

import requests
import pandas as pd

DB_PATH = "stock_warehouse.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}


# ============================================================================
# 月營收抓取
# ============================================================================

def _to_number(val):
    """將字串轉為數值，失敗回 None"""
    try:
        s = str(val).replace(',', '').replace('%', '').strip()
        if s in ('', '-', '不適用', 'NA'):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def fetch_monthly_revenue(roc_year: int, month: int, market: str = "sii"):
    """
    抓取單月營收彙總表

    Args:
        roc_year: 民國年 (e.g. 115 = 2026)
        month: 月份 1-12
        market: 'sii' (上市) 或 'otc' (上櫃)

    Returns:
        list[dict] 營收資料，或 None
    """
    url = f"https://mopsov.twse.com.tw/nas/t21/{market}/t21sc03_{roc_year}_{month}_0.html"

    try:
        time.sleep(random.uniform(2.0, 4.0))
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = 'big5'

        if res.status_code != 200 or '查詢無資料' in res.text:
            return None

        # 用 pandas 解析 HTML 表格
        tables = pd.read_html(io.StringIO(res.text))
        if not tables:
            return None

        records = []
        ad_year = roc_year + 1911
        year_month = f"{ad_year}-{month:02d}"

        for tbl in tables:
            # 攤平多層欄位並移除空白
            if isinstance(tbl.columns, pd.MultiIndex):
                tbl.columns = [str(c[-1]) for c in tbl.columns]
            else:
                tbl.columns = [str(c) for c in tbl.columns]
            tbl.columns = [c.replace(' ', '').replace('　', '').replace('\n', '') for c in tbl.columns]

            # 找出包含「公司代號」的表
            code_col = next((c for c in tbl.columns if '公司代號' in c), None)
            if code_col is None:
                continue

            for _, row in tbl.iterrows():
                code = str(row.get(code_col, '')).strip()
                # 只保留純數字代號 (排除小計/合計列)
                if not code.isdigit():
                    continue

                def col(keyword):
                    c = next((x for x in tbl.columns if keyword in x), None)
                    return row.get(c) if c else None

                records.append({
                    '證券代號': code,
                    '年月': year_month,
                    '當月營收': _to_number(col('當月營收')),
                    '上月營收': _to_number(col('上月營收')),
                    '去年同月營收': _to_number(col('去年當月營收')),
                    '月增率': _to_number(col('上月比較增減')),
                    '年增率': _to_number(col('去年同月增減')),
                    '當月累計營收': _to_number(col('當月累計營收')),
                    '去年累計營收': _to_number(col('去年累計營收')),
                    '累計年增率': _to_number(col('前期比較增減')),
                })

        return records if records else None

    except Exception as e:
        print(f"  [Error] {roc_year}/{month} {market} 營收抓取失敗: {e}")
        return None


def save_revenue(records: list):
    """寫入 Revenue_Fact"""
    if not records:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for r in records:
        cursor.execute('''
            INSERT OR REPLACE INTO Revenue_Fact
            (證券代號, 年月, 當月營收, 上月營收, 去年同月營收, 月增率, 年增率,
             當月累計營收, 去年累計營收, 累計年增率)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['證券代號'], r['年月'], r['當月營收'], r['上月營收'],
            r['去年同月營收'], r['月增率'], r['年增率'],
            r['當月累計營收'], r['去年累計營收'], r['累計年增率']
        ))
    conn.commit()
    conn.close()
    return len(records)


def run_revenue(months_back: int = 3):
    """抓取最近 N 個月的營收 (上市+上櫃)"""
    print("\n" + "=" * 60)
    print(f"📊 抓取月營收資料 (最近 {months_back} 個月)")
    print("=" * 60)

    today = date.today()
    total = 0

    for i in range(months_back):
        # 計算往前第 i 個月 (營收約於次月 10 號公布)
        y = today.year
        m = today.month - 1 - i  # 上個月才有完整營收
        while m <= 0:
            m += 12
            y -= 1
        roc_year = y - 1911

        print(f"\n  📅 {y}-{m:02d} (民國{roc_year}年{m}月)")
        for market, label in [("sii", "上市"), ("otc", "上櫃")]:
            records = fetch_monthly_revenue(roc_year, m, market)
            if records:
                n = save_revenue(records)
                total += n
                print(f"     {label}: {n} 筆")
            else:
                print(f"     {label}: 無資料")

    print(f"\n✅ 月營收抓取完成，共 {total} 筆")


# ============================================================================
# 法說會 / 重大事件抓取
# ============================================================================

def fetch_investor_conferences(roc_year: int):
    """
    抓取法人說明會一覽表 (MOPS t100sb02_1)

    Args:
        roc_year: 民國年
    Returns:
        list[dict] 法說會事件
    """
    url = "https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1"

    records = []
    for market in ["sii", "otc"]:
        try:
            time.sleep(random.uniform(2.0, 4.0))
            payload = {
                'encodeURIComponent': '1',
                'step': '1',
                'firstin': '1',
                'off': '1',
                'TYPEK': market,
                'year': str(roc_year),
            }
            res = requests.post(url, data=payload, headers=HEADERS, timeout=15)
            res.encoding = 'utf-8'

            if res.status_code != 200:
                continue

            try:
                tables = pd.read_html(io.StringIO(res.text))
            except ValueError:
                continue

            for tbl in tables:
                tbl.columns = [str(c) for c in tbl.columns]
                code_col = next((c for c in tbl.columns if '公司代號' in c), None)
                date_col = next((c for c in tbl.columns if '日期' in c), None)
                if code_col is None:
                    continue

                for _, row in tbl.iterrows():
                    code = str(row.get(code_col, '')).strip()
                    if not code.isdigit():
                        continue
                    event_date = str(row.get(date_col, '')).strip() if date_col else ''
                    records.append({
                        '證券代號': code,
                        '日期': event_date,
                        '類型': '法說會',
                        '標題': '法人說明會',
                        '內容摘要': ' | '.join(
                            f"{c}:{row[c]}" for c in tbl.columns
                            if c not in (code_col,) and pd.notna(row[c])
                        )[:500],
                        '來源連結': url,
                    })
        except Exception as e:
            print(f"  [Error] 法說會 {market} 抓取失敗: {e}")

    return records


def save_events(records: list):
    """寫入 Catalyst_Event (避免重複)"""
    if not records:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0
    for r in records:
        # 用 證券代號+日期+類型 判重
        cursor.execute(
            "SELECT 1 FROM Catalyst_Event WHERE 證券代號=? AND 日期=? AND 類型=?",
            (r['證券代號'], r['日期'], r['類型'])
        )
        if cursor.fetchone():
            continue
        cursor.execute('''
            INSERT INTO Catalyst_Event (證券代號, 日期, 類型, 標題, 內容摘要, 來源連結)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (r['證券代號'], r['日期'], r['類型'], r['標題'], r['內容摘要'], r['來源連結']))
        saved += 1
    conn.commit()
    conn.close()
    return saved


def run_events():
    """抓取今年與去年的法說會"""
    print("\n" + "=" * 60)
    print("📅 抓取法人說明會資料")
    print("=" * 60)

    today = date.today()
    total = 0
    for y in [today.year, today.year - 1]:
        roc_year = y - 1911
        print(f"\n  📆 民國 {roc_year} 年 ({y})")
        records = fetch_investor_conferences(roc_year)
        if records:
            n = save_events(records)
            total += n
            print(f"     新增 {n} 筆法說會 (抓到 {len(records)} 筆)")
        else:
            print(f"     無資料")

    print(f"\n✅ 法說會抓取完成，共新增 {total} 筆")


# ============================================================================
# 產業別抓取 (TWSE ISIN)
# ============================================================================

def run_industry():
    """
    從 TWSE ISIN 抓取上市/上櫃公司的產業別，更新 Company_Dim.產業類別
    """
    print("\n" + "=" * 60)
    print("🏭 抓取公司產業別 (TWSE ISIN)")
    print("=" * 60)

    # strMode=2 上市, strMode=4 上櫃
    sources = [
        ("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", "上市"),
        ("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", "上櫃"),
    ]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total = 0

    for url, label in sources:
        try:
            time.sleep(random.uniform(1.5, 3.0))
            res = requests.get(url, headers=HEADERS, timeout=20)
            res.encoding = 'big5'

            tables = pd.read_html(io.StringIO(res.text))
            if not tables:
                print(f"  {label}: 無資料")
                continue

            tbl = tables[0]
            # 第一列為標題
            tbl.columns = [str(c) for c in tbl.iloc[0]]
            tbl = tbl[1:]

            code_name_col = next((c for c in tbl.columns if '有價證券代號' in c or '代號及名稱' in c), tbl.columns[0])
            industry_col = next((c for c in tbl.columns if '產業別' in c), None)

            if industry_col is None:
                print(f"  {label}: 找不到產業別欄位")
                continue

            count = 0
            for _, row in tbl.iterrows():
                raw = str(row[code_name_col]).strip()
                industry = str(row[industry_col]).strip()

                # 格式: "1101　台泥" (代號 全形空白 名稱)
                parts = raw.replace('\u3000', ' ').split()
                if not parts:
                    continue
                code = parts[0].strip()
                if not code.isdigit() or len(code) != 4:
                    continue
                if industry in ('', 'nan', 'None'):
                    continue

                cursor.execute(
                    "UPDATE Company_Dim SET 產業類別 = ? WHERE 證券代號 = ?",
                    (industry, code)
                )
                if cursor.rowcount > 0:
                    count += 1

            conn.commit()
            total += count
            print(f"  {label}: 更新 {count} 檔")

        except Exception as e:
            print(f"  [Error] {label} 產業別抓取失敗: {e}")

    conn.close()
    print(f"\n✅ 產業別更新完成，共 {total} 檔")


# ============================================================================
# 主程式
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="基本面資料抓取 (MOPS)")
    parser.add_argument("--months", type=int, default=3, help="抓取最近 N 個月營收 (預設 3)")
    parser.add_argument("--revenue-only", action="store_true", help="只抓營收")
    parser.add_argument("--events-only", action="store_true", help="只抓法說會")
    parser.add_argument("--industry-only", action="store_true", help="只抓產業別")
    args = parser.parse_args()

    # 確保 schema 已升級
    from core.schema import migrate
    migrate(DB_PATH)

    if args.events_only:
        run_events()
    elif args.revenue_only:
        run_revenue(args.months)
    elif args.industry_only:
        run_industry()
    else:
        run_industry()
        run_revenue(args.months)
        run_events()

    print("\n🎉 基本面資料抓取全部完成！")


if __name__ == "__main__":
    main()
