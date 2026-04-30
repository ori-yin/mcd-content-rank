# -*- coding: utf-8 -*-
"""
app.py - 麦当劳内容排行榜 v3
使用方法: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import re
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(
    page_title="麦当劳内容排行榜",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── 品牌色 ─────────────────────────────────────────────────────
MCD_RED = "#E40004"
MCD_GOLD = "#FFBC0D"
MCD_GREEN = "#00A04A"
MCD_BG = "#FAFAFA"

# ─── 样式 ─────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* ─── 全局字体 ─── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap');
  html, body, .stApp {{
    font-family: 'Inter', 'PingFang SC', 'Helvetica Neue', sans-serif !important;
    background: {MCD_BG};
    color: #1a1a1a;
  }}

  /* ─── Streamlit 顶部导航条 ─── */
  .st-emotion-cache-1kyxreq {{
    background: {MCD_GOLD} !important;
  }}

  /* ─── 侧边栏：金色主题 ─── */
  [data-testid="stSidebar"] {{
    background: {MCD_GOLD} !important;
    border-right: 3px solid rgba(0,0,0,0.08);
    min-width: 240px !important;
    max-width: 240px !important;
    overflow: hidden !important;
  }}

  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] p {{
    color: #000000 !important;
    font-family: 'Inter', 'PingFang SC', sans-serif !important;
  }}

  [data-testid="stSidebar"] .stRadio label,
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stTextInput label,
  [data-testid="stSidebar"] .stDateInput label,
  [data-testid="stSidebar"] .stSlider label {{
    color: #000000 !important;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 4px;
  }}

  [data-testid="stSidebar"] hr {{
    border-color: rgba(0,0,0,0.15) !important;
    margin: 12px 0;
  }}

  [data-testid="stSidebar"] .stSlider > div {{
    padding: 4px 0;
  }}

  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{
    background: rgba(255,255,255,0.5) !important;
    border-radius: 6px !important;

  }}

  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [aria-valuenow] {{
    background: #DC0008 !important;
    border-radius: 6px !important;

  }}

  [data-testid="stSidebar"] .stSelectbox > div > div,
  [data-testid="stSidebar"] .stTextInput > div > div,
  [data-testid="stSidebar"] .stDateInput > div > div {{
    background: rgba(255,255,255,0.6) !important;
    border: 1px solid rgba(0,0,0,0.12) !important;
    border-radius: 10px !important;
    color: #000000 !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="select"] span {{
    color: #000000 !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="input"] {{
    color: #000000 !important;
  }}

  [data-testid="stSidebar"] .stDownloadButton > button {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-weight: 700;
    border: none !important;
    border-radius: 10px !important;
  }}

  /* ─── 页面布局 ─── */
  .block-container {{
    padding-top: 1.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
    background: {MCD_BG};
  }}

  /* ─── 顶部指标卡 ─── */
  div[data-testid="stMetricValue"] {{
    font-size: 22px !important;
    font-weight: 900 !important;
    color: {MCD_RED} !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: -0.02em;
  }}
  div[data-testid="stMetricLabel"] {{
    font-size: 11px !important;
    color: #666 !important;
    font-weight: 500;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }}
  div[data-testid="stMetricDelta"] {{
    display: none;
  }}

  /* ─── Tab 栏 ─── */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 2px solid #EFEFEF;
  }}
  .stTabs [data-baseweb="tab"] {{
    color: #888 !important;
    font-weight: 600;
    font-size: 14px;
    padding: 8px 16px;
    border-radius: 8px 8px 0 0;
    border-bottom: 3px solid transparent;
    transition: all 0.15s ease;
  }}
  .stTabs [data-baseweb="tab"]:hover {{
    color: {MCD_RED} !important;
  }}
  .stTabs [aria-selected="true"] {{
    color: {MCD_RED} !important;
    border-bottom: 3px solid {MCD_RED} !important;
    font-weight: 700;
  }}

  /* ─── 主标题卡片 ─── */
  .mcd-header {{
    background: #DC0008;
    border-radius: 16px;
    padding: 28px 36px;
    color: #FFFFFF;
    margin-bottom: 24px;
    border-left: 6px solid {MCD_GOLD};
  }}
  .mcd-header h1 {{
    font-size: 22px;
    font-weight: 900;
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
    color: #FFFFFF;
  }}
  .mcd-header p {{
    font-size: 13px;
    opacity: 1;
    margin: 0;
    font-weight: 500;
    color: #FFFFFF;
  }}

  /* ─── 排名徽章 ─── */
  .rank-badge {{
    display: inline-block;
    width: 30px; height: 30px;
    border-radius: 50%;
    text-align: center; line-height: 30px;
    font-weight: 900; font-size: 13px;
    margin-right: 8px;
    border: 2px solid transparent;
  }}
  .rank-1 {{
    background: {MCD_GOLD};
    color: {MCD_RED};
    border-color: rgba(255,255,255,0.5);
    box-shadow: 0 2px 8px rgba(255,188,13,0.5);
  }}
  .rank-2 {{
    background: #E8E8E8;
    color: #666;
    border-color: rgba(0,0,0,0.08);
  }}
  .rank-3 {{
    background: #FFBC0D;
    color: #000;
    border-color: rgba(0,0,0,0.1);
  }}
  .rank-other {{
    background: #F2F2F2;
    color: #AAA;
    border-color: transparent;
  }}

  /* ─── 内容卡片 ─── */
  .content-card {{
    background: #FFFFFF;
    border: 1px solid #EFEFEF;
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
  }}
  .content-card:hover {{
    box-shadow: 0 4px 20px rgba(228,0,4, 0.12);
    transform: translateY(-1px);
  }}
  .card-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 6px;
    line-height: 1.5;
    font-family: 'Inter', 'PingFang SC', sans-serif;
  }}
  .card-content {{
    font-size: 13px;
    color: #666;
    line-height: 1.7;
    margin-bottom: 12px;
  }}
  .card-meta {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 11px;
    color: #888;
  }}
  .card-meta span {{
    background: #F8F8F8;
    padding: 4px 10px;
    border-radius: 20px;
    font-weight: 500;
    border: 1px solid #EFEFEF;
  }}
  .card-score {{
    font-size: 26px;
    font-weight: 900;
    color: {MCD_RED};
    text-align: right;
    line-height: 1;
    font-family: 'Inter', sans-serif;
  }}
  .card-score-label {{
    font-size: 10px;
    color: #CCC;
    text-align: right;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  /* ─── 章节标题 ─── */
  .section-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin: 28px 0 14px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid {MCD_RED};
    letter-spacing: -0.01em;
  }}

  /* ─── 数据表格 ─── */
  .stDataFrame thead th {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em;
    border: none !important;
    padding: 10px 12px !important;
  }}
  .stDataFrame tbody tr:hover {{ background: rgba(228,0,4, 0.04) !important; }}
  .stDataFrame tbody td {{
    font-size: 13px !important;
    color: #333 !important;
    padding: 9px 12px !important;
    border-color: #F0F0F0 !important;
  }}

  /* ─── 清洗状态提示 ─── */
  .clean-status {{
    background: #FFF8F0;
    border: 1px solid {MCD_GOLD};
    border-left: 4px solid {MCD_GOLD};
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #000000;
    font-weight: 500;
  }}

  /* ─── 副文本 / 说明文字 ─── */
  .stCaption, p {{
    font-size: 12px !important;
    color: #AAA !important;
  }}

  /* ─── 数字高亮 ─── */
  .stAlert {{
    border-radius: 10px;
  }}

</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────
st.markdown(f"""
<div class="mcd-header">
  <h1>🏆 麦当劳内容排行榜</h1>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 一比一复刻 Ori 的数据清洗脚本（核心逻辑，原封不动）
