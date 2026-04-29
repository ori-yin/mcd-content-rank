# -*- coding: utf-8 -*-
"""
app_v2.py - 麦当劳内容排行榜 v4（极简深色风格 Apple/MiMo 感）
只改 UI，不改业务逻辑
配色：黑白灰体系 #0b0b0c / #141414 / #1a1a1a / #2a2a2a / #ffffff / #a1a1aa
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import re
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="内容排行榜", layout="wide")

# ═══════════════════════════════════════════════════════════════
# 设计规范
# 背景 #0b0b0c  卡片 #141414  边框 #2a2a2a  主文字 #ffffff  次文字 #a1a1aa
# 圆角 12px  大量留白  极轻阴影  无渐变  无高饱和色
# ═══════════════════════════════════════════════════════════════

BG = "#0b0b0c"
CARD = "#141414"
CARD2 = "#1a1a1a"
BORDER = "#2a2a2a"
TEXT = "#ffffff"
TEXT_SUB = "#a1a1aa"
TEXT_DIM = "#666666"
RADIUS = "12px"

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap');

  html, body, .stApp {{
    font-family: 'Inter', 'PingFang SC', sans-serif !important;
    background: {BG} !important;
    color: {TEXT} !important;
  }}

  .st-emotion-cache-1kyxreq {{
    background: transparent !important;
    border-bottom: 1px solid {BORDER} !important;
  }}

  [data-testid="stSidebar"] {{
    background: {CARD} !important;
    border-right: 1px solid {BORDER} !important;
    min-width: 260px !important;
    max-width: 260px !important;
  }}

  [data-testid="stSidebar"] * {{
    color: {TEXT_SUB} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
  }}

  .sidebar-section-title {{
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: {TEXT_DIM} !important;
    margin: 20px 0 10px 0 !important;
    padding-bottom: 6px !important;
    border-bottom: 1px solid {BORDER} !important;
  }}

  [data-testid="stSidebar"] .stSelectbox > div > div,
  [data-testid="stSidebar"] .stDateInput > div > div,
  [data-testid="stSidebar"] .stTextInput > div > div {{
    background: {CARD2} !important;
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important;
    color: {TEXT} !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="select"] span {{ color: {TEXT} !important; }}

  [data-testid="stSidebar"] .stRadio label {{
    color: {TEXT_SUB} !important;
    font-size: 12px !important;
  }}

  .block-container {{
    padding-top: 2rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    background: {BG} !important;
    max-width: 100% !important;
  }}

  .page-title {{
    font-size: 32px; font-weight: 900; color: {TEXT};
    margin: 0 0 4px 0; letter-spacing: -0.03em; line-height: 1.1;
  }}
  .page-subtitle {{
    font-size: 13px; color: {TEXT_SUB};
    margin: 0 0 28px 0; font-weight: 400;
  }}

  div[data-testid="stMetricValue"] {{
    font-size: 26px !important; font-weight: 700 !important;
    color: {TEXT} !important; font-family: 'Inter', sans-serif !important;
    letter-spacing: -0.03em;
  }}
  div[data-testid="stMetricLabel"] {{
    font-size: 11px !important; color: {TEXT_SUB} !important;
    font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase;
  }}
  div[data-testid="stMetricDelta"] {{ display: none; }}
  [data-testid="stHorizontalBlock"] > div {{
    background: {CARD}; border: 1px solid {BORDER};
    border-radius: {RADIUS}; padding: 18px 20px;
  }}

  .stTabs [data-baseweb="tab-list"] {{ gap: 0; border-bottom: 1px solid {BORDER}; }}
  .stTabs [data-baseweb="tab"] {{
    color: {TEXT_SUB} !important; font-weight: 600; font-size: 13px;
    padding: 10px 20px; border-bottom: 2px solid transparent; margin-bottom: -1px;
  }}
  .stTabs [data-baseweb="tab"]:hover {{ color: {TEXT} !important; }}
  .stTabs [aria-selected="true"] {{
    color: {TEXT} !important; border-bottom: 2px solid {TEXT} !important; font-weight: 700;
  }}

  .content-card {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS};
    padding: 20px 22px; margin-bottom: 12px;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  }}
  .content-card:hover {{
    transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.4); border-color: #3a3a3a;
  }}
  .content-card.top-1 {{ border-color: #3a3a3a; background: #181818; }}
  .content-card.top-2, .content-card.top-3 {{ border-color: #2f2f2f; }}

  .rank-badge {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; border-radius: 50%;
    font-weight: 700; font-size: 12px; margin-right: 12px; flex-shrink: 0;
  }}
  .rank-1 {{ background: #2a2a2a; color: {TEXT}; border: 1px solid #444; }}
  .rank-2 {{ background: #222; color: {TEXT_SUB}; border: 1px solid #333; }}
  .rank-3 {{ background: #1f1f1f; color: {TEXT_SUB}; border: 1px solid #2a2a2a; }}
  .rank-other {{ background: #1a1a1a; color: {TEXT_DIM}; border: 1px solid {BORDER}; }}

  .card-title {{
    font-size: 14px; font-weight: 600; color: {TEXT};
    margin: 0 0 8px 0; line-height: 1.5;
  }}
  .card-content {{
    font-size: 13px; color: {TEXT_SUB}; line-height: 1.65; margin-bottom: 14px;
  }}
  .card-meta {{ display: flex; gap: 8px; flex-wrap: wrap; font-size: 11px; color: {TEXT_DIM}; }}
  .card-meta span {{
    background: {CARD2}; padding: 4px 10px; border-radius: 20px;
    border: 1px solid {BORDER}; font-weight: 500; letter-spacing: 0.02em;
  }}
  .card-score {{
    font-size: 28px; font-weight: 900; color: {TEXT}; text-align: right;
    line-height: 1; font-family: 'Inter', sans-serif; letter-spacing: -0.04em;
  }}
  .card-score-label {{
    font-size: 10px; color: {TEXT_DIM}; text-align: right; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.08em; margin-top: 3px;
  }}

  .upload-section {{
    background: {CARD}; border: 1px dashed {BORDER}; border-radius: {RADIUS};
    padding: 40px 24px; text-align: center; margin-bottom: 28px;
    transition: border-color 0.2s ease, background 0.2s ease;
  }}
  .upload-section:hover {{ border-color: #444; background: {CARD2}; }}
  .upload-icon {{ font-size: 28px; margin-bottom: 12px; filter: grayscale(1) opacity(0.5); }}
  .upload-title {{ font-size: 14px; font-weight: 600; color: {TEXT}; margin-bottom: 4px; }}
  .upload-desc {{ font-size: 12px; color: {TEXT_SUB}; margin: 0; }}

  .stDataFrame thead th {{
    background: {CARD} !important; color: {TEXT_SUB} !important;
    font-size: 11px !important; font-weight: 700 !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important;
    border-bottom: 1px solid {BORDER} !important; border: none !important;
    padding: 10px 12px !important;
  }}
  .stDataFrame tbody tr {{ border-bottom: 1px solid {BORDER} !important; }}
  .stDataFrame tbody tr:hover {{ background: rgba(255,255,255,0.02) !important; }}
  .stDataFrame tbody td {{
    font-size: 13px !important; color: {TEXT_SUB} !important;
    padding: 10px 12px !important; border-bottom: 1px solid {BORDER} !important;
  }}
  .stDataFrame tbody td:first-child {{ color: {TEXT} !important; font-weight: 600; }}
  [data-testid="stDataFrame"] {{
    background: {CARD} !important; border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important;
  }}

  .stDownloadButton > button, .stButton > button {{
    background: {CARD2} !important; color: {TEXT} !important;
    border: 1px solid {BORDER} !important; border-radius: {RADIUS} !important;
    font-weight: 600 !important; font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.15s ease; padding: 6px 18px !important;
  }}
  .stDownloadButton > button:hover, .stButton > button:hover {{
    background: #222 !important; border-color: #444 !important;
  }}

  .stAlert {{
    background: {CARD} !important; border: 1px solid {BORDER} !important;
    border-radius: {RADIUS} !important; color: {TEXT_SUB} !important; font-size: 13px !important;
  }}

  hr {{ border-color: {BORDER} !important; margin: 16px 0 !important; }}
  .stCaption, p {{ font-size: 12px !important; color: {TEXT_DIM} !important; }}

  .section-label {{
    font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: {TEXT_DIM}; margin: 28px 0 12px 0;
  }}
</style>
""", unsafe_allow_html=True)

