# -*- coding: utf-8 -*-
"""
app.py - 麦当劳内容排行榜 v2 (Streamlit Web App)

v2 新增功能：
  - 日期范围滑轨筛选（默认最近7日）
  - 预算 Owner 动态筛选
  - 筛选后 HTML 一键下载
  - 更强的空文件 / 乱码容错
  - 灵活列名映射（支持多种编码）

使用方法: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime, timedelta
import io
import sys

st.set_page_config(
    page_title="麦当劳内容排行榜",
    page_icon=":trophy:",
    layout="wide"
)

# ─── 麦当劳品牌色 ───────────────────────────────────────────
MCD_RED   = "#DA291C"
MCD_GOLD  = "#FFC72C"
MCD_GREEN = "#00A04A"
MCD_BG    = "#FAFAFA"

# ─── 全局样式 ────────────────────────────────────────────────
st.markdown(f"""
<style>
  .block-container {{ padding-top: 1rem; }}
  .mcd-header {{
    background: linear-gradient(135deg, {MCD_RED}, #b71c1c);
    border-radius: 14px; padding: 24px 32px; color: #fff;
    margin-bottom: 20px;
  }}
  .mcd-header h1 {{ font-size: 22px; font-weight: 900; margin: 0 0 4px 0; }}
  .mcd-header p {{ font-size: 13px; opacity: 0.85; margin: 0; }}
  .rank-badge {{
    display: inline-block; width: 32px; height: 32px;
    border-radius: 50%; text-align: center; line-height: 32px;
    font-weight: 900; font-size: 14px; margin-right: 8px;
  }}
  .rank-1 {{ background: {MCD_GOLD}; color: {MCD_RED}; }}
  .rank-2 {{ background: #C0C0C0; color: #555; }}
  .rank-3 {{ background: #CD7F32; color: #fff; }}
  .rank-other {{ background: #EEE; color: #888; }}
  .content-card {{
    background: #FFF; border: 1px solid #EEE; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .card-title {{
    font-size: 15px; font-weight: 700; color: #1a1a1a;
    margin: 10px 0 6px 0; line-height: 1.4;
  }}
  .card-content-preview {{
    font-size: 13px; color: #555; line-height: 1.6;
    margin-bottom: 10px; font-style: italic;
  }}
  .card-meta {{ display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: #888; }}
  .card-meta span {{ background: #F5F5F5; padding: 3px 10px; border-radius: 20px; }}
  .card-score {{ font-size: 24px; font-weight: 900; color: {MCD_RED}; text-align: right; line-height: 1; }}
  .card-score-label {{ font-size: 11px; color: #AAA; text-align: right; }}
  .section-title {{
    font-size: 15px; font-weight: 700; color: #1a1a1a;
    margin: 24px 0 12px 0; padding-bottom: 8px;
    border-bottom: 2px solid {MCD_GOLD};
  }}
  .filter-info {{
    font-size: 12px; color: #888; margin-bottom: 8px;
  }}
  div[data-testid="stMetricValue"] {{ font-size: 20px !important; font-weight: 900 !important; color: {MCD_RED} !important; }}
  div[data-testid="stMetricLabel"] {{ font-size: 11px !important; color: #888 !important; }}
  .stDataFrame thead th {{ background: {MCD_RED} !important; color: #fff !important; font-size: 12px !important; }}
  .stDataFrame tbody tr:hover {{ background: #FFF5F5 !important; }}
  .download-info {{
    background: #FFF; border: 2px dashed {MCD_GOLD}; border-radius: 12px;
    padding: 16px 20px; margin: 16px 0; text-align: center;
  }}
</style>
""", unsafe_allow_html=True)

# ─── Header ─────────────────────────────────────────────────
st.markdown(f"""
<div class="mcd-header">
  <h1>:trophy: 麦当劳内容排行榜</h1>
  <p>上传 CSV → 自动计算综合评分 → 筛选 → 下载 HTML 报表</p>
</div>
""", unsafe_allow_html=True)

# ─── 列名标准化映射 ─────────────────────────────────────────
# 支持多种来源 CSV 的列名，统一映射为内部标准列名
COLUMN_ALIASES = {
    # 标准中文名
    "发送日期":    "send_date",
    "触达成功":    "reach",
    "点击人次":    "clicks",
    "订单GC":      "orders",
    "订单Sales":   "sales",
    "计划类型":    "plan_type",
    "渠道":        "channel",
    "Plan Name":  "title",
    "标题":        "title",
    "消息标题":     "msg_title",
    "内容":        "body",
    "预算owner":   "owner",
    "Plan ID":    "plan_id",
    # 兼容无中文列名的原始导出格式（实际列名对应）
    "send_date":  "send_date",
    # 以下为乱码情况（UTF-8 解码失败后 GBK 重试仍残存的 mojibake，
    # 但字节序列可唯一识别，做二次映射兜底）
}
# 按字节特征识别"乱码中文"列（GBK 可读但 UTF-8 报错的列，其列名字节在 gbk 编码后
# 对应特定中文，实际通过列索引做兜底映射）
# 实际业务 CSV 列顺序固定，按位置兜底映射：
POSITION_MAP = {
    0: "send_date",    # 发送日期
    1: "plan_type",   # 计划类型
    2: "channel",     # 渠道
    3: "plan_id",     # Plan ID
    4: "plan_name",   # Plan名称
    5: "owner",       # 预算owner
    6: "is_coupon",   # 是否用券（不参与计算）
    7: "budget_reach",# 预计触达（不参与计算）
    8: "reach",       # 触达成功
    9: "clicks",      # 点击人次
    10: "click_orders",# 点击后下单人次（不参与计算）
    11: "orders",     # 订单GC
    12: "sales",      # 订单Sales
    13: "msg_title",  # 消息标题
    14: "title",      # 标题
    15: "body",       # 内容
}


def read_csv_flexible(uploaded_file):
    """尝试多种编码读取 CSV，兜底空文件处理。"""
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"]
    for enc in encodings:
        try:
            uploaded_file.seek(0)
            raw_bytes = uploaded_file.getvalue()
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, dtype=str)
            # 去空列
            df = df.loc[:, df.columns.str.strip() != ""]
            if df.shape[0] == 0:
                return None, "文件为空（0 行），请检查 CSV 内容"
            return df, None
        except Exception:
            pass
    return None, "无法识别文件编码，请将 CSV 保存为 UTF-8 格式后重试"


def normalize_columns(df):
    """将原始列名标准化为内部列名。"""
    # 先做精确匹配
    rename_map = {}
    for col in df.columns:
        col_s = str(col).strip()
        if col_s in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col_s]
    # 兜底：按位置映射（仅当列数与预期一致时）
    if len(df.columns) >= 13:
        for idx, std_name in POSITION_MAP.items():
            if idx < len(df.columns):
                orig = df.columns[idx]
                if orig not in rename_map:
                    rename_map[orig] = std_name
    df = df.rename(columns=rename_map)
    # 去掉空列
    df = df.loc[:, ~df.columns.str.match(r"^_")]
    return df


def normalize_values(df):
    """清洗数值列中的逗号和 [NULL] 等干扰字符。"""
    num_cols = ["reach", "clicks", "orders", "sales"]
    for col in num_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
                .replace({"[NULL]": "0", "None": "0", "nan": "0"})
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def parse_date(col):
    """解析日期列，支持多种格式。"""
    if col not in ["send_date", "发送日期"]:
        return pd.to_datetime(col, errors="coerce")
    return pd.to_datetime(col, errors="coerce")


# ─── 综合评分计算 ────────────────────────────────────────────
def compute_metrics(df, w_reach=0.35, w_ctr=0.15, w_sales=0.40, w_apu=0.10):
    """计算 CTR / 单均价 / 综合评分。"""
    df = df.copy()
    # CTR
    df["ctr"] = (df["clicks"] / df["reach"].replace(0, 1) * 100).round(2)
    # 单均价
    df["apu"] = (df["sales"] / df["orders"].replace(0, 1)).round(2)
    df["apu"] = df["apu"].replace([float("inf"), -float("inf")], 0)
    df["apu"] = df["apu"].fillna(0)

    # Min-Max 归一化
    def minmax(s):
        mn, mx = s.min(), s.max()
        if mx == mn:
            return s * 0
        return (s - mn) / (mx - mn) * 100

    df["reach_norm"] = minmax(df["reach"])
    df["ctr_norm"]   = minmax(df["ctr"])
    df["sales_norm"] = minmax(df["sales"])
    df["apu_norm"]   = minmax(df["apu"])

    df["score"] = (
        df["reach_norm"] * w_reach
        + df["ctr_norm"]   * w_ctr
        + df["sales_norm"] * w_sales
        + df["apu_norm"]   * w_apu
    ).round(1)

    return df


def build_rank_table(df):
    """生成排行榜表格。"""
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


# ─── HTML 生成 ────────────────────────────────────────────────
def generate_html(df_orig, w_reach, w_ctr, w_sales, w_apu):
    """基于当前筛选结果生成完整 HTML 报表。"""
    df = df_orig.copy()
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 头部 ──
    header = f"""
    <div style="background:{MCD_RED};padding:20px 28px;border-radius:14px;margin-bottom:20px;">
      <h1 style="color:#fff;font-size:20px;font-weight:900;margin:0 0 4px 0;">
        麦当劳内容排行榜
      </h1>
      <p style="color:rgba(255,255,255,0.8);font-size:12px;margin:0;">
        报表日期 {today} &nbsp;|&nbsp; 权重: 触达{int(w_reach*100)}% · CTR{int(w_ctr*100)}% · Sales{int(w_sales*100)}% · 单均价{int(w_apu*100)}%
      </p>
    </div>"""

    # ── 摘要指标 ──
    total = len(df)
    avg_s = df["score"].mean()
    max_s = df["score"].max()
    avg_c = df["ctr"].mean()

    summary = f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
      <div style="background:#FAFAFA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;font-weight:900;color:{MCD_RED};">{total}</div>
        <div style="font-size:11px;color:#888;margin-top:2px;">上榜内容 (条)</div>
      </div>
      <div style="background:#FAFAFA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;font-weight:900;color:{MCD_RED};">{avg_s:.1f}</div>
        <div style="font-size:11px;color:#888;margin-top:2px;">平均综合评分</div>
      </div>
      <div style="background:#FAFAFA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;font-weight:900;color:{MCD_RED};">{max_s:.1f}</div>
        <div style="font-size:11px;color:#888;margin-top:2px;">最高综合评分</div>
      </div>
      <div style="background:#FAFAFA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;font-weight:900;color:{MCD_RED};">{avg_c:.2f}%</div>
        <div style="font-size:11px;color:#888;margin-top:2px;">平均 CTR</div>
      </div>
    </div>"""

    # ── 排名卡片 ──
    rows_html = ""
    for _, row in df.iterrows():
        rank = int(row["rank"])
        score = row["score"]
        title = str(row.get("title", row.get("plan_id", "")))
        body  = str(row.get("body", ""))[:300]
        reach = int(row["reach"])
        ctr   = row["ctr"]
        orders= int(row["orders"])
        sales = int(row["sales"])
        apu   = row["apu"]
        owner = str(row.get("owner", ""))
        plan  = str(row.get("plan_type", ""))
        ch    = str(row.get("channel", ""))
        pid   = str(row.get("plan_id", ""))

        # 排名色
        if rank == 1:
            badge_cls = "rank-1"; badge_bg = MCD_GOLD; badge_color = MCD_RED
        elif rank == 2:
            badge_cls = "rank-2"; badge_bg = "#C0C0C0"; badge_color = "#555"
        elif rank == 3:
            badge_cls = "rank-3"; badge_bg = "#CD7F32"; badge_color = "#fff"
        else:
            badge_cls = "rank-other"; badge_bg = "#EEE"; badge_color = "#888"

        # 评分色
        if score >= 70:
            score_color = MCD_RED
        elif score >= 40:
            score_color = "#E07B00"
        else:
            score_color = "#AAA"

        rows_html += f"""
        <div style="background:#FFF;border:1px solid #EEE;border-radius:12px;padding:16px 20px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div style="flex:1;">
              <span style="display:inline-block;width:32px;height:32px;border-radius:50%;text-align:center;
                          line-height:32px;font-weight:900;font-size:14px;
                          background:{badge_bg};color:{badge_color};margin-right:8px;">{rank}</span>
              <span style="font-size:12px;color:#888;background:#F5F5F5;padding:2px 8px;border-radius:12px;">{plan} · {ch}</span>
              <span style="font-size:12px;color:#AAA;margin-left:8px;">{owner}</span>
            </div>
            <div>
              <div style="font-size:24px;font-weight:900;color:{score_color};line-height:1;">{score}</div>
              <div style="font-size:11px;color:#AAA;">综合评分</div>
            </div>
          </div>
          <div style="font-size:15px;font-weight:700;color:#1a1a1a;margin:10px 0 6px 0;line-height:1.4;">{title}</div>
          {('<div style="font-size:13px;color:#555;line-height:1.6;margin-bottom:10px;font-style:italic;">' + body[:200] + ('...' if len(body)>200 else '') + '</div>') if body and body != 'nan' else ''}
          <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#888;">
            <span style="background:#F5F5F5;padding:3px 10px;border-radius:20px;">触达 {reach:,}</span>
            <span style="background:#F5F5F5;padding:3px 10px;border-radius:20px;">CTR {ctr:.2f}%</span>
            <span style="background:#F5F5F5;padding:3px 10px;border-radius:20px;">订单GC {orders:,}</span>
            <span style="background:#F5F5F5;padding:3px 10px;border-radius:20px;">订单Sales ¥{sales:,}</span>
            <span style="background:#F5F5F5;padding:3px 10px;border-radius:20px;">单均价 ¥{apu:.1f}</span>
          </div>
        </div>"""

    # ── 图表 ──
    top10 = df.head(10)
    chart_bar = px.bar(
        top10, x="rank", y="score", color="score",
        color_continuous_scale=[MCD_GOLD, MCD_RED],
        text="score", title="Top 10 综合评分"
    )
    chart_bar.update_traces(textposition="outside")
    chart_bar.update_layout(
        template="plotly_white", showlegend=False,
        coloraxis_showscale=False, height=380,
        title_font_size=16, title_x=0
    )

    chart_scatter = px.scatter(
        df, x="reach", y="sales", size="ctr",
        color="score", color_continuous_scale=[MCD_GOLD, MCD_RED],
        hover_data=["title"], hover_name="title",
        title="触达量 vs 订单Sales（气泡大小=CTR，颜色=综合评分）"
    )
    chart_scatter.update_layout(template="plotly_white", height=420, title_font_size=16, title_x=0)

    bar_html  = pio.to_html(chart_bar,    include_plotlyjs=True, full_html=False)
    scatter_html = pio.to_html(chart_scatter, include_plotlyjs=True, full_html=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>麦当劳内容排行榜 - {today}</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
           background: {MCD_BG}; margin: 0; padding: 16px; color: #1a1a1a; }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    @media (max-width: 768px) {{ .grid-4 {{ grid-template-columns: repeat(2, 1fr) !important; }} }}
  </style>
</head>
<body>
<div class="container">
  {header}
  {summary}
  <div style="background:#FFF;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
    <h2 style="font-size:15px;font-weight:700;color:#1a1a1a;margin:0 0 12px 0;padding-bottom:8px;border-bottom:2px solid {MCD_GOLD};">📈 可视化图表</h2>
    {bar_html}
    {scatter_html}
  </div>
  <div style="background:#FFF;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
    <h2 style="font-size:15px;font-weight:700;color:#1a1a1a;margin:0 0 16px 0;padding-bottom:8px;border-bottom:2px solid {MCD_GOLD};">🏆 排行榜（{total} 条）</h2>
    {rows_html}
  </div>
</div>
</body>
</html>"""
    return html


# ─── 文件上传 ─────────────────────────────────────────────────
uploaded = st.file_uploader(
    ":inbox_tray: 上传内容数据 CSV",
    type=["csv"],
    help="支持 UTF-8、GBK 编码，列名包含：发送日期/触达成功/点击人次/订单GC/订单Sales/计划类型/渠道 等"
)

if not uploaded:
    st.info(":point_up: 请上传内容数据 CSV 文件开始分析")
    st.markdown("""
    **数据格式要求（CSV 列名对应关系）：**
    | CSV 列名 | 说明 |
    |---|---|
    | 发送日期 / send_date | 内容发送日期 |
    | 计划类型 | aarr / normal 等 |
    | 渠道 | APP Push / 微信1v1 / 短信 等 |
    | 触达成功 | 触达人数 |
    | 点击人次 | 点击次数 |
    | 订单GC | 订单数量 |
    | 订单Sales | 订单金额 |
    | 预算owner | 预算负责人（用于 Owner 筛选） |
    | 标题 / Plan Name | 内容标题（用于展示） |
    | 内容 / body | 内容正文（可选） |

    **综合评分权重（默认）：**
    - 触达量 35% + CTR 15% + 订单Sales 40% + 单均价 10%
    """)
    st.stop()

# ─── 读取 & 标准化 ───────────────────────────────────────────
df_raw, err = read_csv_flexible(uploaded)
if err:
    st.error(f"读取文件失败：{err}")
    sys.exit(0)

df_raw = normalize_columns(df_raw)
df_raw = normalize_values(df_raw)

# 解析日期
if "send_date" in df_raw.columns:
    df_raw["send_date"] = pd.to_datetime(df_raw["send_date"], errors="coerce")

# 必需列检查
needed = ["reach", "clicks", "orders", "sales"]
missing = [c for c in needed if c not in df_raw.columns]
if missing:
    st.error(f"缺少必需列：{missing}。请检查 CSV 列名，或确认文件格式。")
    st.dataframe(df_raw.head(3))
    st.stop()

# ─── 计算指标 ─────────────────────────────────────────────────
df = compute_metrics(df_raw)
df = build_rank_table(df)

# ─── 侧边栏筛选 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("**筛选条件**")

    # 日期范围
    if "send_date" in df.columns and df["send_date"].notna().any():
        date_min = df["send_date"].min().date()
        date_max = df["send_date"].max().date()
        default_start = date_max - timedelta(days=6)  # 默认最近7天
        st.markdown('<p class="filter-info">日期范围（起止均含）</p>', unsafe_allow_html=True)
        date_range = st.slider(
            "发送日期范围",
            min_value=date_min,
            max_value=date_max,
            value=(default_start, date_max),
            format="YYYY-MM-DD"
        )
    else:
        date_range = None

    # 计划类型
    plan_types = ["全部"] + (df["plan_type"].dropna().unique().tolist() if "plan_type" in df.columns else [])
    selected_plan = st.selectbox("计划类型", plan_types)

    # 渠道
    channels = ["全部"] + (df["channel"].dropna().unique().tolist() if "channel" in df.columns else [])
    selected_channel = st.selectbox("渠道", channels)

    # Owner（动态）
    if "owner" in df.columns:
        owners = ["全部"] + df["owner"].dropna().str.strip().unique().tolist()
        owners = [o for o in owners if o and o != "nan" and o != "[NULL]"]
        selected_owner = st.selectbox("预算 Owner", owners)
    else:
        selected_owner = "全部"

    # 关键词搜索
    keyword = st.text_input(":mag: 搜索标题关键词", "")

    st.markdown("---")
    st.markdown("**权重配置**")

    w_reach = st.slider("触达量权重", 0.0, 1.0, 0.35, 0.05, key="w_reach")
    w_ctr   = st.slider("CTR权重",   0.0, 1.0, 0.15, 0.05, key="w_ctr")
    w_sales = st.slider("订单Sales权重", 0.0, 1.0, 0.40, 0.05, key="w_sales")
    w_apu   = st.slider("单均价权重", 0.0, 1.0, 0.10, 0.05, key="w_apu")

    total_w = w_reach + w_ctr + w_sales + w_apu
    if total_w == 0:
        st.warning("权重总和为 0，请调整")
    else:
        st.caption(f"权重合计：{total_w:.0%}")

    # 重新计算评分
    df = compute_metrics(df, w_reach, w_ctr, w_sales, w_apu)
    df = build_rank_table(df)

# ─── 执行筛选 ─────────────────────────────────────────────────
dff = df.copy()

if date_range and "send_date" in dff.columns:
    dff = dff[
        (dff["send_date"] >= pd.Timestamp(date_range[0])) &
        (dff["send_date"] <= pd.Timestamp(date_range[1]) + pd.Timedelta(days=1))
    ]

if selected_plan != "全部" and "plan_type" in dff.columns:
    dff = dff[dff["plan_type"] == selected_plan]

if selected_channel != "全部" and "channel" in dff.columns:
    dff = dff[dff["channel"] == selected_channel]

if selected_owner != "全部" and "owner" in dff.columns:
    dff = dff[dff["owner"] == selected_owner]

if keyword:
    kw = keyword.lower()
    title_col = "title" if "title" in dff.columns else "plan_id"
    dff = dff[dff[title_col].astype(str).str.lower().str.contains(kw, na=False)]

# ─── 顶部摘要指标 ─────────────────────────────────────────────
total_rows = len(dff)
total_score = dff["score"].mean() if total_rows > 0 else 0
top1_score  = dff["score"].max()  if total_rows > 0 else 0
avg_ctr     = dff["ctr"].mean()   if total_rows > 0 else 0

st.markdown(f"筛选后 **{total_rows} 条**内容（原始 **{len(df)} 条**）")

col1, col2, col3, col4 = st.columns(4)
col1.metric("上榜内容", f"{total_rows} 条")
col2.metric("平均综合评分", f"{total_score:.1f}")
col3.metric("最高综合评分", f"{top1_score:.1f}")
col4.metric("平均 CTR", f"{avg_ctr:.2f}%")

# ─── HTML 下载按钮（独立在指标下方）─────────────────────────
if total_rows > 0:
    html_content = generate_html(dff, w_reach, w_ctr, w_sales, w_apu)
    today_str = datetime.now().strftime("%Y%m%d")
    st.download_button(
        label=f":arrow_down: 下载 HTML 报表（{total_rows} 条）",
        data=html_content.encode("utf-8"),
        file_name=f"麦当劳内容排行榜_{today_str}.html",
        mime="text/html",
        use_container_width=True,
        type="primary"
    )

# ─── Tab 视图 ─────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🏆 卡片排行榜", "📋 数据表格", "📈 可视化图表"])

with tab1:
    st.markdown(f"**{len(dff)} 条内容 · 按综合评分排序**")

    cards = list(dff.itertuples())

    for i in range(0, len(cards), 2):
        cols = st.columns([1, 1], gap="medium")
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(cards):
                break
            row = cards[idx]

            rank = row.rank
            if rank == 1:
                badge_cls = "rank-1"; badge_bg = MCD_GOLD; badge_color = MCD_RED
            elif rank == 2:
                badge_cls = "rank-2"; badge_bg = "#C0C0C0"; badge_color = "#555"
            elif rank == 3:
                badge_cls = "rank-3"; badge_bg = "#CD7F32"; badge_color = "#fff"
            else:
                badge_cls = "rank-other"; badge_bg = "#EEE"; badge_color = "#888"

            score = row.score
            if score >= 70:
                score_color = MCD_RED
            elif score >= 40:
                score_color = "#E07B00"
            else:
                score_color = "#AAA"

            title   = str(getattr(row, "title", row.plan_id)) if hasattr(row, "title") else str(row.plan_id)
            body    = str(getattr(row, "body", ""))[:300] if hasattr(row, "body") else ""
            reach   = int(row.reach)
            ctr     = row.ctr
            orders  = int(row.orders)
            sales   = int(row.sales)
            apu     = row.apu
            owner   = str(getattr(row, "owner", "")) if hasattr(row, "owner") else ""
            plan    = str(getattr(row, "plan_type", "")) if hasattr(row, "plan_type") else ""
            channel = str(getattr(row, "channel", "")) if hasattr(row, "channel") else ""
            date_s  = str(row.send_date)[:10] if hasattr(row, "send_date") and pd.notna(row.send_date) else ""

            with col:
                st.markdown(f"""
                <div class="content-card">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div style="flex:1;">
                      <span class="rank-badge {badge_cls}" style="background:{badge_bg};color:{badge_color};">{rank}</span>
                      <span style="font-size:12px;color:#888;background:#F5F5F5;padding:2px 8px;border-radius:12px;">{plan} · {channel}</span>
                      <span style="font-size:12px;color:#AAA;margin-left:8px;">{owner}</span>
                    </div>
                    <div>
                      <div class="card-score" style="color:{score_color};">{score}</div>
                      <div class="card-score-label">综合评分</div>
                    </div>
                  </div>
                  <div class="card-title">{title}</div>
                  {('<div class="card-content-preview">' + body[:200] + ('...' if len(body)>200 else '') + '</div>') if body and body!='nan' else ''}
                  <div class="card-meta">
                    <span>触达 {reach:,}</span>
                    <span>CTR {ctr:.2f}%</span>
                    <span>订单GC {orders:,}</span>
                    <span>Sales ¥{sales:,}</span>
                    <span>单均价 ¥{apu:.1f}</span>
                    {f'<span>{date_s}</span>' if date_s else ''}
                  </div>
                </div>
                """, unsafe_allow_html=True)

with tab2:
    disp_cols = ["rank", "title", "plan_type", "channel", "owner", "reach",
                 "ctr", "orders", "sales", "apu", "score"]
    rename_display = {
        "rank": "排名", "title": "标题", "plan_type": "计划类型",
        "channel": "渠道", "owner": "预算Owner", "reach": "触达成功",
        "ctr": "CTR", "orders": "订单GC", "sales": "订单Sales",
        "apu": "单均价", "score": "综合评分"
    }
    dff_disp = dff[disp_cols].rename(columns=rename_display)
    st.dataframe(dff_disp, use_container_width=True, hide_index=True, height=600)

    csv_out = dff_disp.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 下载排行榜 CSV",
        csv_out,
        f"麦当劳内容排行榜_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv",
        use_container_width=True
    )

with tab3:
    if len(dff) == 0:
        st.warning("当前筛选条件无数据，请调整筛选条件")
    else:
        # Top 10 柱状图
        top10 = dff.head(10)
        fig_bar = px.bar(
            top10, x="rank", y="score", color="score",
            color_continuous_scale=[MCD_GOLD, MCD_RED],
            text="score", title="Top 10 综合评分"
        )
        fig_bar.update_traces(textposition="outside")
        fig_bar.update_layout(
            template="plotly_white", showlegend=False,
            coloraxis_showscale=False, height=380,
            title_font_size=16, title_x=0
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # 散点图
        fig_scatter = px.scatter(
            dff, x="reach", y="sales", size="ctr",
            color="score", color_continuous_scale=[MCD_GOLD, MCD_RED],
            hover_data=["title"], hover_name="title",
            title="触达量 vs 订单Sales（气泡大小=CTR，颜色=综合评分）"
        )
        fig_scatter.update_layout(template="plotly_white", height=420, title_font_size=16, title_x=0)
        st.plotly_chart(fig_scatter, use_container_width=True)

        # 分维度 Top 5
        c1, c2, c3, c4 = st.columns(4)
        metrics_top5 = {
            c1: ("触达量 Top 5", "reach", ["rank", "title", "reach", "ctr", "score"]),
            c2: ("订单Sales Top 5", "sales", ["rank", "title", "sales", "apu", "score"]),
            c3: ("CTR Top 5", "ctr",   ["rank", "title", "reach", "ctr", "orders"]),
            c4: ("单均价 Top 5", "apu", ["rank", "title", "sales", "apu", "orders"]),
        }
        for col, (title, sort_col, show_cols) in metrics_top5.items():
            with col:
                st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
                top5 = dff.nlargest(5, sort_col)[[c for c in show_cols if c in dff.columns]]
                rename_t5 = {"rank": "排名", "title": "标题", "reach": "触达", "ctr": "CTR",
                             "sales": "Sales", "apu": "单均价", "orders": "订单GC", "score": "评分"}
                top5_disp = top5.rename(columns=rename_t5)
                st.dataframe(top5_disp, hide_index=True, use_container_width=True)
