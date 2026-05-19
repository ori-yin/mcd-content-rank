"""
app.py - 麦当劳内容排行榜
"""
import html as _html
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import re
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import streamlit_mermaid as stmd

st.set_page_config(
    page_title="麦当劳内容排行榜",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════
# Section 0: CTR/GC 分段函数阈值配置
#   - Q3 阈值 = 75th percentile，来自全量数据统计
#   - amp 校准：使 Q3 得分 = 100
#   - 公式: G < C → score = amp × 100 × (G/C)^EXP; G >= C → score = amp × 100 (EXP=1.5)
# ═══════════════════════════════════════════════════════════════

# CTR 阈值配置 (单位: 百分比%，如 0.31 = 0.31% CTR)
CTR_THRESHOLDS = {
    "APP Push": 0.31,
    "企微1v1": 2.62,
    "微信小程序订阅消息": 4.01,
    "短信": 0.53,
}
# GC 阈值配置 (单位: 百分比，如 69.5 = 69.5%)
GC_THRESHOLDS = {
    "APP Push": 69.5,
    "企微1v1": 18.5,
    "微信小程序订阅消息": 41.0,
    "短信": 26.7,
}
# 未知渠道 fallback Q3 (来自全量 CTR/GC 统计)
CTR_UNKNOWN_THRESHOLD = 2.85   # 2.85%
GC_UNKNOWN_THRESHOLD = 34.8  # 34.8%

EXP = 1.5  # 幂次：E越大区分度越大（G/threshold^EXP，若 G/threshold=0.5→得分=100×0.5^1.5≈35）



def piecewise_score(G, threshold):
    if G < threshold:
        return 100.0 * ((G / threshold) ** EXP)
    return 100.0

def piecewise_score_vec(G_col, threshold_col):
    """向量化版本：整列一次计算，比 apply 快 100 倍"""
    ratio = G_col / threshold_col
    return np.where(ratio >= 1, 100.0, 100.0 * ratio ** EXP)

# ─── 品牌色 ─────────────────────────────────────────────────────
MCD_RED = "#DA291C"  # 麦当劳品牌红
MCD_GOLD = "#FFC000"
MCD_GREEN = "#00A04A"
MCD_BG = "#FAFAFA"

# ─── 列名常量 ──────────────────────────────────────────────────
OWNER_COL = "预算owner"   

# ─── 样式 ─────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* ─── 全局字体 ─── */
    html, body, .stApp {{
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif !important;
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

  }}

  /* ─── 文件上传区：统一左右两侧边框 ─── */
  [data-testid="stSidebar"] [data-testid="stRadio"] > div {{
    border: 1px solid rgba(0,0,0,0.15) !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
    background: rgba(255,255,255,0.6) !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploader"] > div > div {{
    border: 1px solid rgba(0,0,0,0.15) !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
    background: rgba(255,255,255,0.6) !important;
  }}

  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p {{
    color: #000000 !important;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
  }}

  /* ─── 侧边栏：弱化数据类型和上传文件标签 ─── */
  [data-testid="stSidebar"] [data-testid="stRadio"] label,
  [data-testid="stSidebar"] [data-testid="stFileUploader"] label {{
    color: #999 !important;
    font-weight: 300 !important;
    font-size: 10px !important;
    letter-spacing: 0.02em;
  }}

  /* ─── 侧边栏：其他标签保持正常 ─── */
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
    background: {MCD_RED} !important;
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

  /* ─── 顶部指标卡（弱化：小字+中灰）─── */
  div[data-testid="stMetricValue"] {{
    font-size: 14px !important;
    font-weight: 300 !important;
    color: #999 !important;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    letter-spacing: 0;
  }}
  div[data-testid="stMetricLabel"] {{
    font-size: 10px !important;
    color: #BBB !important;
    font-weight: 300;
    letter-spacing: 0.04em;
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
    background: {MCD_RED};
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
    background: #FFC000;
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
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
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
    font-size: 12px;
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
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
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
  .stCaption {{
    font-size: 12px !important;
    color: #AAA !important;
  }}

  /* ─── 数字高亮 ─── */
  .stAlert {{
    border-radius: 10px;
  }}

  /* ─── 综合评分 Info Tooltip ─── */
  .score-info-wrap {{
    display: inline-block;
    position: relative;
    vertical-align: middle;
    margin-left: 5px;
    cursor: help;
    line-height: 1;
  }}
  .score-info-wrap .info-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #E0E0E0;
    color: #999;
    font-size: 9px;
    font-weight: 900;
    font-style: normal;
    line-height: 1;
    user-select: none;
    transition: background 0.15s, color 0.15s;
  }}
  .score-info-wrap:hover .info-icon {{
    background: {MCD_RED};
    color: #FFF;
  }}
  .score-tooltip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: calc(100% + 8px);
    right: calc(100% + 10px);
    background: rgba(30, 30, 30, 0.95);
    color: #FFFFFF;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12px;
    white-space: pre-line;
    line-height: 1.6;
    min-width: 220px;
    max-width: 300px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    z-index: 9999;
    pointer-events: none;
    transition: opacity 0.15s ease;
  }}
  .score-tooltip::after {{
    content: '';
    position: absolute;
    top: 100%;
    right: auto;
    left: 100%;
    border: 5px solid transparent;
    border-left-color: rgba(30, 30, 30, 0.95);
  }}
  .score-info-wrap:hover .score-tooltip {{
    visibility: visible;
    opacity: 1;
  }}

