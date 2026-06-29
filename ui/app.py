# ui/app.py - Streamlit Web 應用程序
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

from core.data import data_query
from core.analysis import StockAnalyzer, IndustryComparison, GroupAnalysis
from core.filters import StockFilter, PredefinedFilters
from backtesting.engine import BacktestEngine, StrategyLibrary

# ============================================================================
# 輔助函式：可搜尋股票下拉選單
# ============================================================================

def searchable_stock_select(label: str, key: str, all_stocks_df=None, separator: str = " - "):
    """顯示一個含文字搜尋的股票下拉選單，回傳 股票代號"""
    if all_stocks_df is None:
        all_stocks_df = data_query.get_all_stocks()
    options = {f"{row['證券代號']}{separator}{row['證券名稱']}": row['證券代號']
               for _, row in all_stocks_df.iterrows()}
    option_list = list(options.keys())

    search = st.text_input(f"🔍 {label}", key=f"srch_{key}", placeholder="輸入代號或名稱搜尋後選取")
    filtered = [o for o in option_list if not search or search.upper() in o.upper()]
    if not filtered:
        st.warning(f"無符合「{search}」的股票")
        return None

    selected = st.selectbox(label, filtered, key=f"sel_{key}")
    return options[selected]

# ============================================================================
# Streamlit 頁面配置
# ============================================================================
def render_group_analysis_page():
    st.title("🏷️ 族群分析")

    all_stocks_df = data_query.get_all_stocks()
    all_tags = data_query.get_all_tags()

    # 取得各標籤的股票數量
    tag_counts = {}
    for tag in all_tags:
        members = data_query.get_stocks_by_tag(tag)
        tag_counts[tag] = len(members)

    st.markdown("### 📌 所有族群")
    if not all_tags:
        st.info("尚無任何族群，請在下方建立")
    else:
        cols = st.columns(4)
        for i, tag in enumerate(all_tags):
            with cols[i % 4]:
                if st.button(f"{tag} ({tag_counts.get(tag, 0)})", key=f"tag_btn_{tag}", use_container_width=True):
                    st.session_state["selected_theme"] = tag

    selected_theme = st.session_state.get("selected_theme", all_tags[0] if all_tags else None)
    if not selected_theme and all_tags:
        selected_theme = all_tags[0]

    st.divider()

    if selected_theme:
        tab1, tab2 = st.tabs(["🔍 依族群管理股票", "🎯 依個股貼標籤"])

        # ===== Tab 1: 依族群管理股票 =====
        with tab1:
            st.subheader(f"🏷️ {selected_theme}")
            theme_stocks = data_query.get_stocks_by_tag(selected_theme)

            st.write("成份股：")
            if not theme_stocks.empty:
                for _, row in theme_stocks.iterrows():
                    col_a, col_b = st.columns([4, 1])
                    col_a.write(f"📌 **{row['證券代號']} {row['證券名稱']}**")
                    if col_b.button("🗑️ 移除", key=f"rm_{selected_theme}_{row['證券代號']}"):
                        data_query.remove_stock_tag(row['證券代號'], selected_theme)
                        st.rerun()
            else:
                st.info("此族群尚無成份股")

            st.markdown("---")
            chosen_code = searchable_stock_select("加入股票至此族群：", "group_add", all_stocks_df, separator=" ")
            if chosen_code is not None and st.button("確認加入", type="primary", key="t1_submit"):
                data_query.set_stock_tag(chosen_code, selected_theme, 0.9, "manual")
                st.rerun()

        # ===== Tab 2: 依個股貼標籤 =====
        with tab2:
            code2 = searchable_stock_select("選擇股票：", "stock_tag", all_stocks_df, separator=" ")
            if code2 is None:
                st.stop()
            name2 = data_query.get_stock_by_id(code2).get('證券名稱', '')

            current_tags_df = data_query.get_tags_of_stock(code2)
            current_tag_names = current_tags_df['族群'].tolist() if not current_tags_df.empty else []

            st.write(f"📈 **{code2} {name2}** 目前所屬族群：")
            if current_tag_names:
                st.markdown(" ".join([f"`{t}`" for t in current_tag_names]))
            else:
                st.caption("⚠️ 尚不屬於任何族群")

            updated = st.multiselect(
                "編輯族群標籤（可多選或輸入新名稱）：",
                options=all_tags,
                default=current_tag_names,
                key="t2_tags"
            )
            if st.button("💾 儲存變更", type="primary", key="t2_save"):
                # 先全部移除再重新加入
                for tag in current_tag_names:
                    data_query.remove_stock_tag(code2, tag)
                for tag in updated:
                    data_query.set_stock_tag(code2, tag, 0.9, "manual")
                st.rerun()


    