# ═══════════════════════════════════════════════════════════════

def extract_title_from_forms(forms):
    """从 forms 列表中提取标题"""
    if not isinstance(forms, list):
        return None
    for item in forms:
        if item.get('code') == 'thing1' and item.get('value'):
            return item['value']
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if code.startswith('thing') and value:
            return value
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if not code.startswith('time') and value:
            return value
    return None


def extract_text_from_forms(forms):
    """从 forms 列表中提取正文"""
    if not isinstance(forms, list):
        return None
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if code in ['thing5', 'short_thing5'] and value:
            return value
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if code.startswith('thing') and code != 'thing1' and value:
            return value
    return None


def parse_message(raw):
    """将原始 JSON 消息解析为标题和正文"""
    if pd.isna(raw) or not isinstance(raw, str):
        return pd.Series({'标题': '', '内容': ''})

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return pd.Series({'标题': '', '内容': ''})

    title = data.get('title')
    if not title:
        title = extract_title_from_forms(data.get('forms'))
    if not title:
        attachments = data.get('attachments')
        if isinstance(attachments, list) and len(attachments) > 0:
            title = attachments[0].get('name', '')

    text = data.get('text')
    if not text:
        text = extract_text_from_forms(data.get('forms'))

    if not title and text:
        first_part = re.split(r'[。！？\n]', str(text).strip())[0].strip()
        if len(first_part) > 0:
            title = first_part
        else:
            title = str(text)[:20]

    title = str(title).strip() if title else ''
    text = str(text).strip() if text else ''

    # 清洗特殊字符
    title = title.replace('?', '').replace('\r\n', '').replace('\n', '').replace('\r', '')
    text = text.replace('?', '').replace('\r\n', '').replace('\n', '').replace('\r', '')

    return pd.Series({'标题': title, '内容': text})


