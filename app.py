"""
app.py - 麦当劳内容排行榜
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import re
import numpy as np
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
MCD_GOLD = "#FFC000"
MCD_GREEN = "#00A04A"
MCD_BG = "#FAFAFA"

# ─── 列名常量 ──────────────────────────────────────────────────
OWNER_COL = "预算owner"   

# ═══════════════════════════════════════════════════════════════
# 样式系统（排版优先，配色保持麦当劳红金绿）
# ═══════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
  /* ─── 全局字体与基础 ─── */
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;900&display=swap');
  html, body, .stApp {{
    font-family: 'PingFang SC', 'DM Sans', 'Microsoft YaHei', sans-serif !important;
    background: {MCD_BG};
    color: #1a1a1a;
    -webkit-font-smoothing: antialiased;
  }}

  /* ─── Streamlit 顶部导航条（隐藏）── */
  .st-emotion-cache-1kyxreq {{
    background: transparent !important;
  }}
  #MainMenu {{ visibility: hidden; }}
  footer {{ visibility: hidden; }}
  header {{ visibility: hidden; }}

  /* ─── 侧边栏：金色主题 + 精致排版 ─── */
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {MCD_GOLD} 0%, #FFD54F 100%) !important;
    border-right: none;
    padding: 12px 16px 24px 8px !important;
  }}
  [data-testid="stSidebar"] > div:first-child {{
    padding-top: 0 !important;
  }}
  /* 去掉侧边栏顶部大段空白 */
  [data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
    display: none !important;
  }}
  section[data-testid="stSidebarSidebar"] > div > div:nth-child(1) {{
    min-height: 0 !important;
    padding-top: 0 !important;
    margin-top: 0 !important;
  }}

  /* 侧边栏分区标题 */
  [data-testid="stSidebar"] > div > div > div > div >
    div:first-child > [data-testid="stVerticalBlock"] > 
    div:first-child > [data-testid="stMarkdownContainer"] {{
    }}
  .sidebar-section-title {{
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: rgba(0,0,0,0.45) !important;
    margin: 20px 0 10px 4px !important;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(0,0,0,0.1);
  }}

  /* 侧边栏控件统一样式 */
  [data-testid="stSidebar"] label {{
    color: rgba(0,0,0,0.7) !important;
    font-weight: 600 !important;
    font-size: 12px !important;
  }}
  [data-testid="stSidebar"] .stSelectbox > div > div,
  [data-testid="stSidebar"] .stTextInput > div > div,
  [data-testid="stSidebar"] .stDateInput > div > div {{
    background: rgba(255,255,255,0.7) !important;
    border: 1px solid rgba(0,0,0,0.08) !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
  }}
  [data-testid="stSidebar"] [data-baseweb="select"] span,
  [data-testid="stSidebar"] [data-baseweb="input"] {{
    color: #1a1a1a !important;
    font-size: 13px !important;
  }}

  /* 侧边栏 Radio 水平紧凑 */
  [data-testid="stSidebar"] [data-testid="stRadio"] > div {{
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
  }}
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {{
    gap: 6px !important;
  }}
  [data-testid="stSidebar"] [data-testid="stRadio"] label {{
    font-size: 11px !important;
    padding: 6px 12px !important;
    border-radius: 20px !important;
    border: 1px solid rgba(0,0,0,0.12) !important;
    background: rgba(255,255,255,0.5) !important;
  }}
  [data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="checked"] {{
    background: {MCD_RED} !important;
    color: #fff !important;
    border-color: {MCD_RED} !important;
  }}

  /* 文件上传区 */
  [data-testid="stSidebar"] [data-testid="stFileUploader"] > div > div {{
    border: 2px dashed rgba(0,0,0,0.15) !important;
    border-radius: 14px !important;
    padding: 16px !important;
    background: rgba(255,255,255,0.4) !important;
    transition: all 0.2s ease;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploader"]:hover > div > div {{
    border-color: {MCD_RED} !important;
    background: rgba(255,255,255,0.65) !important;
  }}

  /* Slider */
  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{
    background: transparent !important;
    border-radius: 4px !important;
    height: 4px !important;
  }}
  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [aria-valuenow] {{
    background: {MCD_RED} !important;
    border-radius: 50% !important;
    width: 16px !important;
    height: 16px !important;
    box-shadow: 0 1px 4px rgba(228,0,4,0.25) !important;
  }}
  /* Slider 容器紧凑 */
  [data-testid="stSidebar"] .stSlider > div {{
    padding-top: 0 !important;
    padding-bottom: 2px !important;
  }}

  /* Expander (权重配置) */
  [data-testid="stSidebar"] .stExpander {{
    background: rgba(255,255,255,0.35) !important;
    border: 1px solid rgba(0,0,0,0.08) !important;
    border-radius: 12px !important;
  }}
  [data-testid="stSidebar"] .stExpander [data-testid="stExpanderContent"] {{
    padding: 16px !important;
  }}
  /* Expander 内 slider 去掉多余分隔线 */
  [data-testid="stSidebar"] .stExpander hr {{
    display: none !important;
  }}
  [data-testid="stSidebar"] .stExpander .stSlider {{
    padding-top: 2px !important;
    padding-bottom: 2px !important;
    margin-top: 2px !important;
    margin-bottom: 2px !important;
  }}

  /* 下载按钮 */
  [data-testid="stSidebar"] .stDownloadButton > button,
  .stDownloadButton > button {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-weight: 700;
    border: none !important;
    border-radius: 10px !important;
    padding: 8px 20px !important;
  }}

  /* ─── 主内容区 ─── */
  .block-container {{
    padding-top: 1rem;
    padding-left: 2.5rem;
    padding-right: 2.5rem;
    max-width: 1400px;
    background: {MCD_BG};
  }}

  /* ─── Header 卡片 ─── */
  .mcd-header {{
    background: linear-gradient(135deg, {MCD_RED} 0%, #C00003 100%);
    border-radius: 16px;
    padding: 32px 40px;
    color: #FFFFFF;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
  }}
  .mcd-header::after {{
    content: '';
    position: absolute;
    top: -30px;
    right: -30px;
    width: 120px;
    height: 120px;
    background: rgba(255,255,255,0.06);
    border-radius: 50%;
  }}
  .mcd-header::before {{
    content: '';
    position: absolute;
    bottom: -20px;
    right: 80px;
    width: 80px;
    height: 80px;
    background: rgba(255,255,255,0.04);
    border-radius: 50%;
  }}
  .mcd-header h1 {{
    font-size: 24px;
    font-weight: 900;
    margin: 0 0 4px 0;
    letter-spacing: -0.03em;
    color: #FFFFFF;
    position: relative;
    z-index: 1;
  }}
  .mcd-header .header-sub {{
    font-size: 13px;
    opacity: 0.85;
    margin: 0;
    font-weight: 400;
    color: #FFFFFF;
    position: relative;
    z-index: 1;
  }}

  /* ─── 上传区域（主内容区）── */
  .upload-zone {{
    background: #FFFFFF;
    border: 2px dashed #E0E0E0;
    border-radius: 16px;
    padding: 28px;
    text-align: center;
    margin-bottom: 24px;
    transition: all 0.2s ease;
  }}
  .upload-zone:hover {{
    border-color: {MCD_RED};
    background: #FFFDFD;
  }}

  /* ─── 指标卡：轻量化 ─── */
  div[data-testid="stMetricValue"] {{
    font-size: 26px !important;
    font-weight: 900 !important;
    color: #1a1a1a !important;
    font-family: 'DM Sans', 'PingFang SC', sans-serif !important;
    letter-spacing: -0.02em;
  }}
  div[data-testid="stMetricLabel"] {{
    font-size: 11px !important;
    color: #999 !important;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-top: 4px;
  }}
  div[data-testid="stMetricDelta"] {{
    display: none;
  }}
  div[data-testid="stMetric"] {{
    background: #FFFFFF !important;
    border: 1px solid #F0F0F0 !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
  }}

  /* ─── Tab 栏 ─── */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 6px;
    border-bottom: 2px solid #F0F0F0;
    margin-bottom: 24px;
  }}
  .stTabs [data-baseweb="tab"] {{
    color: #999 !important;
    font-weight: 600;
    font-size: 13px;
    padding: 10px 20px;
    border-radius: 10px 10px 0 0;
    border-bottom: 3px solid transparent;
    transition: all 0.15s ease;
    letter-spacing: 0.01em;
  }}
  .stTabs [data-baseweb="tab"]:hover {{
    color: {MCD_RED} !important;
    background: rgba(228,0,4,0.03);
  }}
  .stTabs [aria-selected="true"] {{
    color: {MCD_RED} !important;
    border-bottom: 3px solid {MCD_RED} !important;
    font-weight: 700;
    background: rgba(228,0,4,0.04);
  }}

  /* ─── 排名徽章 ─── */
  .rank-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px; height: 28px;
    border-radius: 50%;
    font-weight: 900; font-size: 12px;
    flex-shrink: 0;
  }}
  .rank-1 {{
    background: {MCD_GOLD};
    color: #7A5000;
    box-shadow: 0 2px 8px rgba(255,188,13,0.4);
  }}
  .rank-2 {{
    background: #E8E8E8;
    color: #666;
  }}
  .rank-3 {{
    background: #E8A000;
    color: #fff;
  }}
  .rank-other {{
    background: #F2F2F2;
    color: #AAA;
  }}

  /* ─── 内容卡片：核心升级 ─── */
  .content-card {{
    background: #FFFFFF;
    border: 1px solid #F0F0F0;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 16px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
    position: relative;
    overflow: visible;
  }}
  .content-card:hover {{
    box-shadow: 0 6px 24px rgba(228,0,4,0.08);
    transform: translateY(-2px);
    border-color: rgba(228,0,4,0.15);
  }}
  .card-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 6px;
    line-height: 1.55;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }}
  .card-content {{
    font-size: 12.5px;
    color: #777;
    line-height: 1.65;
    margin-bottom: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }}
  .card-meta {{
    display: flex;
    gap: 4px;
    flex-wrap: nowrap;
    font-size: 10.5px;
  }}
  .card-meta span {{
    background: #F7F7F7;
    padding: 3px 7px;
    border-radius: 14px;
    font-weight: 500;
    color: #888;
    border: 1px solid #F0F0F0;
    white-space: nowrap;
  }}
  .card-score {{
    font-size: 30px;
    font-weight: 900;
    text-align: right;
    line-height: 1;
    font-family: 'DM Sans', 'PingFang SC', sans-serif;
    letter-spacing: -0.02em;
  }}
  .card-score-label {{
    font-size: 10px;
    color: #BBB;
    text-align: right;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
  }}

  /* ─── 章节标题 ─── */
  .section-title {{
    font-size: 13px;
    font-weight: 700;
    color: #1a1a1a;
    margin: 24px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid {MCD_RED};
    letter-spacing: -0.01em;
  }}

  /* ─── 数据表格 ─── */
  .stDataFrame thead th {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em;
    border: none !important;
    padding: 12px 14px !important;
    text-transform: uppercase;
  }}
  .stDataFrame tbody tr:hover {{ background: rgba(228,0,4,0.03) !important; }}
  .stDataFrame tbody td {{
    font-size: 12.5px !important;
    color: #333 !important;
    padding: 10px 14px !important;
    border-color: #F5F5F5 !important;
  }}

  /* ─── 清洗状态提示 ─── */
  .clean-status {{
    background: #FFF9E6;
    border: 1px solid {MCD_GOLD};
    border-left: 4px solid {MCD_GOLD};
    border-radius: 12px;
    padding: 12px 20px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #1a1a1a;
    font-weight: 500;
  }}

  /* ─── Caption ─── */
  .stCaption {{
    font-size: 11px !important;
    color: #CCC !important;
  }}

  /* ─── Alert ─── */
  .stAlert {{
    border-radius: 12px;
  }}

  /* ─── 综合评分 Tooltip ─── */
  .score-info-wrap {{
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: middle;
    margin-left: 6px;
    cursor: help;
  }}
  .score-info-wrap .info-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #EEE;
    color: #999;
    font-size: 9px;
    font-weight: 900;
    transition: all 0.15s ease;
  }}
  .score-info-wrap:hover .info-icon {{
    background: {MCD_RED};
    color: #FFF;
    transform: scale(1.1);
  }}
  .score-tooltip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: calc(100% + 8px);
    right: 0;
    background: rgba(25,25,25,0.96);
    color: #FFFFFF;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 11.5px;
    white-space: pre-line;
    line-height: 1.65;
    min-width: 240px;
    max-width: 320px;
    text-align: left;
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
    z-index: 9999;
    pointer-events: none;
    transition: all 0.18s ease;
  }}
  .score-tooltip::after {{
    content: '';
    position: absolute;
    top: 100%;
    right: 12px;
    border: 6px solid transparent;
    border-top-color: rgba(25,25,25,0.96);
  }}
  .score-info-wrap:hover .score-tooltip {{
    visibility: visible;
    opacity: 1;
  }}

</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# Section 1: Header
# ═══════════════════════════════════════════════════════════════

today_str = datetime.now().strftime("%Y年%m月%d日")
st.markdown(f"""
<div class="mcd-header">
  <h1>麦当劳内容排行榜</h1>
  <p class="header-sub">Content Performance Ranking · {today_str}</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# Section 2: 数据清洗函数
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
    for item in (forms or []):
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

    title = title.replace('?', '').replace('\r\n', '').replace('\n', '').replace('\r', '')
    text = text.replace('?', '').replace('\r\n', '').replace('\n', '').replace('\r', '')

    return pd.Series({'标题': title, '内容': text})