# ─── 页面标题 ─────────────────────────────────────────────────
st.markdown("""
<div class="page-title">内容排行榜</div>
<div class="page-subtitle">上传原始 CSV → 自动清洗 → 生成综合评分</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# Ori 的数据清洗逻辑（原封不动）
# ═══════════════════════════════════════════════════════════════

def extract_title_from_forms(forms):
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
        title = first_part if first_part else str(text)[:20]

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
        raise ValueError("无法读取 CSV 文件")
    if df.shape[1] < 15:
        raise ValueError(f"CSV 只有 {df.shape[1]} 列，第 15 列（O列）不存在")
    o_col = df.iloc[:, 14]
    parsed_df = o_col.apply(parse_message)
    df['标题'] = parsed_df['标题']
    df['内容'] = parsed_df['内容']
    df = df.drop(df.columns[14], axis=1)
    return df


# ═══════════════════════════════════════════════════════════════
# App 主逻辑
# ═══════════════════════════════════════════════════════════════

st.markdown("""
<div class="upload-section">
  <div class="upload-icon">↑</div>
  <div class="upload-title">拖拽或点击上传 CSV</div>
  <p class="upload-desc">支持 UTF-8 / GBK / GB2312 编码</p>
</div>
""", unsafe_allow_html=True)

mode = st.radio(
    "数据类型",
    ["原始 CSV（含 JSON 列，需清洗）", "已清洗 CSV（直接使用）"],
    horizontal=True,
    label_visibility="collapsed"
)

uploaded = st.file_uploader("上传 CSV 文件", type=["csv"], label_visibility="collapsed")

if uploaded:
    if mode == "原始 CSV（含 JSON 列，需清洗）":
        with st.spinner("数据清洗中..."):
            try:
                df = clean_raw_csv(uploaded)
                st.markdown(
                    f'<div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;'
                    f'padding:12px 16px;margin-bottom:20px;font-size:13px;color:#a1a1aa;">'
                    f'✓ 清洗完成 — 最终 {df.shape[1]} 列，{df.shape[0]} 行</div>',
                    unsafe_allow_html=True
                )
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

    date_col = "发送日期"
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    df["CTR"] = (df["点击人次"] / df["触达成功"] * 100).round(2)
    df["CTR"] = df["CTR"].replace([float("inf"), -float("inf")], 0).fillna(0)
    df["单均价"] = (df["订单Sales"] / df["订单GC"]).round(2)
    df["单均价"] = df["单均价"].replace([float("inf"), -float("inf")], 0).fillna(0)

    def minmax(series):
        mn, mx = series.min(), series.max()
        if mx == mn:
            return series * 0
        return (series - mn) / (mx - mn) * 100

    df["触达_norm"] = minmax(df["触达成功"])
    df["CTR_norm"] = minmax(df["CTR"])
    df["Sales_norm"] = minmax(df["订单Sales"])
    df["单均价_norm"] = minmax(df["单均价"])

    # ─── 侧边筛选面板 ─────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="sidebar-section-title">筛选条件</div>', unsafe_allow_html=True)

        if date_col in df.columns and df[date_col].notna().any():
            min_dt = df[date_col].min().date()
            max_dt = df[date_col].max().date()
            default_start = max(min_dt, max_dt - timedelta(days=6))
            date_range = st.date_input(
                "日期范围", value=(default_start, max_dt),
                min_value=min_dt, max_value=max_dt,
                label_visibility="visible"
            )
        else:
            date_range = None

        plan_types = ["全部"] + df["计划类型"].dropna().unique().tolist()
        selected_plan = st.selectbox("计划类型", plan_types)

        channels = ["全部"] + df["渠道"].dropna().unique().tolist()
        selected_channel = st.selectbox("渠道", channels)

        owner_col = "预算owner"
        if owner_col in df.columns:
            owners = ["全部"] + df[owner_col].dropna().unique().tolist()
        else:
            owners = ["全部"]
        selected_owner = st.selectbox("预算 Owner", owners)

        keyword = st.text_input("搜索关键词", "")

        st.markdown('<div class="sidebar-section-title">权重配置</div>', unsafe_allow_html=True)

        def weight_slider(label, key, default):
            col1, col2 = st.columns([1, 3])
            val = col2.slider(
                label, 0.0, 1.0, default, 0.05,
                label_visibility="collapsed", key=key
            )
            col1.markdown(
                f"<div style='font-size:12px;color:#a1a1aa;padding-top:8px'>{label}</div>",
                unsafe_allow_html=True
            )
            col1.markdown(
                f"<div style='font-size:12px;color:#ffffff;font-weight:700;"
                f"text-align:right;padding-top:8px'>{int(val*100)}%</div>",
                unsafe_allow_html=True
            )
            return val

        w_reach = weight_slider("触达量", "w_reach", 0.35)
        w_ctr = weight_slider("CTR", "w_ctr", 0.15)
        w_sales = weight_slider("订单Sales", "w_sales", 0.40)
        w_apu = weight_slider("单均价", "w_apu", 0.10)

        total_w = w_reach + w_ctr + w_sales + w_apu
        st.markdown(
            f"<div style='font-size:11px;color:#666;text-align:right;margin-top:8px'>"
            f"合计 {int(total_w*100)}%</div>",
            unsafe_allow_html=True
        )

    # ─── 综合评分 ─────────────────────────────────────────────
    df["综合评分"] = (
        df["触达_norm"] * w_reach
        + df["CTR_norm"] * w_ctr
        + df["Sales_norm"] * w_sales
        + df["单均价_norm"] * w_apu
    ).round(1)

    # ─── 筛选 ─────────────────────────────────────────────────
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
        dff = dff[
            dff[title_col].str.lower().str.contains(kw, na=False) |
            dff["内容"].str.lower().str.contains(kw, na=False)
        ]

    if len(dff) > 0:
        dff = dff.sort_values("综合评分", ascending=False).reset_index(drop=True)
    dff["排名"] = dff.index + 1

    # ─── 顶部指标 ─────────────────────────────────────────────
    total_rows = len(dff)
    total_score = dff["综合评分"].mean() if total_rows > 0 else 0
    top1_score = dff["综合评分"].max() if total_rows > 0 else 0
    avg_ctr = dff["CTR"].mean() if total_rows > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("上榜内容", f"{total_rows} 条")
    col2.metric("平均综合评分", f"{total_score:.1f}")
    col3.metric("最高综合评分", f"{top1_score:.1f}")
    col4.metric("平均 CTR", f"{avg_ctr:.2f}%")

    # ─── Tabs ─────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["排行榜", "数据表", "图表"])

    with tab1:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据")
        else:
            st.markdown(
                f'<div class="section-label">{total_rows} 条内容 · 按综合评分排序</div>',
                unsafe_allow_html=True
            )
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
                        card_class = "top-1"; badge_class = "rank-1"
                    elif rank == 2:
                        card_class = "top-2"; badge_class = "rank-2"
                    elif rank == 3:
                        card_class = "top-3"; badge_class = "rank-3"
                    else:
                        card_class = ""; badge_class = "rank-other"

                    date_val = getattr(row, '发送日期', None)
                    date_str = str(date_val)[:10] if date_val is not None and pd.notna(date_val) else ""
                    plan_type_val = getattr(row, '计划类型', None)
                    plan_type_short = str(plan_type_val)[:4] if plan_type_val is not None and pd.notna(plan_type_val) else ""
                    channel_val = getattr(row, '渠道', None)
                    channel_short = str(channel_val) if channel_val is not None and pd.notna(channel_val) else ""
                    title = str(getattr(row, '标题', '')) if getattr(row, '标题', '') else ''
                    content = str(getattr(row, '内容', '')) if getattr(row, '内容', '') else ''
                    if not title:
                        title = str(getattr(row, '消息标题', '')) if getattr(row, '消息标题', '') else ''

                    def safe_int(val, default=0):
                        try: return int(val)
                        except: return default
                    def safe_float(val, default=0.0):
                        try: return float(val)
                        except: return default

                    reach = safe_int(getattr(row, '触达成功', 0))
                    ctr_val = safe_float(getattr(row, 'CTR', 0))
                    gc_val = safe_int(getattr(row, '订单GC', 0))
                    sales_val = safe_float(getattr(row, '订单Sales', 0))
                    apu_val = safe_float(getattr(row, '单均价', 0))
                    score = row.综合评分

                    with col:
                        st.markdown(f"""
                        <div class="content-card {card_class}">
                          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                            <div style="display:flex; align-items:center;">
                              <span class="rank-badge {badge_class}">{rank}</span>
                              <span style="font-size:11px; color:{TEXT_SUB}; background:{CARD2}; padding:3px 8px; border-radius:12px; border:1px solid {BORDER};">
                                {plan_type_short} · {channel_short}
                              </span>
                              <span style="font-size:11px; color:{TEXT_DIM}; margin-left:10px;">{date_str}</span>
                            </div>
                            <div>
                              <div class="card-score">{score:.1f}</div>
                              <div class="card-score-label">综合评分</div>
                            </div>
                          </div>
                          <div class="card-title">【标题】{title[:80]}{'...' if len(title) > 80 else ''}</div>
                          <div class="card-content">{content[:200]}{'...' if len(content) > 200 else ''}</div>
                          <div class="card-meta">
                            <span>触达 {reach:,}</span>
                            <span>CTR {ctr_val:.2f}%</span>
                            <span>订单 {gc_val:,}</span>
                            <span>Sales {int(sales_val):,}</span>
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
        disp_df = dff[available].copy()
        if 'CTR' in disp_df.columns:
            disp_df['CTR'] = disp_df['CTR'].apply(lambda x: f"{x:.2f}%")
        if '订单Sales' in disp_df.columns:
            disp_df['订单Sales'] = disp_df['订单Sales'].apply(lambda x: int(x) if pd.notna(x) else '')

        st.dataframe(disp_df, use_container_width=True, hide_index=True, height=600)
        csv_out = disp_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下载 CSV", csv_out, "内容排行榜.csv", "text/csv", use_container_width=True)

    with tab3:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据")
        else:
            top10 = dff.head(10)
            fig_bar = px.bar(
                top10, x="排名", y="综合评分",
                color="综合评分",
                color_continuous_scale=["#333", "#666", "#fff"],
                text="综合评分",
                title="Top 10 综合评分"
            )
            fig_bar.update_traces(textposition="outside", textfont_color="#666")
            fig_bar.update_layout(
                template=None, showlegend=False, coloraxis_showscale=False,
                height=380, paper_bgcolor=BG, plot_bgcolor=BG,
                font_color=TEXT_SUB,
                title_font_color=TEXT
            )
            fig_bar.update_xaxes(color=TEXT_SUB, gridcolor=BORDER, tickfont_color=TEXT_SUB)
            fig_bar.update_yaxes(color=TEXT_SUB, gridcolor=BORDER, tickfont_color=TEXT_SUB)
            st.plotly_chart(fig_bar, use_container_width=True)

            title_col = "标题" if "标题" in dff.columns else "消息标题"
            fig_scatter = px.scatter(
                dff, x="触达成功", y="订单Sales", size="CTR",
                color="综合评分",
                color_continuous_scale=["#333", "#666", "#fff"],
                hover_name=title_col,
                title="触达量 vs 订单 Sales（气泡大小 = CTR）"
            )
            fig_scatter.update_layout(
                template=None, height=420, paper_bgcolor=BG, plot_bgcolor=BG,
                font_color=TEXT_SUB, title_font_color=TEXT
            )
            fig_scatter.update_xaxes(color=TEXT_SUB, gridcolor=BORDER, tickfont_color=TEXT_SUB)
            fig_scatter.update_yaxes(color=TEXT_SUB, gridcolor=BORDER, tickfont_color=TEXT_SUB)
            st.plotly_chart(fig_scatter, use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="section-label">触达量 Top 5</div>', unsafe_allow_html=True)
                top_reach = dff.nlargest(5, "触达成功")[["排名", title_col, "触达成功", "CTR", "综合评分"]]
                st.dataframe(top_reach, hide_index=True, use_container_width=True)
            with c2:
                st.markdown('<div class="section-label">订单 Sales Top 5</div>', unsafe_allow_html=True)
                top_sales = dff.nlargest(5, "订单Sales")[["排名", title_col, "订单Sales", "单均价", "综合评分"]]
                st.dataframe(top_sales, hide_index=True, use_container_width=True)

else:
    st.markdown("""
    <div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;
                padding:32px 24px;margin-top:8px;text-align:center;">
      <div style="font-size:36px;margin-bottom:16px;filter:grayscale(1)opacity(0.3);">↑</div>
      <div style="font-size:16px;font-weight:700;color:#fff;margin-bottom:8px;">上传 CSV 开始分析</div>
      <div style="font-size:13px;color:#a1a1aa;line-height:1.8;">
        原始 CSV：自动运行清洗逻辑，直接出排行榜<br>
        已清洗 CSV：直接使用<br><br>
        <span style="color:#666;">综合评分权重（默认）</span><br>
        触达量 35% · CTR 15% · 订单Sales 40% · 单均价 10%
      </div>
    </div>
    """, unsafe_allow_html=True)