def clean_raw_csv(uploaded_file) -> pd.DataFrame:
    """
    一比一复刻清洗逻辑：
    1. 尝试多种编码读取原始 CSV
    2. 检查是否有至少 15 列
    3. 读取第 O 列（索引 14，即第 15 列）
    4. 解析 JSON，提取标题和内容
    5. 合并回原 DataFrame，删除原始 JSON 列
    """
    bytes_data = uploaded_file.read()

    # 尝试多种编码（原脚本逻辑）
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(BytesIO(bytes_data), encoding=enc, on_bad_lines='skip')
            break
        except Exception:
            continue

    if df is None:
        raise ValueError("无法读取 CSV 文件，请检查文件格式")

    # 检查是否有至少 15 列（原脚本逻辑）
    if df.shape[1] < 15:
        raise ValueError(f"CSV 只有 {df.shape[1]} 列，第 15 列（O列）不存在")

    # 读取第 O 列（索引 14，原脚本逻辑）
    o_col = df.iloc[:, 14]

    # 执行解析（原脚本逻辑）
    parsed_df = o_col.apply(parse_message)

    # 合并回原 DataFrame，删除原始 JSON 列（原脚本逻辑）
    df['标题'] = parsed_df['标题']
    df['内容'] = parsed_df['内容']
    df = df.drop(df.columns[14], axis=1)

    return df

# ═══════════════════════════════════════════════════════════════
# App 主逻辑
# ═══════════════════════════════════════════════════════════════

# ─── 文件上传 + 清洗模式选择 ────────────────────────────────────
mode = st.radio(
    "数据类型",
    ["原始 CSV（含 JSON 列，需清洗）", "已清洗 CSV（直接使用）"],
    horizontal=True,
    help="原始 CSV：上传运行清洗脚本之前的文件；已清洗 CSV：运行完脚本后的文件"
)

uploaded = st.file_uploader(
    "📤 上传 CSV 文件",
    type=["csv"],
    help="支持 UTF-8、GBK、GB2312、Latin1 编码"
)