</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# Section 1: 全局配置与样式
# ═══════════════════════════════════════════════════════════════

# ─── Header ───────────────────────────────────────────────────
st.markdown(f"""
<div class="mcd-header">
  <h1>麦当劳内容排行榜</h1>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# Section 2: 数据清洗函数
# ═══════════════════════════════════════════════════════════════

# Ori 的数据清洗脚本
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
# Section 3: App 主逻辑
# ═══════════════════════════════════════════════════════════════

# App 主逻辑
# ═══════════════════════════════════════════════════════════════

# ─── 文件上传 + 清洗模式选择 ────────────────────────────────────
with st.expander("数据源", expanded=False):
    col_left, col_right = st.columns([1, 1])
    with col_left:
        mode = st.radio(
            "数据类型",
            ["原始 CSV（含 JSON 列，需清洗）", "已清洗 CSV（直接使用）"],
            horizontal=True,
            help="原始 CSV：上传运行清洗脚本之前的文件；已清洗 CSV：运行完脚本后的文件"
        )
    with col_right:
        uploaded = st.file_uploader(
            "上传 CSV 文件",
            type=["csv"],
            help="支持 UTF-8、GBK、GB2312、Latin1 编码"
        )

# 只在首次上传或文件变化时触发气球
if uploaded is not None:
    current_file_id = uploaded.file_id
    if st.session_state.get("last_file_id") != current_file_id:
        st.balloons()
        st.session_state.last_file_id = current_file_id

    # ─── 读取数据 ───────────────────────────────────────────────
    if mode == "原始 CSV（含 JSON 列，需清洗）":
        with st.spinner("正在运行数据清洗脚本..."):
            try:
                df = clean_raw_csv(uploaded)
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
    df["订单GC转化率"] = (df["订单GC"] / df["点击人次"] * 100).round(2)
    df["订单GC转化率"] = df["订单GC转化率"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # ─── 幂次归一化（仅触达）────────────────────────────────
    df["触达_norm"] = ((df["触达成功"] / df["触达成功"].max()) ** 0.3) * 100

    # --- 计算全量数据的综合评分（用于渠道均值，不受筛选影响）----------------------

    # 触达分段惩戒系数（触达量越小折扣越大，归一化后应用）
    def penalty_coef_from_reach(reach_raw):
        """触达量不足的降权：触达量越小折扣越大（归一化后应用）"""
        if reach_raw < 100:
            return 0.1
        elif reach_raw < 500:
            return 0.3
        elif reach_raw < 1000:
            return 0.5
        elif reach_raw < 5000:
            return 0.8
        else:
            return 1.0

    _ctr_thresh = df["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    df["CTR_score_full"] = piecewise_score_vec(df["CTR"], _ctr_thresh)
    _gc_thresh = df["渠道"].astype(str).map(GC_THRESHOLDS).fillna(GC_UNKNOWN_THRESHOLD)
    df["GC_score_full"] = piecewise_score_vec(df["订单GC转化率"], _gc_thresh)
    df["综合评分_full"] = (
        df["触达_norm"] * 0.2 + df["CTR_score_full"] * 0.50 + df["GC_score_full"] * 0.30
    ) * pd.cut(
        df["触达成功"].fillna(0),
        bins=[-1, 99, 499, 999, 4999, float("inf")],
        labels=[0.1, 0.3, 0.5, 0.8, 1.0]
    ).astype(float)

    # --- 计算分渠道平均综合评分（基于全量数据，不受筛选影响）----------------------
    channel_avg_score = {}
    if "渠道" in df.columns:
        for ch in df["渠道"].dropna().unique():
            ch_df = df[df["渠道"] == ch]
            if len(ch_df) > 0:
                channel_avg_score[ch] = ch_df["综合评分_full"].mean()
            else:
                channel_avg_score[ch] = 0.0
    # 注：CTR_norm 和 订单GC转化率_norm 在筛选后按渠道分层计算，此处不预先计算

    # ─── 侧边筛选 ─────────────────────────────────────────────
    with st.sidebar:
        # ─── 筛选条件 ───────────────────────────────────────────
        st.markdown("**筛选条件**")

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

                # ─── 权重配置（折叠）─────────────────────────────────────
        st.markdown("**权重**")
        with st.expander("权重配置", expanded=False):
            w_reach = st.slider("触达权重", 0.0, 1.0, 0.20, 0.05)
            w_ctr = st.slider("CTR权重", 0.0, 1.0, 0.50, 0.05)
            w_gc = st.slider("GC转化率权重", 0.0, 1.0, 0.30, 0.05)
        # ─── 排序 ────────────────────────────────────────────────
        st.markdown("**排序**")
        sort_order = st.radio("综合评分排序", ["降序", "升序"], index=0, horizontal=True, label_visibility="collapsed")

        total_w = w_reach + w_ctr + w_gc
        if total_w == 0:
            st.warning("权重总和为 0，请调整权重")
            norm_reach, norm_ctr, norm_gc = 0, 0, 0
        else:
            norm_reach = w_reach / total_w
            norm_ctr = w_ctr / total_w
            norm_gc = w_gc / total_w

    # ─── 计算综合评分（筛选后在渠道分层归一化之后计算）──────────────────
    # 注：触达_norm 已在全局计算，CTR_norm 和 订单GC转化率_norm 需在筛选后按渠道分层计算

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
        mask = pd.Series(False, index=dff.index)
        # 搜索标题列
        title_candidates = [c for c in ["标题", "消息标题"] if c in dff.columns]
        if title_candidates:
            mask |= dff[title_candidates[0]].astype(str).str.lower().str.contains(kw, na=False)
        # 搜索内容列
        if "内容" in dff.columns:
            mask |= dff["内容"].astype(str).str.lower().str.contains(kw, na=False)
        dff = dff[mask]

    # ─── 分段评分（CTR/GC 按渠道 Q3 阈值 + amp 校准）───────────────────
    # CTR_score 和 GC_score 范围: 0 ~ 100+，饱和在 amp×100（各渠道 Q3 = 100）
    def get_channel_score(G_raw, channel, threshold_map, threshold_unknown):
        ch = str(channel) if channel is not None else "未知渠道"
        threshold = threshold_map.get(ch, threshold_unknown)
        return piecewise_score(G_raw, threshold)

    _dff_ctr_thresh = dff["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    dff["CTR_score"] = piecewise_score_vec(dff["CTR"], _dff_ctr_thresh)
    _dff_gc_thresh = dff["渠道"].astype(str).map(GC_THRESHOLDS).fillna(GC_UNKNOWN_THRESHOLD)
    dff["GC_score"] = piecewise_score_vec(dff["订单GC转化率"], _dff_gc_thresh)
    # ─── 计算综合评分（CTR_score/GC_score 替代原 CTR_norm/GC转化率_norm）───
    base_score = (
        dff["触达_norm"] * norm_reach
        + dff["CTR_score"] * norm_ctr
        + dff["GC_score"] * norm_gc
    ).round(2)
    reach_raw_for_penalty = dff["触达成功"].fillna(0)
    penalty_vec = pd.cut(
        reach_raw_for_penalty,
        bins=[-1, 99, 499, 999, 4999, float("inf")],
        labels=[0.1, 0.3, 0.5, 0.8, 1.0]
    ).astype(float)
    dff["综合评分"] = base_score * penalty_vec

    # ─── 筛选后重排排名 ────────────────────────────────────────
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
    col1.metric("上榜内容", f"{total_rows} 条")
    col2.metric("平均综合评分", f"{total_score:.2f}")
    col3.metric("最高综合评分", f"{top1_score:.2f}")
    col4.metric("平均 CTR", f"{avg_ctr:.2f}%")

    # ─── Tab 切换 ─────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["卡片排行榜", "算法说明", "数据表格", "可视化图表"])

    with tab1:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据，请调整筛选条件")
        else:
            
            cards = list(dff.itertuples())

            # ─── 分页 ─────────────────────────────────────────────
            PAGE_SIZE = 50
            total_pages = max(1, (len(cards) + PAGE_SIZE - 1) // PAGE_SIZE)
            if "card_page" not in st.session_state:
                st.session_state.card_page = 1
            page = st.session_state.card_page
            page_cards = cards[(page-1)*PAGE_SIZE : page*PAGE_SIZE]

            # ─── 合并渲染：拼成一个 HTML 字符串 ──────────────────────
            html_parts = []
            for row in page_cards:
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
                if score >= 75:
                    score_color = "#00A04A"
                elif score >= 40:
                    score_color = "#FFC000"
                else:
                    score_color = "#DA291C"

                # tooltip
                reach_raw_t = int(getattr(row, '触达成功', 0) or 0)
                if reach_raw_t < 100:
                    penalty_coef_t, penalty_label = 0.1, "置信度低(x0.1)"
                elif reach_raw_t < 500:
                    penalty_coef_t, penalty_label = 0.3, "置信度低(x0.3)"
                elif reach_raw_t < 1000:
                    penalty_coef_t, penalty_label = 0.5, "置信度中(x0.5)"
                elif reach_raw_t < 5000:
                    penalty_coef_t, penalty_label = 0.8, "置信度较高(x0.8)"
                else:
                    penalty_coef_t, penalty_label = 1.0, "置信度高(x1.0)"

                reach_norm = getattr(row, '触达_norm', 0)
                ctr_score_t = getattr(row, 'CTR_score', 0)
                gc_score_t = getattr(row, 'GC_score', 0)
                base_score_t = reach_norm * w_reach + ctr_score_t * w_ctr + gc_score_t * w_gc
                tooltip_text = _html.escape(
                    "({:.1f}x{:.2f} + {:.1f}x{:.2f} + {:.1f}x{:.2f}) x {:.1f} = {:.2f}  [{}]".format(
                        reach_norm, w_reach, ctr_score_t, w_ctr, gc_score_t, w_gc,
                        penalty_coef_t, score, penalty_label
                    )
                )

                date_val = getattr(row, '发送日期', None)
                date_str = str(date_val)[:10] if date_val is not None and not (isinstance(date_val, float) and date_val != date_val) else ""
                channel_short = str(getattr(row, '渠道', '') or '')
                owner_short = str(getattr(row, '预算owner', '') or '') if hasattr(row, '预算owner') else ''
                plan_type_short = str(getattr(row, '计划类型', '') or '')
                title = str(getattr(row, '标题', '') or '')
                if not title:
                    title = str(getattr(row, '消息标题', '') or '')
                content = str(getattr(row, '内容', '') or '')

                try: reach = int(getattr(row, '触达成功', 0))
                except: reach = 0
                try: clicks_val = int(getattr(row, '点击人次', 0))
                except: clicks_val = 0
                try: ctr_val = float(getattr(row, 'CTR', 0))
                except: ctr_val = 0.0
                try: gc_val = int(getattr(row, '订单GC', 0))
                except: gc_val = 0
                try: sales_val = float(getattr(row, '订单Sales', 0))
                except: sales_val = 0.0
                try: gc_rate_val = float(getattr(row, '订单GC转化率', 0))
                except: gc_rate_val = 0.0

                channel_avg = channel_avg_score.get(channel_short, 0)

                html_parts.append(f"""
                <div class="content-card">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div style="flex:1;">
                      <span class="rank-badge {badge_class}">{rank}</span>
                      <span style="font-size:12px; color:#888; background:#F5F5F5; padding:2px 8px; border-radius:12px;">{channel_short}</span>
                      <span style="font-size:12px; color:#AAA;"> · {owner_short} · {plan_type_short} · {date_str}</span>
                    </div>
                    <div>
                      <div style="display:flex;align-items:flex-start;justify-content:flex-end;gap:0;">
                        <div class="card-score" style="color:{score_color};">{score:.2f}</div>
                        <div class="score-info-wrap">
                          <span class="info-icon">i</span>
                          <div class="score-tooltip">{tooltip_text}</div>
                        </div>
                      </div>
                      <div class="card-score-label">均值 {channel_avg:.2f}</div>
                    </div>
                  </div>
                  <div class="card-title">{title[:80]}{'...' if len(title) > 80 else ''}</div>
                  <div class="card-content">{content[:200]}{'...' if len(content) > 200 else ''}</div>
                  <div class="card-meta">
                    <span>触达 {reach:,}</span>
                    <span>点击 {clicks_val:,}</span>
                    <span>CTR {ctr_val:.2f}%</span>
                    <span>GC {gc_val:,}</span>
                    <span>Sales {int(sales_val):,}</span>
                    <span>GC转化率 {gc_rate_val:.2f}%</span>
                  </div>
                </div>
                """)

            grid_html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">' + "".join(html_parts) + '</div>'
            st.html(grid_html)
            # ─── 底部翻页 ─────────────────────────────────────────
            pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
            with pcol1:
                if st.button("⬅ 上一页", disabled=(page <= 1)):
                    st.session_state.card_page = page - 1
                    st.rerun()
            with pcol2:
                st.markdown(f"<div style='text-align:center; color:#888; font-size:13px; padding-top:8px;'>第 {page}/{total_pages} 页，共 {len(cards)} 条</div>", unsafe_allow_html=True)
            with pcol3:
                if st.button("下一页 ➡", disabled=(page >= total_pages)):
                    st.session_state.card_page = page + 1
                    st.rerun()

    with tab2:
        st.markdown('<div class="section-title">综合评分算法说明</div>', unsafe_allow_html=True)
        st.components.v1.html("""
<!DOCTYPE html>
<html>
<head>

<style>
  body { margin: 0; background: #FAFAFA; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }
  #wrap {
    position: relative;
    background: #fff;
    border: 1px solid #EFEFEF;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  }
  #wrap:fullscreen, #wrap:-webkit-full-screen {
    background: #fff;
    border-radius: 0;
    padding: 40px;
    overflow: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
  }
  #wrap:fullscreen #diagram, #wrap:-webkit-full-screen #diagram {
    width: 100%;
    max-width: 1200px;
  }
  #btn-fs {
    position: absolute;
    top: 12px;
    right: 12px;
    background: #DA291C;
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    z-index: 10;
    letter-spacing: 0.03em;
    transition: background 0.15s;
  }
  #btn-fs:hover { background: #b5200f; }
  #diagram svg { width: 100% !important; height: auto !important; }
