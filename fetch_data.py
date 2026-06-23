#!/usr/bin/env python3
"""
fetch_data.py - 一鍵資料抓取 + 清洗 + 入庫

用法:
    python fetch_data.py                     # 抓取到今天 (增量 ETL)
    python fetch_data.py --end 2026-06-17    # 抓取到指定日期
    python fetch_data.py --start 2025-01-01  # 指定開始日期
    python fetch_data.py --etl-only          # 只跑 ETL (增量模式)
    python fetch_data.py --fetch-only        # 只抓取，不跑 ETL
    python fetch_data.py --rebuild           # 完整重建 ETL (處理所有 JSON)
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path


def sync_staging_to_db():
    """將 staging/ 已有的 JSON 自動標記為 success，避免重複下載"""
    import sqlite3
    from pathlib import Path

    conn = sqlite3.connect('task_status.db')
    cursor = conn.cursor()

    staging_files = list(Path('staging').glob('*.json'))
    updated = 0
    for f in staging_files:
        raw = f.stem
        date_str = f'{raw[:4]}-{raw[4:6]}-{raw[6:8]}'
        cursor.execute(
            'UPDATE fetch_status SET status = ? WHERE date = ? AND status != ?',
            ('success', date_str, 'success')
        )
        if cursor.rowcount > 0:
            updated += 1

    conn.commit()
    conn.close()

    if updated > 0:
        print(f'   [同步] 已將 {updated} 個現有 JSON 標記為 success')


def run_fetcher(start_date: str, end_date: str):
    """執行 Step 1: 資料抓取"""
    print("\n" + "=" * 60)
    print("📡 Step 1 / 2 — 從 TWSE 抓取原始資料")
    print(f"   日期範圍: {start_date} → {end_date}")
    print("=" * 60)

    # 動態覆寫 step1 的常數，再呼叫其邏輯
    import step1_fetcher as s1
    import sqlite3
    import pandas as pd

    s1.START_DATE = start_date
    s1.END_DATE = end_date

    # 重新初始化 DB（補入新的日期任務）
    conn = s1.init_db()
    sync_staging_to_db()  # 將已有 JSON 同步為 success
    cursor = conn.cursor()

    cursor.execute(
        "SELECT date FROM fetch_status WHERE status IN ('pending', 'error') ORDER BY date ASC"
    )
    tasks = [row[0] for row in cursor.fetchall()]

    if not tasks:
        print("\n✅ 所有日期皆已抓取完畢，無需重新抓取。")
        conn.close()
        return

    print(f"\n準備抓取 {len(tasks)} 天的資料...")

    from tqdm import tqdm
    consecutive_errors = 0

    for date_str in tqdm(tasks, desc="抓取進度"):
        status, raw_json_data = s1.fetch_twse_data(date_str)

        if status == "success" and raw_json_data is not None:
            save_path = s1.STAGING_DIR / f"{date_str.replace('-', '')}.json"
            import json
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(raw_json_data, f, ensure_ascii=False)
            consecutive_errors = 0
        elif status == "error":
            consecutive_errors += 1
            if consecutive_errors >= 5:
                print("\n[中斷] 連續 5 次錯誤，可能被 TWSE 暫時封鎖。請稍後重試。")
                break

        cursor.execute(
            "UPDATE fetch_status SET status = ? WHERE date = ?", (status, date_str)
        )
        conn.commit()

    conn.close()
    print("\n✅ 資料抓取完成！")


def run_etl(rebuild: bool = False):
    """執行 Step 2: ETL 清洗與資料庫建置"""
    mode = "完整重建" if rebuild else "增量處理"
    print("\n" + "=" * 60)
    print(f"🔄 Step 2 / 2 — ETL {mode}")
    print("=" * 60)

    import step2_etl_and_db as s2
    if rebuild:
        s2.rebuild_main()
    else:
        s2.incremental_main()


def run_fundamentals(months: int = 3):
    """執行 Step 3: 基本面抓取 (產業別 + 月營收 + 法說會) 並自動標籤族群"""
    print("\n" + "=" * 60)
    print("📊 Step 3 — 基本面資料 (產業別/營收/法說會) + 族群自動標籤")
    print("=" * 60)

    import step3_fundamentals as s3
    from core.schema import migrate
    from core.themes import auto_tag_all_companies

    migrate()
    s3.run_industry()
    s3.run_revenue(months)
    s3.run_events()

    print("\n🏷️  執行族群自動標籤...")
    auto_tag_all_companies()


def main():
    parser = argparse.ArgumentParser(
        description="一鍵資料抓取 + 清洗入庫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
    python fetch_data.py                       # 抓取到今天
    python fetch_data.py --end 2026-06-17      # 抓取到指定日期
    python fetch_data.py --etl-only            # 只跑 ETL 清洗
    python fetch_data.py --fetch-only          # 只抓取，不清洗
        """
    )

    parser.add_argument(
        "--start", default="2016-01-01",
        help="開始日期 (預設: 2016-01-01, 格式: YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", default=datetime.today().strftime('%Y-%m-%d'),
        help="結束日期 (預設: 今天, 格式: YYYY-MM-DD)"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="只跑 ETL 清洗，不重新抓取"
    )
    parser.add_argument(
        "--fetch-only", action="store_true",
        help="只抓取資料，不跑 ETL"
    )
    parser.add_argument(
        "--with-fundamentals", action="store_true",
        help="同時抓取基本面 (產業別/月營收/法說會) 並自動標籤族群"
    )
    parser.add_argument(
        "--fundamentals-only", action="store_true",
        help="只抓基本面資料 (不抓股價)"
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="完整重建 ETL (重新處理所有 JSON，預設為增量模式)"
    )

    args = parser.parse_args()

    # 驗證日期格式
    try:
        start_dt = datetime.strptime(args.start, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end, '%Y-%m-%d')
    except ValueError as e:
        print(f"❌ 日期格式錯誤: {e}")
        sys.exit(1)

    if start_dt > end_dt:
        print(f"❌ 開始日期 ({args.start}) 不能晚於結束日期 ({args.end})")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════╗
║           股市資料一鍵更新工具                    ║
║  開始: {args.start}   結束: {args.end}       ║
╚══════════════════════════════════════════════════╝""")

    t_start = time.time()

    if args.fundamentals_only:
        run_fundamentals()
    elif args.etl_only:
        run_etl(rebuild=args.rebuild)
    elif args.fetch_only:
        run_fetcher(args.start, args.end)
    else:
        # 預設：抓取 + ETL (增量)
        run_fetcher(args.start, args.end)
        run_etl(rebuild=args.rebuild)
        if args.with_fundamentals:
            run_fundamentals()

    elapsed = time.time() - t_start
    mins, secs = divmod(int(elapsed), 60)

    print(f"""
╔══════════════════════════════════════════════════╗
║  ✅ 全部完成！耗時 {mins:02d}:{secs:02d}                        ║
║                                                  ║
║  啟動儀表板:                                      ║
║    python main.py web --port 8503                ║
╚══════════════════════════════════════════════════╝""")


if __name__ == "__main__":
    main()
