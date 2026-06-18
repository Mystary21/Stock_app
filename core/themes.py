#!/usr/bin/env python3
"""
core/themes.py - 主題族群關鍵字字典 + 自動標籤

提供一份「主題族群 → 關鍵字」對照字典，
用於根據公司名稱 / 法說會內容 / 產業別自動建議族群標籤。

維度分類:
  材料/製程、產品/應用、題材/供應鏈、客戶關聯
"""

import sqlite3

DB_PATH = "stock_warehouse.db"

# ============================================================================
# 主題族群字典
# 格式: 分類 -> { 族群名稱: [關鍵字, ...] }
# 關鍵字會比對公司名稱、產業別、法說會內容摘要
# ============================================================================

THEME_DICTIONARY = {
    "材料/製程": {
        "第三代半導體": ["第三代半導體", "化合物半導體", "寬能隙"],
        "氮化鎵(GaN)": ["氮化鎵", "GaN"],
        "碳化矽(SiC)": ["碳化矽", "SiC"],
        "矽光子": ["矽光子", "光子", "silicon photonics"],
        "先進封裝": ["先進封裝", "CoWoS", "SoIC", "封裝測試", "封測"],
    },
    "產品/應用": {
        "射頻元件": ["射頻", "RF", "PA", "功率放大"],
        "功率半導體": ["功率半導體", "功率元件", "MOSFET", "IGBT"],
        "記憶體": ["記憶體", "DRAM", "NAND", "Flash", "記憶體模組"],
        "面板": ["面板", "顯示器", "LCD", "OLED", "驅動IC"],
        "被動元件": ["被動元件", "電容", "電阻", "電感", "MLCC", "鉭電容"],
        "PCB/載板": ["PCB", "印刷電路板", "載板", "ABF", "電路板"],
        "光通訊": ["光通訊", "光收發", "矽光子", "CPO", "光模組"],
        "散熱": ["散熱", "均熱", "熱導", "風扇", "水冷"],
        "網通": ["網通", "交換器", "路由", "switch", "router"],
    },
    "題材/供應鏈": {
        "AI伺服器": ["AI伺服器", "伺服器", "server", "GPU", "HPC", "資料中心"],
        "低軌衛星": ["低軌衛星", "衛星", "LEO", "SpaceX", "Starlink"],
        "電動車": ["電動車", "EV", "車用", "電池", "充電"],
        "機器人": ["機器人", "人形機器人", "robot", "自動化"],
        "蘋果供應鏈": ["蘋果", "Apple", "iPhone", "AirPods"],
        "輝達供應鏈": ["輝達", "NVIDIA", "Nvidia", "GB200", "Blackwell"],
        "綠能/儲能": ["綠能", "儲能", "太陽能", "風電", "再生能源"],
        "半導體設備": ["半導體設備", "設備", "晶圓設備", "檢測設備"],
    },
    "客戶關聯": {
        "台積電供應鏈": ["台積電", "TSMC"],
        "特斯拉供應鏈": ["特斯拉", "Tesla"],
    },
}


def seed_theme_tags(db_path: str = DB_PATH):
    """將主題字典的族群名稱寫入 Tag_Dim (含分類)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 取得分類 ID 對照
    cursor.execute("SELECT Category_Name, Category_ID FROM Tag_Category")
    cat_map = dict(cursor.fetchall())

    added = 0
    for category, groups in THEME_DICTIONARY.items():
        cat_id = cat_map.get(category)
        for group_name in groups:
            cursor.execute(
                "SELECT Tag_ID FROM Tag_Dim WHERE Tag_Name = ?", (group_name,)
            )
            if cursor.fetchone():
                # 已存在 → 更新分類
                cursor.execute(
                    "UPDATE Tag_Dim SET Category_ID = ? WHERE Tag_Name = ?",
                    (cat_id, group_name)
                )
            else:
                cursor.execute(
                    "INSERT INTO Tag_Dim (Tag_Name, Category_ID) VALUES (?, ?)",
                    (group_name, cat_id)
                )
                added += 1

    conn.commit()
    conn.close()
    print(f"[Themes] 已植入主題族群標籤，新增 {added} 個")


def auto_suggest_tags(text: str) -> list:
    """
    根據一段文字 (公司名稱/產業別/法說會內容) 自動建議族群標籤

    Returns:
        list[tuple]: [(族群名稱, 分類, 命中關鍵字), ...]
    """
    if not text:
        return []
    text_lower = str(text).lower()
    suggestions = []
    for category, groups in THEME_DICTIONARY.items():
        for group_name, keywords in groups.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    suggestions.append((group_name, category, kw))
                    break
    return suggestions


def auto_tag_all_companies(db_path: str = DB_PATH, min_strength: float = 0.5):
    """
    對所有公司執行自動標籤 (根據 公司名稱 + 產業別 + 法說會內容)

    這只是「建議」，會以較低的關聯強度寫入，標明資料來源為 auto
    """
    from datetime import datetime

    seed_theme_tags(db_path)  # 確保標籤存在

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 取得 Tag 名稱 -> ID
    cursor.execute("SELECT Tag_Name, Tag_ID FROM Tag_Dim")
    tag_map = dict(cursor.fetchall())

    # 取得所有公司
    cursor.execute("SELECT 證券代號, 證券名稱, 產業類別 FROM Company_Dim")
    companies = cursor.fetchall()

    # 取得每家公司的法說會摘要 (合併)
    cursor.execute("SELECT 證券代號, GROUP_CONCAT(內容摘要, ' ') FROM Catalyst_Event GROUP BY 證券代號")
    event_map = dict(cursor.fetchall())

    now = datetime.now().isoformat()
    tagged = 0

    for code, name, industry in companies:
        # 組合判斷文字
        text = f"{name or ''} {industry or ''} {event_map.get(code, '')}"
        suggestions = auto_suggest_tags(text)

        for group_name, category, kw in suggestions:
            tag_id = tag_map.get(group_name)
            if tag_id is None:
                continue
            # 自動標籤關聯強度較低 (0.5)，避免覆蓋人工標記的高強度
            cursor.execute('''
                INSERT OR IGNORE INTO Company_Tag_Map
                (證券代號, Tag_ID, 關聯強度, 資料來源, 更新時間)
                VALUES (?, ?, ?, ?, ?)
            ''', (code, tag_id, min_strength, f"auto:{kw}", now))
            if cursor.rowcount > 0:
                tagged += 1

    conn.commit()
    conn.close()
    print(f"[Themes] 自動標籤完成，新增 {tagged} 筆股票-族群關聯")


if __name__ == "__main__":
    auto_tag_all_companies()