st.set_page_config(
    page_title="股市觀察工具",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂樣式
st.markdown("""
<style>
    .main {
        padding-top: 0;
    }
    h1 {
        color: #1f77b4;
    }
    h2 {
        color: #ff7f0e;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 側邊欄導航
# ============================================================================

st.sidebar.title("📊 股市觀察工具")
st.sidebar.divider()

page = st.sidebar.radio(
    "選擇功能",
    [
        "🏠 首頁",
        "📈 單檔分析",
        "🏢 族群比較",
        "🏷️ 族群分析",
        "🔍 選股篩選",
        "🎯 回測策略",
    ]
)

st.sidebar.divider()
st.sidebar.markdown("**系統狀態**")

# 資料新鮮度
freshness = data_query.get_data_freshness()
if freshness['latest_date']:
    st.sidebar.metric("最新資料", freshness['latest_date'])
else:
    st.sidebar.metric("最新資料", "⚠️ 無資料")

st.sidebar.metric("股票", freshness['total_stocks'])
st.sidebar.metric("產業", freshness['total_industries'])

# 待抓取
pending = data_query.get_pending_fetch_count()
if pending > 0:
    st.sidebar.warning(f"待抓取 {pending} 天資料")
else:
    st.sidebar.success("✅ 所有資料已抓取完畢")

# ============================================================================
# 首頁
# ============================================================================

if page == "🏠 首頁":
    st.title("📊 股市觀察工具")
    st.markdown("""
    歡迎使用股市觀察工具！這是一個功能完整的股票分析平台。
    
    ### 🎯 核心功能
    
    **1. 📈 單檔分析** - 深入分析單支股票
    - K線圖與移動平均線
    - 技術指標 (RSI, MACD, 布林帶等)
    - 歷史價格與統計數據
    
    **2. 🏢 族群比較** - 比較相同產業的股票
    - 產業內領頭股
    - 漲幅排行與跌幅排行
    - 產業績效統計
    - 股票相關性分析
    
    **3. 🏷️ 族群分析** - 互動式族群管理
    - Tag 標籤雲快速選取族群
    - 即時新增/移除股票至族群
    - 個股多標籤編輯
    - 資料庫即時同步
    
    **4. 🔍 選股篩選** - 根據條件篩選股票
    - 價格、成交量篩選
    - 技術指標篩選 (RSI、移動平均線等)
    - 預定義篩選組合 (看漲信號、超賣股等)
    
    **5. 🎯 回測策略** - 測試量化策略
    - SMA 交叉策略
    - RSI 超買超賣策略
    - MACD 策略
    - 自訂策略支持
    
    ---
    
    ### 📊 數據來源
    
    - **API**: 台灣證券交易所 (TWSE)
    - **數據範圍**: 2016 年至今
    - **更新頻率**: 每個交易日
    
    """)
    
    # 顯示最近漲幅榜
    st.divider()
    st.subheader("📈 最近漲幅榜 (Top 10)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**漲幅最大**")
        all_stocks_with_price = []
        for _, stock in all_stocks.iterrows():
            latest = data_query.get_latest_price(stock['證券代號'])
            if latest:
                all_stocks_with_price.append({
                    '證券代號': stock['證券代號'],
                    '證券名稱': stock['證券名稱'],
                    '收盤價': latest['收盤價'],
                    '漲跌': latest['漲跌'],
                })
        
        if all_stocks_with_price:
            df_gainers = pd.DataFrame(all_stocks_with_price).nlargest(10, '漲跌')
            st.dataframe(df_gainers, use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("**跌幅最大**")
        if all_stocks_with_price:
            df_losers = pd.DataFrame(all_stocks_with_price).nsmallest(10, '漲跌')
            st.dataframe(df_losers, use_container_width=True, hide_index=True)

# ============================================================================
# 單檔分析頁面
# ============================================================================

elif page == "📈 單檔分析":
    st.title("📈 單檔股票分析")
    
    # 股票選擇（含搜尋）
    stock_id = searchable_stock_select("選擇股票", "single_stock")
    if stock_id is None:
        st.stop()
    
    # 取得股票資訊
    stock_info = data_query.get_stock_by_id(stock_id)
    latest_price = data_query.get_latest_price(stock_id)
    analyzer = StockAnalyzer(stock_id)
    
    if stock_info and latest_price:
        # 顯示基本資訊
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("股票代號", stock_id)
        with col2:
            st.metric("股票名稱", stock_info.get('證券名稱') or 'N/A')
        with col3:
            st.metric("產業類別", stock_info.get('產業類別') or 'N/A')
        with col4:
            st.metric("收盤價", f"${latest_price['收盤價']:.2f}")
        with col5:
            change_color = "🟢" if latest_price['漲跌'] > 0 else "🔴" if latest_price['漲跌'] < 0 else "⚪"
            st.metric("漲跌", f"{change_color} {latest_price['漲跌']:.2f}")
        
        st.divider()
        
        # K線圖
        st.subheader("📊 K線圖與移動平均線")
        
        date_range = st.slider(
            "選擇日期範圍",
            min_value=analyzer.df['日期'].min().date(),
            max_value=analyzer.df['日期'].max().date(),
            value=(
                (analyzer.df['日期'].max() - timedelta(days=365)).date(),
                analyzer.df['日期'].max().date()
            ),
            format="YYYY-MM-DD"
        )
        
        df_filtered = analyzer.df[
            (analyzer.df['日期'].dt.date >= date_range[0]) &
            (analyzer.df['日期'].dt.date <= date_range[1])
        ]
        
        fig = go.Figure()
        
        # K線
        fig.add_trace(go.Candlestick(
            x=df_filtered['日期'],
            open=df_filtered['開盤價'],
            high=df_filtered['最高價'],
            low=df_filtered['最低價'],
            close=df_filtered['收盤價'],
            name='K線'
        ))
        
        # 移動平均線
        if 'SMA_20' in df_filtered.columns:
            fig.add_trace(go.Scatter(
                x=df_filtered['日期'],
                y=df_filtered['SMA_20'],
                name='SMA 20',
                line=dict(color='orange', width=1)
            ))
        
        if 'SMA_50' in df_filtered.columns:
            fig.add_trace(go.Scatter(
                x=df_filtered['日期'],
                y=df_filtered['SMA_50'],
                name='SMA 50',
                line=dict(color='blue', width=1)
            ))
        
        fig.update_layout(
            title=f"{stock_id} - {stock_info.get('證券名稱')} K線圖",
            yaxis_title="價格",
            xaxis_title="日期",
            template="plotly_white",
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 技術指標
        st.subheader("📈 技術指標")
        
        indicators = analyzer.get_latest_indicators()
        
        def fmt(val, fmt_str=".2f", prefix="", suffix=""):
            """安全格式化，None 回傳 N/A"""
            if val is None:
                return "N/A"
            return f"{prefix}{val:{fmt_str}}{suffix}"
        
        def rsi_signal(val):
            if val is None: return "⬜ 無資料"
            if val >= 70: return "🔴 超買，留意回調"
            if val <= 30: return "🟢 超賣，留意反彈"
            return "🟡 中性區間 (30-70)"
        
        def macd_signal(macd, signal):
            if macd is None or signal is None: return "⬜ 無資料"
            if macd > signal: return "🟢 MACD 上穿 Signal，偏多"
            return "🔴 MACD 下穿 Signal，偏空"
        
        def ma_signal(close, sma20, sma50):
            if close is None or sma20 is None or sma50 is None: return "⬜ 無資料"
            if close > sma20 > sma50: return "🟢 多頭排列，強勢上漲"
            if close < sma20 < sma50: return "🔴 空頭排列，弱勢下跌"
            if sma20 > sma50: return "🟡 短期均線上方，偏多"
            return "🟡 短期均線下方，偏空"
        
        def stoch_signal(k):
            if k is None: return "⬜ 無資料"
            if k >= 80: return "🔴 超買區間，留意賣壓"
            if k <= 20: return "🟢 超賣區間，留意買盤"
            return "🟡 中性"
        
        def vol_signal(vol):
            if vol is None: return "⬜ 無資料"
            if vol >= 3: return "🔴 高波動，風險偏高"
            if vol <= 1: return "🟢 低波動，走勢平穩"
            return "🟡 中等波動"
        
        close_val = indicators.get('收盤價')
        rsi_val = indicators.get('RSI_14')
        macd_val = indicators.get('MACD')
        macd_sig_val = indicators.get('MACD_Signal')
        sma20_val = indicators.get('SMA_20')
        sma50_val = indicators.get('SMA_50')
        stoch_val = indicators.get('Stoch_K')
        vol_val = indicators.get('Volatility')
        
        # RSI
        with st.expander("📊 RSI (相對強度指標, 14日) — 衡量超買/超賣", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("RSI (14)", fmt(rsi_val))
            with c2:
                st.markdown(f"**訊號**: {rsi_signal(rsi_val)}")
                st.caption("RSI > 70 為超買、< 30 為超賣。數值越高代表近期漲幅強勁，但也代表回調風險越高。")
        
        # MACD
        with st.expander("📊 MACD (移動平均收斂散度) — 動量趨勢指標", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("MACD", fmt(macd_val, ".4f"))
                st.metric("Signal", fmt(macd_sig_val, ".4f"))
            with c2:
                st.markdown(f"**訊號**: {macd_signal(macd_val, macd_sig_val)}")
                st.caption("MACD 線（12日EMA - 26日EMA）上穿 Signal 線（9日EMA）時為買進訊號，反之為賣出訊號。")
        
        # 移動平均線
        with st.expander("📊 移動平均線 (SMA) — 趨勢方向判斷", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("SMA 20", fmt(sma20_val, ".2f", "$"))
                st.metric("SMA 50", fmt(sma50_val, ".2f", "$"))
            with c2:
                st.markdown(f"**訊號**: {ma_signal(close_val, sma20_val, sma50_val)}")
                st.caption("SMA20（20日均線）代表短期趨勢，SMA50（50日均線）代表中期趨勢。\n股價在均線上方偏多，SMA20 > SMA50 為黃金交叉（看漲訊號）。")
        
        # 隨機指標
        with st.expander("📊 KD 隨機指標 (%K) — 短線超買超賣", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("%K", fmt(stoch_val))
            with c2:
                st.markdown(f"**訊號**: {stoch_signal(stoch_val)}")
                st.caption("%K > 80 為超買、< 20 為超賣。常用 %K 下穿 %D 作為賣出訊號，上穿為買入訊號。")
        
        # 波動率
        with st.expander("📊 波動率 (20日標準差) — 風險衡量", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("波動率", fmt(vol_val, ".2f", suffix="%"))
            with c2:
                st.markdown(f"**訊號**: {vol_signal(vol_val)}")
                st.caption("以近20日日報酬率的標準差衡量股價波動程度。波動率越高，代表價格起伏越大，持有風險相對越高。")
        
        # 基本面分析
        st.divider()
        st.subheader("📊 基本面分析")
        
        fundamentals = data_query.get_fundamentals(stock_id)
        if fundamentals:
            def fmt_basic(val):
                """格式化基本面數值"""
                if val is None:
                    return "N/A"
                if isinstance(val, float) and val >= 0:
                    return f"{val:.2f}"
                if isinstance(val, float) and val < 0:
                    return f"{val:.2f}"
                return f"{val}"
            
            def fmt_pct(val):
                """格式化百分比"""
                if val is None:
                    return "N/A"
                return f"{val:.2f}%"
            
            c1, c2, c3, c4, c5 = st.columns(5)
            
            with c1:
                st.metric("本益比 (P/E)", fmt_basic(fundamentals.get('pe_ratio')))
            with c2:
                st.metric("市帳率 (P/B)", fmt_basic(fundamentals.get('pb_ratio')))
            with c3:
                st.metric("ROE", fmt_pct(fundamentals.get('roe')))
            with c4:
                st.metric("ROA", fmt_pct(fundamentals.get('roa')))
            with c5:
                st.metric("淨利率", fmt_pct(fundamentals.get('net_margin')))
            
            st.divider()
            
            c1, c2, c3, c4 = st.columns(4)
            
            with c1:
                st.metric("負債比", fmt_pct(fundamentals.get('debt_ratio')))
            with c2:
                st.metric("毛利率", fmt_pct(fundamentals.get('gross_margin')))
            with c3:
                st.metric("EPS", fmt_basic(fundamentals.get('eps')))
            with c4:
                st.metric("BPS", fmt_basic(fundamentals.get('bps')))
            
            st.divider()
            st.caption("基本面分析資料來源：MOPS 財務報表 + 最新收盤價。指標計算基於最近一個會計年度財務數據。")
        
        else:
            st.info("⚠️ 尚未取得基本面資料，請先執行資料抓取")
        
        # 分析摘要
        st.divider()
        st.subheader("📋 分析摘要")
        
        summary = analyzer.get_analysis_summary()
        summary_df = pd.DataFrame([summary]).T
        summary_df.columns = ['值']
        
        st.dataframe(summary_df, use_container_width=True)

# ============================================================================
# 族群比較頁面
# ============================================================================

elif page == "🏢 族群比較":
    st.title("🏢 族群比較分析")
    st.caption("依「主題族群」(材料/製程、產品/應用、題材/供應鏈、客戶關聯) 分析，一檔股票可屬於多個族群")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 族群總覽", "🔀 多族群交叉篩選", "📊 族群深度分析",
        "⚖️ 族群PK", "✏️ 族群編輯"
    ])

    # ---- Tab 1: 族群總覽 ----
    with tab1:
        st.subheader("📋 所有族群總覽")
        overview = GroupAnalysis.get_group_overview()
        if overview.empty:
            st.info("尚無族群資料，請先執行 `python step3_fundamentals.py` 並到「族群編輯」頁標記股票")
        else:
            categories = overview['分類'].dropna().unique().tolist()
            for cat in categories:
                st.markdown(f"#### 🏷️ {cat}")
                cat_df = overview[overview['分類'] == cat][['Tag_Name', '股票數', '描述']]
                cat_df = cat_df.rename(columns={'Tag_Name': '族群名稱'})
                st.dataframe(cat_df, use_container_width=True, hide_index=True)

    # ---- Tab 2: 多族群交叉篩選 ----
    with tab2:
        st.subheader("🔀 多族群交叉篩選")
        st.caption("找出『同時屬於』或『屬於任一』多個族群的股票，例如：氮化鎵 + 低軌衛星")

        all_tags = data_query.get_all_tags()
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_tags = st.multiselect("選擇族群 (可多選)", all_tags, key="cross_tags")
        with col2:
            mode = st.radio("模式", ["AND (同時)", "OR (任一)"], key="cross_mode")

        if selected_tags:
            mode_val = "AND" if mode.startswith("AND") else "OR"
            result = GroupAnalysis.cross_filter(selected_tags, mode_val)
            if result.empty:
                st.warning("沒有符合條件的股票")
            else:
                st.success(f"找到 {len(result)} 檔股票")
                st.dataframe(result, use_container_width=True, hide_index=True)

    # ---- Tab 3: 族群深度分析 ----
    with tab3:
        st.subheader("📊 族群深度分析 (營收 + 股價)")

        all_tags = data_query.get_all_tags()
        selected_tag = st.selectbox("選擇族群", all_tags, key="deep_tag")

        if selected_tag:
            # 營收彙總
            rev_perf = GroupAnalysis.group_revenue_performance(selected_tag)
            if rev_perf:
                st.markdown(f"#### 💰 營收表現 (最新月份: {rev_perf.get('最新月份', 'N/A')})")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("成員數", rev_perf.get('成員數', 0))
                with c2:
                    avg_yoy = rev_perf.get('平均年增率')
                    st.metric("平均年增率", f"{avg_yoy}%" if avg_yoy is not None else "N/A")
                with c3:
                    st.metric("年增成長家數", rev_perf.get('年增成長家數', 0))
                with c4:
                    st.metric("年增衰退家數", rev_perf.get('年增衰退家數', 0))
            else:
                st.info("此族群尚無營收資料 (需執行 step3_fundamentals.py 抓取營收)")

            st.divider()

            # 股價表現
            st.markdown("#### 📈 成員股價表現")
            price_perf = GroupAnalysis.group_price_performance(selected_tag)
            if not price_perf.empty:
                price_perf = price_perf.sort_values('近20日報酬%', ascending=False, na_position='last')
                st.dataframe(price_perf, use_container_width=True, hide_index=True)

                # 近20日報酬長條圖
                chart_df = price_perf.dropna(subset=['近20日報酬%']).head(20)
                if not chart_df.empty:
                    fig = go.Figure(go.Bar(
                        x=chart_df['證券名稱'],
                        y=chart_df['近20日報酬%'],
                        marker_color=['green' if v > 0 else 'red' for v in chart_df['近20日報酬%']]
                    ))
                    fig.update_layout(
                        title=f"{selected_tag} 成員近20日報酬率",
                        yaxis_title="報酬率 (%)", template="plotly_white", height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("此族群尚無成員或股價資料")

    # ---- Tab 4: 族群 PK ----
    with tab4:
        st.subheader("⚖️ 族群 PK (多族群橫向比較)")
        all_tags = data_query.get_all_tags()
        pk_tags = st.multiselect("選擇要比較的族群 (建議 2-5 個)", all_tags, key="pk_tags")

        if len(pk_tags) >= 2:
            with st.spinner("分析中..."):
                compare_df = GroupAnalysis.compare_groups(pk_tags)
            st.dataframe(compare_df, use_container_width=True, hide_index=True)

            # 視覺化: 平均年增率 vs 平均報酬
            plot_df = compare_df.dropna(subset=['平均年增率%', '平均近20日報酬%'])
            if not plot_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(name='平均年增率%', x=plot_df['族群'], y=plot_df['平均年增率%']))
                fig.add_trace(go.Bar(name='平均近20日報酬%', x=plot_df['族群'], y=plot_df['平均近20日報酬%']))
                fig.update_layout(barmode='group', template="plotly_white", height=400,
                                  title="族群基本面 vs 股價動能")
                st.plotly_chart(fig, use_container_width=True)
        elif pk_tags:
            st.info("請至少選擇 2 個族群進行比較")

    # ---- Tab 5: 族群編輯 ----
    with tab5:
        st.subheader("✏️ 族群編輯 (手動標記股票)")
        st.caption("根據你對公司基本面/法說會/Guidance 的研究，將股票歸入族群")

        edit_stock_id = searchable_stock_select("選擇股票", "edit_stock")
        if edit_stock_id is None:
            st.stop()

        # 顯示該股票目前所屬族群
        st.markdown("#### 目前所屬族群")
        current_tags = data_query.get_tags_of_stock(edit_stock_id)
        if not current_tags.empty:
            st.dataframe(current_tags, use_container_width=True, hide_index=True)
        else:
            st.info("此股票尚未歸入任何族群")

        st.divider()
        col1, col2 = st.columns(2)

        # 新增族群
        with col1:
            st.markdown("#### ➕ 加入族群")
            all_tags = data_query.get_all_tags()
            add_mode = st.radio("方式", ["選現有族群", "新建族群"], key="add_mode")
            if add_mode == "選現有族群":
                tag_to_add = st.selectbox("族群", all_tags, key="tag_add")
            else:
                tag_to_add = st.text_input("新族群名稱", key="tag_new")

            strength = st.select_slider(
                "關聯強度",
                options=[0.3, 0.6, 0.9],
                value=0.9,
                format_func=lambda x: {0.3: "概念沾邊", 0.6: "有參與", 0.9: "主力業務"}[x],
                key="strength"
            )
            if st.button("加入", type="primary", key="btn_add"):
                if tag_to_add:
                    data_query.set_stock_tag(edit_stock_id, tag_to_add, strength, "manual")
                    st.success(f"已將 {edit_stock_id} 加入「{tag_to_add}」")
                    st.rerun()

        # 移除族群
        with col2:
            st.markdown("#### ➖ 移除族群")
            if not current_tags.empty:
                tag_to_remove = st.selectbox("選擇要移除的族群", current_tags['族群'].tolist(), key="tag_remove")
                if st.button("移除", key="btn_remove"):
                    data_query.remove_stock_tag(edit_stock_id, tag_to_remove)
                    st.success(f"已移除「{tag_to_remove}」")
                    st.rerun()
            else:
                st.caption("無可移除的族群")

# ============================================================================
# 族群分析頁面 (互動式族群管理)
# ============================================================================

elif page == "🏷️ 族群分析":
    render_group_analysis_page()

# ============================================================================
# 選股篩選頁面
# ============================================================================

elif page == "🔍 選股篩選":
    st.title("🔍 選股篩選")
    
    filter_type = st.radio(
        "選擇篩選方式",
        ["預定義篩選", "自訂篩選"]
    )
    
    if filter_type == "預定義篩選":
        st.subheader("📋 預定義篩選組合")
        
        predefined = st.selectbox(
            "選擇篩選條件",
            [
                "看漲信號 (黃金交叉 + 價格 > SMA20)",
                "超賣股票 (RSI < 30)",
                "超買股票 (RSI > 70)",
                "成交量大漲股",
            ]
        )
        
        if st.button("執行篩選", type="primary"):
            with st.spinner("篩選中..."):
                if predefined == "看漲信號 (黃金交叉 + 價格 > SMA20)":
                    result = PredefinedFilters.bullish_signal()
                elif predefined == "超賣股票 (RSI < 30)":
                    result = PredefinedFilters.oversold_stocks(30)
                elif predefined == "超買股票 (RSI > 70)":
                    result = PredefinedFilters.overbought_stocks(70)
                else:  # 成交量大漲股
                    result = PredefinedFilters.high_volume_gainers(10000000, 0)
                
                st.success(f"找到 {len(result)} 檔符合條件的股票")
                
                if not result.empty:
                    st.dataframe(result, use_container_width=True, hide_index=True)
    
    else:  # 自訂篩選
        st.subheader("🔧 自訂篩選組合")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**價格篩選**")
            price_min = st.number_input("最低價格", value=0, min_value=0)
            price_max = st.number_input("最高價格", value=1000, min_value=0)
        
        with col2:
            st.markdown("**成交量篩選**")
            min_volume = st.number_input("最低成交量", value=0, min_value=0, step=1000000)
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("**漲跌篩選**")
            change_min = st.number_input("最低漲跌", value=-50.0)
            change_max = st.number_input("最高漲跌", value=50.0)
        
        with col4:
            st.markdown("**產業篩選**")
            industries = data_query.get_all_industries()
            selected_industries = st.multiselect("選擇產業", industries)
        
        # 技術指標篩選
        st.markdown("**技術指標篩選**")
        col5, col6 = st.columns(2)
        
        with col5:
            rsi_min = st.number_input("RSI 最小值", value=0, min_value=0, max_value=100)
            rsi_max = st.number_input("RSI 最大值", value=100, min_value=0, max_value=100)
        
        with col6:
            use_golden_cross = st.checkbox("黃金交叉 (SMA20 > SMA50)")
            use_price_above_ma = st.checkbox("價格高於 SMA20")
        
        if st.button("執行自訂篩選", type="primary"):
            with st.spinner("篩選中..."):
                filter_obj = StockFilter()
                
                if price_max > 0:
                    filter_obj.filter_by_price_range(price_min, price_max)
                
                if min_volume > 0:
                    filter_obj.filter_by_volume(min_volume)
                
                filter_obj.filter_by_change_percent(change_min, change_max)
                
                if rsi_min > 0 or rsi_max < 100:
                    filter_obj.filter_by_rsi(rsi_min if rsi_min > 0 else None, 
                                           rsi_max if rsi_max < 100 else None)
                
                if use_golden_cross:
                    filter_obj.filter_by_moving_average_cross()
                
                if use_price_above_ma:
                    filter_obj.filter_by_price_above_ma(20)
                
                if selected_industries:
                    # 為每個產業分別篩選，然後合併
                    all_results = []
                    for industry in selected_industries:
                        industry_filter = StockFilter().filter_by_industry(industry)
                        # 複製所有條件
                        for cond, _ in filter_obj.conditions:
                            industry_filter.conditions.append(cond)
                        all_results.append(industry_filter.execute())
                    result = pd.concat(all_results, ignore_index=True).drop_duplicates()
                else:
                    result = filter_obj.execute()
                
                st.success(f"找到 {len(result)} 檔符合條件的股票")
                
                if not result.empty:
                    st.dataframe(result, use_container_width=True, hide_index=True)

# ============================================================================
# 回測策略頁面
# ============================================================================

elif page == "🎯 回測策略":
    st.title("🎯 量化策略回測")
    
    # 回測模式選擇
    mode = st.radio(
        "選擇回測模式",
        ["單股回測", "多股組合回測"]
    )
    
    if mode == "單股回測":
        st.subheader("📈 單股回測")
        
        col1, col2 = st.columns(2)
        
        with col1:
            stock_id = searchable_stock_select("選擇股票", "backtest_stock")
            if stock_id is None:
                st.stop()
        
        with col2:
            strategy = st.selectbox(
                "選擇策略",
                ["SMA 交叉策略", "RSI 超買超賣策略", "MACD 策略"]
            )
        
        # 回測參數
        col3, col4, col5 = st.columns(3)
        
        with col3:
            start_date = st.date_input("開始日期", value=datetime.now() - timedelta(days=365))
        
        with col4:
            end_date = st.date_input("結束日期", value=datetime.now())
        
        with col5:
            initial_capital = st.number_input("初始資本", value=100000, min_value=1000, step=1000)
        
        if st.button("開始回測", type="primary"):
            with st.spinner("回測中..."):
                try:
                    engine = BacktestEngine(
                        [stock_id],
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        initial_capital
                    )
                    
                    if strategy == "SMA 交叉策略":
                        engine.add_signal(StrategyLibrary.sma_crossover_strategy)
                    elif strategy == "RSI 超買超賣策略":
                        engine.add_signal(StrategyLibrary.rsi_strategy)
                    else:  # MACD
                        engine.add_signal(StrategyLibrary.macd_strategy)
                    
                   results = engine.backtest()
                
                # 顯示結果
                st.success("回測完成！")
                
                st.subheader("📊 回測結果")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("股票", stock_id)
                
                with col2:
                    st.metric("初始資本", f"${results['初始資本']:,.0f}")
                
                with col3:
                    final_value = results['最終價值']
                    profit = final_value - results['初始資本']
                    st.metric("最終價值", f"${final_value:,.0f}", 
                            delta=f"${profit:,.0f}")
                
                with col4:
                    st.metric("總報酬率", f"{results['總報酬率%']:.2f}%")
                
                col5, col6, col7 = st.columns(3)
                
                with col5:
                    st.metric("最大虧損", f"{results['最大虧損%']:.2f}%")
                
                with col6:
                    st.metric("勝率", f"{results['勝率%']:.2f}%")
                
                with col7:
                    st.metric("交易次數", results['總交易次數'])
                
                # 組合淨值曲線
                st.subheader("📈 組合淨值曲線")
                
                portfolio_df = results['組合淨值曲線']
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=portfolio_df['日期'],
                    y=portfolio_df['組合總值'],
                    name='組合總值',
                    line=dict(color='green', width=2)
                ))
                
                fig.update_layout(
                    title=f"{stock_id} 組合淨值曲線",
                    yaxis_title="價值 ($)",
                    xaxis_title="日期",
                    template="plotly_white",
                    height=400,
                    hovermode='x unified'
                ))
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 交易清單
                if results['交易清單']:
                    st.subheader("📋 交易清單")
                    trades_df = pd.DataFrame(results['交易清單'])
                    st.dataframe(trades_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"回測失敗: {str(e)}")


# ============================================================================
# 多股組合回測頁面
# ============================================================================

elif mode == "多股組合回測":
    st.subheader("📊 多股組合回測")
    
    st.caption("選擇多檔股票進行組合回測，資金平均分配到每檔股票")
    
    # 股票選擇
    st.markdown("**選擇回測股票**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        stock1 = searchable_stock_select("股票 1", "backtest_stock1")
    
    with col2:
        stock2 = searchable_stock_select("股票 2", "backtest_stock2")
    
    with col3:
        stock3 = searchable_stock_select("股票 3", "backtest_stock3")
    
    # 收集股票
    selected_stocks = []
    if stock1:
        selected_stocks.append(stock1)
    if stock2:
        selected_stocks.append(stock2)
    if stock3:
        selected_stocks.append(stock3)
    
    if not selected_stocks:
        st.warning("請至少選擇一檔股票")
    elif len(selected_stocks) < 2:
        st.info("建議至少選擇 2 檔股票進行組合回測")
    
    if st.button("開始組合回測", type="primary", disabled=len(selected_stocks) < 2):
        with st.spinner("回測中..."):
            try:
                engine = BacktestEngine(
                    selected_stocks,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    initial_capital
                )
                
                engine.add_signal(StrategyLibrary.sma_crossover_strategy)
                
                results = engine.backtest()
                
                st.success("組合回測完成！")
                
                st.subheader("📊 組合回測結果")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("股票數量", len(selected_stocks))
                
                with col2:
                    st.metric("股票列表", ", ".join(selected_stocks))
                
                with col3:
                    final_value = results['最終價值']
                    profit = final_value - results['初始資本']
                    st.metric("最終價值", f"${final_value:,.0f}", 
                            delta=f"${profit:,.0f}")
                
                with col4:
                    st.metric("總報酬率", f"{results['總報酬率%']:.2f}%")
                
                col5, col6, col7 = st.columns(3)
                
                with col5:
                    st.metric("最大虧損", f"{results['最大虧損%']:.2f}%")
                
                with col6:
                    st.metric("勝率", f"{results['勝率%']:.2f}%")
                
                with col7:
                    st.metric("交易次數", results['總交易次數'])
                
                # 組合淨值曲線
                st.subheader("📈 組合淨值曲線")
                
                portfolio_df = results['組合淨值曲線']
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=portfolio_df['日期'],
                    y=portfolio_df['組合總值'],
                    name='組合總值',
                    line=dict(color='green', width=2)
                ))
                
                fig.update_layout(
                    title=f"組合淨值曲線 ({', '.join(selected_stocks)})",
                    yaxis_title="價值 ($)",
                    xaxis_title="日期",
                    template="plotly_white",
                    height=400,
                    hovermode='x unified'
                ))
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 交易清單
                if results['交易清單']:
                    st.subheader("📋 交易清單")
                    trades_df = pd.DataFrame(results['交易清單'])
                    st.dataframe(trades_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"回測失敗：{str(e)}")


# ============================================================================
# 頁腳
# ============================================================================

st.divider()
st.markdown("""
---
**股市觀察工具** v1.0 | 數據來源：台灣證券交易所 | 僅供分析參考，不構成投資建議
""")