def clean_raw_csv(uploaded_file) -> pd.DataFrame:
    bytes_data = uploaded_file.read()

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

    if df.shape[1] < 15:
        raise ValueError(f"CSV 只有 {df.shape[1]} 列，第 15 列（O列）不存在")

    o_col = df.iloc[:, 14]
    parsed_df = o_col.apply(parse_message)

    df['标题'] = parsed_df['标题']
    df['内容'] = parsed_df['内容']
    df = df.drop(df.columns[14], axis=1)

    return df

# ═══════════════════════════════════════════════════════════════
# Section 3: App 主逻辑
# ═══════════════════════════════════════════════════════════════

# ─── 文件上传区域（紧凑布局）───────────────────────────────────
col_left, col_right = st.columns([1.2, 1])
with col_left:
    mode = st.radio(
        "数据类型",
        ["原始 CSV（含 JSON 列）", "已清洗 CSV"],
        horizontal=True,
        label_visibility="visible",
        help="原始 CSV 含 JSON 需清洗；已清洗 CSV 可直接使用"
    )
with col_right:
    uploaded = st.file_uploader(
        "上传 CSV",
        type=["csv"],
        help="支持 UTF-8 / GBK / GB2312"
    )

if uploaded is not None:
    current_file_id = uploaded.file_id
    if st.session_state.get("last_file_id") != current_file_id:
        st.balloons()
        st.session_state.last_file_id = current_file_id

    # ─── 读取数据 ───────────────────────────────────────────────
    if mode == "原始 CSV（含 JSON 列）":
        with st.spinner("正在清洗数据..."):
            try:
                df = clean_raw_csv(uploaded)
            except ValueError as e:
                st.error(str(e))
                st.stop()
    else:
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
    df["订单GC转化率"] = (df["订单GC"] / df["点击人次"] * 100).round(2)
    df["订单GC转化率"] = df["订单GC转化率"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # ─── 幂次归一化（仅触达）────────────────────────────────
    df["触达_norm"] = ((df["触达成功"] / df["触达成功"].max()) ** 0.3) * 100

    # ─── 侧边筛选 ─────────────────────────────────────────────
    with st.sidebar:
        # 筛选条件区
        st.markdown('<div class="sidebar-section-title">筛选条件</div>', unsafe_allow_html=True)

        if date_col in df.columns and df[date_col].notna().any():
            min_dt = df[date_col].min().date()
            max_dt = df[date_col].max().date()
            default_start = max(min_dt, max_dt - timedelta(days=6))
            date_range = st.date_input(
                "日期范围",
                value=(default_start, max_dt),
                min_value=min_dt,
                max_value=max_dt
            )
        else:
            date_range = None

        plan_types = ["全部"] + df["计划类型"].dropna().unique().tolist()
        selected_plan = st.selectbox("计划类型", plan_types)

        channels = ["全部"] + df["渠道"].dropna().unique().tolist()
        selected_channel = st.selectbox("渠道", channels)

        owner_col = OWNER_COL
        if owner_col in df.columns:
            owners = ["全部"] + df[owner_col].dropna().unique().tolist()
        else:
            owners = ["全部"]
        selected_owner = st.selectbox("预算 Owner", owners)

        keyword = st.text_input("搜索关键词", "")

        # 排序区
        st.markdown('<div class="sidebar-section-title">排序方式</div>', unsafe_allow_html=True)
        sort_order = st.radio("综合评分排序", ["降序", "升序"], index=0, horizontal=True, label_visibility="collapsed")

        # 权重配置
        with st.expander("权重配置", expanded=False):
            w_reach = st.slider("触达权重", 0.0, 1.0, 0.35, 0.05)
            w_ctr = st.slider("CTR权重", 0.0, 1.0, 0.35, 0.05)
            w_gc = st.slider("GC转化率权重", 0.0, 1.0, 0.30, 0.05)

        total_w = w_reach + w_ctr + w_gc
        if total_w == 0:
            st.warning("权重总和为 0，请调整权重")
            norm_reach, norm_ctr, norm_gc = 0, 0, 0
        else:
            norm_reach = w_reach / total_w
            norm_ctr = w_ctr / total_w
            norm_gc = w_gc / total_w

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

    # ─── 渠道分层归一化 ──────────────────────────────────────
    def strat_minmax(sub_df, col):
        mn, mx = sub_df[col].min(), sub_df[col].max()
        if mx == mn or mx == 0:
            return sub_df[col] * 0 + 50
        return (sub_df[col] - mn) / (mx - mn) * 100

    dff["CTR_norm"] = 50.0
    dff["订单GC转化率_norm"] = 50.0
    
    if "渠道" in dff.columns and len(dff) > 0:
        ctr_norm_col = dff["CTR_norm"].copy()
        gc_rate_col = dff["订单GC转化率_norm"].copy()
        for ch, grp in dff.groupby("渠道"):
            if len(grp) > 0:
                mask = dff["渠道"] == ch
                ctr_norm_col.loc[mask] = strat_minmax(grp, "CTR")
                gc_rate_col.loc[mask] = strat_minmax(grp, "订单GC转化率")
        dff["CTR_norm"] = ctr_norm_col.values
        dff["订单GC转化率_norm"] = gc_rate_col.values

    # ─── 综合评分 ─────────────────────────────────────────────
    dff["综合评分"] = (
        dff["触达_norm"] * norm_reach
        + dff["CTR_norm"] * norm_ctr
        + dff["订单GC转化率_norm"] * norm_gc
    ).round(2)

    # ─── 重排排名 ─────────────────────────────────────────────
    if len(dff) > 0:
        asc = (sort_order == "升序")
        dff = dff.sort_values("综合评分", ascending=asc).reset_index(drop=True)
    dff["排名"] = dff.index + 1

    # ─── 顶部指标卡 ───────────────────────────────────────────
    total_rows = len(dff)
    total_score = dff["综合评分"].mean() if total_rows > 0 else 0
    top1_score = dff["综合评分"].max() if total_rows > 0 else 0
    avg_ctr = (dff["点击人次"].sum() / dff["触达成功"].sum() * 100) if dff["触达成功"].sum() > 0 else 0 if total_rows > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("上榜内容", f"{total_rows}")
    col2.metric("平均评分", f"{total_score:.1f}")
    col3.metric("最高评分", f"{top1_score:.1f}")
    col4.metric("平均 CTR", f"{avg_ctr:.2f}%")

    # ─── Tab 切换 ─────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["卡片排行榜", "数据表格", "可视化图表"])

    with tab1:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据，请调整筛选条件")
        else:
            cards = list(dff.itertuples())

            all_scores = [c.综合评分 for c in cards]
            if len(set(all_scores)) > 2:
                p33 = float(np.percentile(all_scores, 33))
                p67 = float(np.percentile(all_scores, 67))
            else:
                p33 = p67 = all_scores[0] if all_scores else 0

            for i in range(0, len(cards), 2):
                cols = st.columns([1, 1], gap="medium")
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(cards):
                        break
                    row = cards[idx]
                    rank = row.排名
                    badge_class = ("rank-1" if rank == 1 else
                                   "rank-2" if rank == 2 else
                                   "rank-3" if rank == 3 else
                                   "rank-other")

                    score = row.综合评分
                    score_color = MCD_GREEN if score >= p67 else (
                        "#888888" if score >= p33 else MCD_RED)

                    reach_norm = getattr(row, '触达_norm', 0)
                    ctr_norm   = getattr(row, 'CTR_norm', 0)
                    gc_norm = getattr(row, '订单GC转化率_norm', 0)

                    impact_parts = []
                    if reach_norm < 33:
                        impact_parts.append(f"触达偏低({reach_norm:.1f})")
                    elif reach_norm > 67:
                        impact_parts.append(f"触达偏高({reach_norm:.1f})")
                    if ctr_norm < 33:
                        impact_parts.append(f"CTR偏低({ctr_norm:.1f})")
                    elif ctr_norm > 67:
                        impact_parts.append(f"CTR偏高({ctr_norm:.1f})")
                    if gc_norm < 33:
                        impact_parts.append(f"GC转化率偏低({gc_norm:.1f})")
                    elif gc_norm > 67:
                        impact_parts.append(f"GC转化率偏高({gc_norm:.1f})")
                    impact = " / ".join(impact_parts) if impact_parts else "正常"
                    formula = (
                        f"{reach_norm:.1f}×{norm_reach:.2f} + "
                        f"{ctr_norm:.1f}×{norm_ctr:.2f} + "
                        f"{gc_norm:.1f}×{norm_gc:.2f} = {score:.2f}"
                    )
                    tooltip_text = f"{impact}\n{formula}"

                    with col:
                        date_val = getattr(row, '发送日期', None)
                        date_str = str(date_val)[:10] if date_val is not None and pd.notna(date_val) else ""
                        channel_val = getattr(row, '渠道', None)
                        channel_short = str(channel_val) if channel_val is not None and pd.notna(channel_val) else ""
                        owner_short = str(getattr(row, '预算owner', '')) if hasattr(row, '预算owner') else ''
                        plan_type_val = getattr(row, '计划类型', None)
                        plan_type_short = str(plan_type_val) if plan_type_val is not None and pd.notna(plan_type_val) else ""
                        title = str(getattr(row, '标题', '')) if getattr(row, '标题', '') else ''
                        content = str(getattr(row, '内容', '')) if getattr(row, '内容', '') else ''
                        if not title:
                            title = str(getattr(row, '消息标题', '')) if getattr(row, '消息标题', '') else ''

                        try: reach = int(getattr(row, '触达成功', 0))
                        except (ValueError, TypeError): reach = 0
                        try: clicks_val = int(getattr(row, '点击人次', 0))
                        except (ValueError, TypeError): clicks_val = 0
                        try: ctr_val = float(getattr(row, 'CTR', 0))
                        except (ValueError, TypeError): ctr_val = 0.0
                        try: gc_val = int(getattr(row, '订单GC', 0))
                        except (ValueError, TypeError): gc_val = 0
                        try: sales_val = float(getattr(row, '订单Sales', 0))
                        except (ValueError, TypeError): sales_val = 0.0
                        try: gc_rate_val = float(getattr(row, '订单GC转化率', 0))
                        except (ValueError, TypeError): gc_rate_val = 0.0

                        st.markdown(f"""
                        <div class="content-card">
                          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div style="flex:1; min-width:0;">
                              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                                <span class="rank-badge {badge_class}">{rank}</span>
                                <span style="font-size:11px;font-weight:500;color:#999;background:#F5F5F5;padding:2px 10px;border-radius:12px;">{channel_short}</span>
                                <span style="font-size:11px;color:#AAA;">{owner_short}</span>
                                <span style="font-size:11px;color:#BBB;">{plan_type_short} · {date_str}</span>
                              </div>
                              <div class="card-title">{title[:80]}{'...' if len(title) > 80 else ''}</div>
                              <div class="card-content">{content[:200]}{'...' if len(content) > 200 else ''}</div>
                              <div class="card-meta">
                                <span>触达 {reach:,}</span>
                                <span>点击 {clicks_val:,}</span>
                                <span>CTR {ctr_val:.2f}%</span>
                                <span>GC {gc_val:,}</span>
                                <span>Sales {int(sales_val):,}</span>
                                <span>GC转化 {gc_rate_val:.2f}%</span>
                              </div>
                            </div>
                            <div style="flex-shrink:0;padding-left:20px;text-align:right;">
                              <div style="display:flex;align-items:center;justify-content:flex-end;gap:4px;">
                                <div class="card-score" style="color:{score_color};">{score:.1f}</div>
                                <div class="score-info-wrap">
                                  <span class="info-icon">i</span>
                                  <div class="score-tooltip">{tooltip_text}</div>
                                </div>
                              </div>
                              <div class="card-score-label">综合评分</div>
                            </div>
                          </div>
                        </div>
                        """, unsafe_allow_html=True)

    # ─── Tab 2: 数据表格 ──────────────────────────────────────
    with tab2:
        title_col = "标题" if "标题" in dff.columns else "消息标题"
        owner_c = owner_col if owner_col in dff.columns else None
        display_cols = ["排名", title_col, "内容", "计划类型", "渠道",
                         date_col, owner_c,
                         "触达成功", "点击人次", "CTR", "订单GC", "订单Sales", "订单GC转化率", "综合评分"]
        display_cols = [c for c in display_cols if c is not None]
        available = [c for c in display_cols if c in dff.columns]
        disp_df = dff[available].copy()
        if 'CTR' in disp_df.columns:
            disp_df['CTR'] = disp_df['CTR'].apply(lambda x: f"{x:.2f}%")
        if '订单Sales' in disp_df.columns:
            disp_df['订单Sales'] = disp_df['订单Sales'].apply(lambda x: int(x) if pd.notna(x) else '')
        st.dataframe(disp_df, use_container_width=True, hide_index=True, height=600)
        csv_out = disp_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下载排行榜 CSV", csv_out, "麦当劳内容排行榜.csv", "text/csv", use_container_width=True)

    # ─── Tab 3: 可视化图表 ───────────────────────────────────
    with tab3:
        def _fmt_num(x):
            if abs(x) >= 1_000_000:
                return f"{x/1_000_000:.1f}M"
            elif abs(x) >= 1000:
                return f"{x/1000:.1f}k"
            else:
                return f"{x:.2f}"

        def _bar_line_chart(df_grp, dim_name, dim_label):
            agg = df_grp.groupby(dim_name).agg(
                触达量=("触达成功", "sum"),
                点击人次=("点击人次", "sum")
            ).reset_index()
            agg["日均触达量"] = (agg["触达量"] / num_days).round(2)
            agg["CTR"] = (agg["点击人次"] / agg["触达量"] * 100).round(2)
            agg["CTR"] = agg["CTR"].fillna(0).replace([float("inf"), -float("inf")], 0)
            agg = agg.sort_values("触达量", ascending=False)
            from plotly.subplots import make_subplots
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(
                x=agg[dim_name], y=agg["日均触达量"],
                name="日均触达量", marker_color=MCD_RED, opacity=0.85,
                text=agg["日均触达量"].apply(_fmt_num), textposition="outside"
            ), secondary_y=False)
            fig.add_trace(go.Scatter(
                x=agg[dim_name], y=agg["CTR"],
                name="CTR (%)", mode="lines+markers+text",
                line=dict(color=MCD_GOLD, width=3),
                marker=dict(size=10, color=MCD_GOLD),
                text=agg["CTR"].apply(lambda x: f"{x:.2f}%"),
                textposition="top center",
                textfont=dict(color="#B88600", size=12, family="PingFang SC, Microsoft YaHei, sans-serif")
            ), secondary_y=True)
            ctr_max = agg["CTR"].max() * 1.5
            fig.update_layout(
                template="plotly_white", height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=20),
                xaxis_title=""
            )
            fig.update_yaxes(title_text="日均触达量", secondary_y=False, showgrid=False)
            fig.update_yaxes(title_text="CTR (%)", secondary_y=True, range=[0, max(ctr_max, 1)], showgrid=False)
            fig.update_xaxes(showgrid=False)
            fig.update_xaxes(title_text=dim_label, tickangle=-20)
            return fig

        if total_rows == 0:
            st.warning("当前筛选条件下无数据")
        else:
            if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                start_dt, end_dt = date_range
                num_days = max((end_dt - start_dt).days, 1)
            else:
                num_days = 1

            if "渠道" in dff.columns and dff["渠道"].notna().sum() > 0:
                st.plotly_chart(_bar_line_chart(dff, "渠道", ""), use_container_width=True)
            else:
                st.info("当前数据无渠道维度")

            if owner_col in dff.columns and dff[owner_col].notna().sum() > 0:
                st.plotly_chart(_bar_line_chart(dff, owner_col, ""), use_container_width=True)
            else:
                st.info("当前数据无预算Owner维度")

            if "触达成功" in dff.columns and "订单Sales" in dff.columns and "CTR" in dff.columns:
                title_col = "标题" if "标题" in dff.columns else "消息标题"

                dff_h = dff.copy()
                dff_h["_触达_h"] = dff_h["触达成功"].apply(lambda v: f"{v/1000:.1f}k" if abs(v) >= 1000 else f"{v:.1f}")
                dff_h["_Sales_h"] = dff_h["订单Sales"].apply(lambda v: f"{v/1000:.1f}k" if abs(v) >= 1000 else f"{v:.1f}")
                dff_h["_CTR_h"] = dff_h["CTR"].apply(lambda v: f"{v:.2f}%")

                cd = ["_触达_h", "_Sales_h", "_CTR_h"]
                h_parts = [
                    "<b>%{hovertext}</b>",
                    "%{customdata[0]} 触达",
                    "%{customdata[1]} 订单",
                    "%{customdata[2]} CTR"
                ]
                if owner_col and owner_col in dff_h.columns:
                    dff_h["_BU_h"] = dff_h[owner_col].fillna("").astype(str)
                    cd.append("_BU_h")
                    h_parts.append("%{customdata[3]}")

                h_template = "<br>".join(h_parts) + "<extra></extra>"

                fig_scatter = px.scatter(
                    dff_h,
                    x="触达成功", y="订单Sales",
                    custom_data=cd,
                    hover_name=title_col,
                    hover_data={
                        "触达成功": False,
                        "订单Sales": False,
                        "CTR": False,
                        "_触达_h": False,
                        "_Sales_h": False,
                        "_CTR_h": False,
                        "_BU_h": False,
                    }
                )
                fig_scatter.update_traces(
                    hovertemplate=h_template,
                    marker=dict(size=14, color=MCD_RED, opacity=0.75, line=dict(width=0))
                )
                fig_scatter.update_layout(
                    template="plotly_white",
                    height=450,
                    showlegend=False,
                    xaxis_title="",
                    yaxis_title=""
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