</style>
</head>
<body>
<div id="wrap">
  <button id="btn-fs" onclick="toggleFS()">⛶ 全屏</button>
  <div id="diagram" class="mermaid">
flowchart TD
    A[原始数据] --> B[计算衍生指标]
    B --> C[CTR = 点击人次除以触达成功]
    B --> D[GC转化率 = 订单GC除以点击人次]
    C --> E[CTR分]
    D --> F[GC分]
    A --> G[触达分 = 幂次归一化]
    E --> E1{CTR低于渠道Q3阈值}
    E1 --> |是| E2[100乘以CTR/Q3的1.5次方]
    E1 --> |否| E3[100分 饱和]
    F --> F1{GC率低于渠道Q3阈值}
    F1 --> |是| F2[100乘以GC率/Q3的1.5次方]
    F1 --> |否| F3[100分 饱和]
    G --> H[加权求和]
    E2 --> H
    E3 --> H
    F2 --> H
    F3 --> H
    H --> I[base = 触达0.2 + CTR0.5 + GC0.3]
    I --> J[置信度惩戒]
    J --> J1{触达量}
    J1 --> |触达小于100| J2[系数0.1]
    J1 --> |100到499| J3[系数0.3]
    J1 --> |500到999| J4[系数0.5]
    J1 --> |1000到4999| J5[系数0.8]
    J1 --> |5000以上| J6[系数1.0]
    J2 --> K[综合评分]
    J3 --> K
    J4 --> K
    J5 --> K
    J6 --> K
    style K fill:#DA291C,color:#fff,font-weight:bold
    style I fill:#FFC000,color:#000
    style H fill:#FFC000,color:#000
  </div>