if uploaded:
    # ─── 读取数据 ───────────────────────────────────────────────
    if mode == "原始 CSV（含 JSON 列，需清洗）":
        with st.spinner("正在运行数据清洗脚本..."):
            try:
                df = clean_raw_csv(uploaded)
                col_count_before = df.shape[1] + 1  # +1 因为去掉了 JSON 列，加了 2 个新列
                # 清洗在 clean_raw_csv() 中静默完成
            except ValueError as e:
                st.error(str(e))
                st.stop()
    else:
        # 已清洗 CSV，直接读取（第一版方式）
        try:
            df = pd.read_csv(uploaded, encoding="gbk")
        except Exception:
            try:
                df = pd.read_csv(uploaded, encoding="utf-8")
            except Exception:
                df = pd.read_csv(uploaded, encoding="utf-8-sig")

    # ─── 解析日期列 ────────────────────────────────────────────
    date_col = "发送日期"
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # ─── 计算衍生指标 ─────────────────────────────────────────
    df["CTR"] = (df["点击人次"] / df["触达成功"] * 100).round(2)
    df["CTR"] = df["CTR"].replace([float("inf"), -float("inf")], 0).fillna(0)
    df["单均价"] = (df["订单Sales"] / df["订单GC"]).round(2)
    df["单均价"] = df["单均价"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # ─── Min-Max 归一化 ───────────────────────────────────────
    def minmax(series):
        mn, mx = series.min(), series.max()
        if mx == mn:
            return series * 0
        return (series - mn) / (mx - mn) * 100

    df["触达_norm"] = minmax(df["触达成功"])
    df["CTR_norm"] = minmax(df["CTR"])
    df["Sales_norm"] = minmax(df["订单Sales"])
    df["单均价_norm"] = minmax(df["单均价"])

    # ─── 侧边筛选 ─────────────────────────────────────────────
    with st.sidebar:
        st.markdown("**筛选条件**")

        # 日期范围筛选
        if date_col in df.columns and df[date_col].notna().any():
            min_dt = df[date_col].min().date()
            max_dt = df[date_col].max().date()
            default_start = max(min_dt, max_dt - timedelta(days=6))
            date_range = st.date_input(
                "📅 日期范围",
                value=(default_start, max_dt),
                min_value=min_dt,
                max_value=max_dt,
                help="筛选发送日期范围"
            )
        else:
            date_range = None

        # 计划类型筛选
        plan_types = ["全部"] + df["计划类型"].dropna().unique().tolist()
        selected_plan = st.selectbox("计划类型", plan_types)

        # 渠道筛选
        channels = ["全部"] + df["渠道"].dropna().unique().tolist()
        selected_channel = st.selectbox("渠道", channels)

        # 预算 Owner 筛选
        owner_col = "预算owner"
        if owner_col in df.columns:
            owners = ["全部"] + df[owner_col].dropna().unique().tolist()
        else:
            owners = ["全部"]
        selected_owner = st.selectbox("预算 Owner", owners)

        # 关键词搜索
        keyword = st.text_input("🔍 搜索标题/内容关键词", "")

        st.markdown("---")
        # 权重调整
        col_w, _ = st.columns([4, 1])
        with col_w:
            st.markdown("**权重配置**", help="综合评分 = 触达_归一 × 权重 + CTR_归一 × 权重 + Sales_归一 × 权重 + 单均价_归一 × 权重")


        w_reach = st.slider("触达量权重", 0.0, 1.0, 0.35, 0.05)
        w_ctr = st.slider("CTR权重", 0.0, 1.0, 0.15, 0.05)
        w_sales = st.slider("订单Sales权重", 0.0, 1.0, 0.40, 0.05)
        w_apu = st.slider("单均价权重", 0.0, 1.0, 0.10, 0.05)

        st.markdown("**排序方式**")
        sort_order = st.radio("综合评分排序", ["降序", "升序"], index=0, horizontal=True, label_visibility="collapsed")

        total_w = w_reach + w_ctr + w_sales + w_apu
        if total_w == 0:
            st.warning("权重总和为 0，请调整权重")
            norm_reach, norm_ctr, norm_sales, norm_apu = 0, 0, 0, 0
        else:
            # 归一化权重（除以总和），确保相对权重比例正确
            norm_reach = w_reach / total_w
            norm_ctr = w_ctr / total_w
            norm_sales = w_sales / total_w
            norm_apu = w_apu / total_w

    # ─── 计算综合评分（基于归一化权重 × 100）──────────────────
    df["综合评分"] = (
        df["触达_norm"] * norm_reach * 100
        + df["CTR_norm"] * norm_ctr * 100
        + df["Sales_norm"] * norm_sales * 100
        + df["单均价_norm"] * norm_apu * 100
    ).round(1)

    # 排名在筛选后重排，见下方筛选后处理

    # ─── 应用筛选 ─────────────────────────────────────────────
    dff = df.copy()

    if date_range is not None:
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_dt, end_dt = date_range
            if pd.notna(start_dt) and pd.notna(end_dt):
                dff = dff[
                    (dff[date_col] >= pd.to_datetime(start_dt)) &
                    (dff[date_col] <= pd.to_datetime(end_dt) + timedelta(days=1))
                ]

    if selected_plan != "全部":
        dff = dff[dff["计划类型"] == selected_plan]

    if selected_channel != "全部":
        dff = dff[dff["渠道"] == selected_channel]

    if selected_owner != "全部":
        dff = dff[dff[owner_col] == selected_owner]

    if keyword:
        kw = keyword.lower()
        title_col = "标题" if "标题" in dff.columns else "消息标题"
        content_col = "内容"
        dff = dff[
            dff[title_col].str.lower().str.contains(kw, na=False) |
            dff[content_col].str.lower().str.contains(kw, na=False)
        ]

    # ─── 筛选后重排排名 ────────────────────────────────────────
    if len(dff) > 0:
        asc = (sort_order == "升序")
        dff = dff.sort_values("综合评分", ascending=asc).reset_index(drop=True)
    dff["排名"] = dff.index + 1

    # ─── 顶部指标卡 ───────────────────────────────────────────
    total_rows = len(dff)
    total_score = dff["综合评分"].mean() if total_rows > 0 else 0
    top1_score = dff["综合评分"].max() if total_rows > 0 else 0
    avg_ctr = dff["CTR"].mean() if total_rows > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("上榜内容", f"{total_rows} 条")
    col2.metric("平均综合评分", f"{total_score:.1f}")
    col3.metric("最高综合评分", f"{top1_score:.1f}")
    col4.metric("平均 CTR", f"{avg_ctr:.2f}%")

    # ─── Tab 切换 ─────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["🏆 卡片排行榜", "📋 数据表格", "📈 可视化图表"])

    with tab1:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据，请调整筛选条件")
        else:
            st.markdown(f"**{total_rows} 条内容 · 按综合评分排序**")
            cards = list(dff.itertuples())

            for i in range(0, len(cards), 2):
                cols = st.columns([1, 1], gap="medium")
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(cards):
                        break
                    row = cards[idx]
                    rank = row.排名
                    if rank == 1:
                        badge_class = "rank-1"
                    elif rank == 2:
                        badge_class = "rank-2"
                    elif rank == 3:
                        badge_class = "rank-3"
                    else:
                        badge_class = "rank-other"

                    score = row.综合评分
                    if score >= 70:
                        score_color = MCD_RED
                    elif score >= 40:
                        score_color = "#E07B00"
                    else:
                        score_color = "#AAA"

                    with col:
                        date_val = getattr(row, '发送日期', None)
                        date_str = str(date_val)[:10] if date_val is not None and pd.notna(date_val) else ""
                        plan_type_val = getattr(row, '计划类型', None)
                        plan_type_short = str(plan_type_val)[:4] if plan_type_val is not None and pd.notna(plan_type_val) else ""
                        channel_val = getattr(row, '渠道', None)
                        channel_short = str(channel_val) if channel_val is not None and pd.notna(channel_val) else ""
                        owner_short = str(getattr(row, '预算owner', '')) if hasattr(row, '预算owner') else ''
                        title = str(getattr(row, '标题', '')) if getattr(row, '标题', '') else ''
                        content = str(getattr(row, '内容', '')) if getattr(row, '内容', '') else ''

                        if not title:
                            title = str(getattr(row, '消息标题', '')) if getattr(row, '消息标题', '') else ''

                        # 直接用列名从 namedtuple 取值（安全方式）
                        try:
                            reach = int(getattr(row, '触达成功', 0))
                        except (ValueError, TypeError):
                            reach = 0
                        try:
                            ctr_val = float(getattr(row, 'CTR', 0))
                        except (ValueError, TypeError):
                            ctr_val = 0.0
                        try:
                            gc_val = int(getattr(row, '订单GC', 0))
                        except (ValueError, TypeError):
                            gc_val = 0
                        try:
                            sales_val = float(getattr(row, '订单Sales', 0))
                        except (ValueError, TypeError):
                            sales_val = 0.0
                        try:
                            apu_val = float(getattr(row, '单均价', 0))
                        except (ValueError, TypeError):
                            apu_val = 0.0

                        st.markdown(f"""
                        <div class="content-card">
                          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div style="flex:1;">
                              <span class="rank-badge {badge_class}">{rank}</span>
                              <span style="font-size:12px; color:#888; background:#F5F5F5; padding:2px 8px; border-radius:12px;">
                                {plan_type_short} · {channel_short}
                              </span>
                              <span style="font-size:12px; color:#AAA; margin-left:8px;">{owner_short} · {date_str}</span>
                            </div>
                            <div>
                              <div class="card-score" style="color:{score_color};">{int(score)}</div>
                              <div class="card-score-label">综合评分</div>
                            </div>
                          </div>
                          <div class="card-title">【标题】{title[:80]}{'...' if len(title) > 80 else ''}</div>
                          <div class="card-content">{content[:200]}{'...' if len(content) > 200 else ''}</div>
                          <div class="card-meta">
                            <span>触达 {reach:,}</span>
                            <span>CTR {ctr_val:.2f}%</span>
                            <span>订单GC {gc_val:,}</span>
                            <span>订单Sales {int(sales_val):,}</span>
                            <span>单均价 {apu_val:.1f}</span>
                          </div>
                        </div>
                        """, unsafe_allow_html=True)

    with tab2:
        title_col = "标题" if "标题" in dff.columns else "消息标题"
        owner_c = owner_col if owner_col in dff.columns else None
        display_cols = ["排名", title_col, "内容", "计划类型", "渠道",
                         date_col, owner_c,
                         "触达成功", "点击人次", "CTR", "订单GC", "订单Sales", "单均价", "综合评分"]
        display_cols = [c for c in display_cols if c is not None]
        available = [c for c in display_cols if c in dff.columns]
        # 格式化副本：CTR加%号、订单Sales变整数
        disp_df = dff[available].copy()
        if 'CTR' in disp_df.columns:
            disp_df['CTR'] = disp_df['CTR'].apply(lambda x: f"{x:.2f}%")
        if '订单Sales' in disp_df.columns:
            disp_df['订单Sales'] = disp_df['订单Sales'].apply(lambda x: int(x) if pd.notna(x) else '')
        st.dataframe(
            disp_df,
            use_container_width=True,
            hide_index=True,
            height=600
        )
        csv_out = disp_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 下载排行榜 CSV",
            csv_out,
            "麦当劳内容排行榜.csv",
            "text/csv",
            use_container_width=True
        )

    with tab3:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据")
        else:
            top10 = dff.head(10)
            fig_bar = px.bar(
                top10, x="排名", y="综合评分",
                color="综合评分",
                color_continuous_scale=["#FFD700", "#DA291C"],
                text="综合评分",
                title="Top 10 综合评分"
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(
                template="plotly_white",
                showlegend=False,
                coloraxis_showscale=False,
                height=400
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            title_col = "标题" if "标题" in dff.columns else "消息标题"
            fig_scatter = px.scatter(
                dff,
                x="触达成功", y="订单Sales",
                size="CTR",
                color="综合评分",
                color_continuous_scale=["#FFD700", "#DA291C"],
                hover_name=title_col,
                title="触达量 vs 订单Sales（气泡大小=CTR，颜色=综合评分）"
            )
            fig_scatter.update_layout(template="plotly_white", height=450)
            st.plotly_chart(fig_scatter, use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="section-title">📊 触达量 Top 5</div>', unsafe_allow_html=True)
                top_reach = dff.nlargest(5, "触达成功")[["排名", title_col, "触达成功", "CTR", "综合评分"]]
                st.dataframe(top_reach, hide_index=True, use_container_width=True)
            with c2:
                st.markdown('<div class="section-title">💰 订单Sales Top 5</div>', unsafe_allow_html=True)
                top_sales = dff.nlargest(5, "订单Sales")[["排名", title_col, "订单Sales", "单均价", "综合评分"]]
                st.dataframe(top_sales, hide_index=True, use_container_width=True)

else:
    st.info("请上传 CSV 文件开始分析")