</div>
<script>
  function renderMermaid() {
    if (typeof mermaid !== 'undefined') {
      mermaid.initialize({ startOnLoad: false, theme: 'default', flowchart: { useMaxWidth: true } });
      mermaid.run({ nodes: document.querySelectorAll('.mermaid') });
    } else {
      setTimeout(renderMermaid, 100);
    }
  }
  var _s = document.createElement('script');
  _s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
  _s.onload = renderMermaid;
  _s.onerror = function() { setTimeout(renderMermaid, 300); };
  document.head.appendChild(_s);

  function toggleFS() {
    var wrap = document.getElementById('wrap');
    var btn = document.getElementById('btn-fs');
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      var req = wrap.requestFullscreen || wrap.webkitRequestFullscreen;
      if (req) req.call(wrap);
    } else {
      var ex = document.exitFullscreen || document.webkitExitFullscreen;
      if (ex) ex.call(document);
    }
  }

  document.addEventListener('fullscreenchange', updateBtn);
  document.addEventListener('webkitfullscreenchange', updateBtn);
  function updateBtn() {
    var btn = document.getElementById('btn-fs');
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      btn.textContent = '✕ 退出全屏';
    } else {
      btn.textContent = '⛶ 全屏';
    }
  }
</script>
</body>
</html>
""", height=1200, scrolling=False)

        with st.expander("阈值与惩戒系数参考", expanded=False):
            st.markdown("""
<div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:8px;">
  <div style="flex:1; min-width:180px; background:#fff; border:1px solid #EFEFEF; border-radius:12px; padding:16px 20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
    <div style="font-size:12px; font-weight:700; color:#DA291C; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:10px;">渠道 CTR Q3 阈值</div>
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">APP Push</td><td style="padding:6px 4px; text-align:right; font-weight:600;">0.31%</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">企微1v1</td><td style="padding:6px 4px; text-align:right; font-weight:600;">2.62%</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">小程序订阅消息</td><td style="padding:6px 4px; text-align:right; font-weight:600;">4.01%</td></tr>
      <tr><td style="padding:6px 4px; color:#888;">短信</td><td style="padding:6px 4px; text-align:right; font-weight:600;">0.53%</td></tr>
    </table>
  </div>
  <div style="flex:1; min-width:180px; background:#fff; border:1px solid #EFEFEF; border-radius:12px; padding:16px 20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
    <div style="font-size:12px; font-weight:700; color:#DA291C; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:10px;">渠道 GC转化率 Q3 阈值</div>
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">APP Push</td><td style="padding:6px 4px; text-align:right; font-weight:600;">69.5%</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">企微1v1</td><td style="padding:6px 4px; text-align:right; font-weight:600;">18.5%</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">小程序订阅消息</td><td style="padding:6px 4px; text-align:right; font-weight:600;">41.0%</td></tr>
      <tr><td style="padding:6px 4px; color:#888;">短信</td><td style="padding:6px 4px; text-align:right; font-weight:600;">26.7%</td></tr>
    </table>
  </div>
  <div style="flex:1; min-width:180px; background:#fff; border:1px solid #EFEFEF; border-radius:12px; padding:16px 20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
    <div style="font-size:12px; font-weight:700; color:#DA291C; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:10px;">置信度惩戒系数</div>
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">&lt; 100</td><td style="padding:6px 4px; text-align:right; font-weight:600; color:#DA291C;">× 0.1</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">100 ~ 499</td><td style="padding:6px 4px; text-align:right; font-weight:600; color:#DA291C;">× 0.3</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">500 ~ 999</td><td style="padding:6px 4px; text-align:right; font-weight:600; color:#FFC000;">× 0.5</td></tr>
      <tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">1000 ~ 4999</td><td style="padding:6px 4px; text-align:right; font-weight:600; color:#FFC000;">× 0.8</td></tr>
      <tr><td style="padding:6px 4px; color:#888;">≥ 5000</td><td style="padding:6px 4px; text-align:right; font-weight:600; color:#00A04A;">× 1.0</td></tr>
    </table>
  </div>
</div>
""", unsafe_allow_html=True)
    with tab3:
        title_col = "标题" if "标题" in dff.columns else "消息标题"
        owner_c = owner_col if owner_col in dff.columns else None
        display_cols = ["排名", title_col, "内容", "计划类型", "渠道",
                         date_col, owner_c,
                         "触达成功", "点击人次", "CTR", "订单GC", "订单Sales", "订单GC转化率", "综合评分"]
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

    # ─── Tab 3: 可视化图表 ───────────────────────────────────
    with tab4:
        # 图表辅助函数
        def _fmt_num(x):
            if abs(x) >= 1_000_000:
                return f"{x/1_000_000:.1f}M"
            elif abs(x) >= 1000:
                return f"{x/1000:.1f}k"
            else:
                return f"{x:.2f}"

        def _bar_line_chart(df_grp, dim_name, dim_label, num_days):
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
                line=dict(color="#FFC000", width=3),
                marker=dict(size=10, color="#FFC000"),
                text=agg["CTR"].apply(lambda x: f"{x:.2f}%"),
                textposition="top center",
                textfont=dict(color="#FFC000", size=12, family="PingFang SC, Microsoft YaHei, sans-serif")
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
                st.plotly_chart(_bar_line_chart(dff, "渠道", "", num_days), use_container_width=True)
            else:
                st.info("当前数据无渠道维度")

            if owner_col in dff.columns and dff[owner_col].notna().sum() > 0:
                st.plotly_chart(_bar_line_chart(dff, owner_col, "", num_days), use_container_width=True)
            else:
                st.info("当前数据无预算Owner维度")


