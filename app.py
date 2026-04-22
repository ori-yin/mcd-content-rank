# -*- coding: utf-8 -*-
"""
app.py - 麦当劳内容排行榜 (Streamlit Web App)
使用方法: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="麦当劳内容排行榜",
    page_icon="🏆",
    layout="wide"
)

# ─── 样式 ─────────────────────────────────────────────────────
MCD_RED = "#DA291C"
MCD_GOLD = "#FFC72C"
MCD_GREEN = "#00A04A"
MCD_BG = "#FAFAFA"

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
    display: inline-block;
    width: 32px; height: 32px;
    border-radius: 50%;
    text-align: center;
    line-height: 32px;
    font-weight: 900;
    font-size: 14px;
    margin-right: 8px;
  }}
  .rank-1 {{ background: {MCD_GOLD}; color: {MCD_RED}; }}
  .rank-2 {{ background: #C0C0C0; color: #555; }}
  .rank-3 {{ background: #CD7F32; color: #fff; }}
  .rank-other {{ background: #EEE; color: #888; }}
  .score-high {{ color: {MCD_RED}; font-weight: 900; }}
  .score-mid {{ color: #555; font-weight: 600; }}
  .score-low {{ color: #AAA; }}
  .content-card {{
    background: #FFF;
    border: 1px solid #EEE;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .card-title {{
    font-size: 15px; font-weight: 700; color: #1a1a1a;
    margin-bottom: 6px; line-height: 1.4;
  }}
  .card-content {{
    font-size: 13px; color: #555; line-height: 1.6;
    margin-bottom: 12px;
  }}
  .card-meta {{
    display: flex; gap: 16px; flex-wrap: wrap;
    font-size: 12px; color: #888;
  }}
  .card-meta span {{ background: #F5F5F5; padding: 3px 10px; border-radius: 20px; }}
  .card-score {{
    font-size: 24px; font-weight: 900; color: {MCD_RED};
    text-align: right; line-height: 1;
  }}
  .card-score-label {{ font-size: 11px; color: #AAA; text-align: right; }}
  .filter-section {{
    background: #FFF; border: 1px solid #EEE;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
  }}
  .metric-box {{
    background: {MCD_BG}; border-radius: 10px;
    padding: 12px 16px; text-align: center;
  }}
  .metric-val {{ font-size: 22px; font-weight: 900; color: {MCD_RED}; }}
  .metric-lbl {{ font-size: 11px; color: #888; margin-top: 2px; }}
  .section-title {{
    font-size: 15px; font-weight: 700; color: #1a1a1a;
    margin: 24px 0 12px 0; padding-bottom: 8px;
    border-bottom: 2px solid {MCD_GOLD};
  }}
  div[data-testid="stMetricValue"] {{ font-size: 20px !important; font-weight: 900 !important; color: {MCD_RED} !important; }}
  div[data-testid="stMetricLabel"] {{ font-size: 11px !important; color: #888 !important; }}
  .stDataFrame thead th {{ background: {MCD_RED} !important; color: #fff !important; font-size: 12px !important; }}
  .stDataFrame tbody tr:hover {{ background: #FFF5F5 !important; }}
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────
st.markdown(f"""
<div class="mcd-header">
  <h1>🏆 麦当劳内容排行榜</h1>
  <p>上传内容数据 CSV → 自动计算综合评分 → 生成可视化排行榜</p>
</div>
""", unsafe_allow_html=True)

# ─── 文件上传 ─────────────────────────────────────────────────
uploaded = st.file_uploader(
    "📤 上传内容数据 CSV 文件",
    type=["csv"],
    help="支持 UTF-8 或 GBK 编码的 CSV 文件"
)

if uploaded:
    try:
        df = pd.read_csv(uploaded, encoding="gbk")
    except Exception:
        try:
            df = pd.read_csv(uploaded, encoding="utf-8")
        except Exception:
            df = pd.read_csv(uploaded, encoding="utf-8-sig")

    # ─── 计算衍生指标 ─────────────────────────────────────────
    df["CTR"] = (df["点击人次"] / df["触达成功"] * 100).round(2)
    df["单均价"] = (df["订单Sales"] / df["订单GC"]).round(2)
    df["单均价"] = df["单均价"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # ─── 综合评分（Min-Max 归一化加权）─────────────────────────
    def minmax(series):
        mn, mx = series.min(), series.max()
        if mx == mn:
            return series * 0
        return (series - mn) / (mx - mn) * 100

    df["触达_norm"] = minmax(df["触达成功"])
    df["CTR_norm"] = minmax(df["CTR"])
    df["Sales_norm"] = minmax(df["订单Sales"])
    df["单均价_norm"] = minmax(df["单均价"])

    df["综合评分"] = (
        df["触达_norm"] * 0.35
        + df["CTR_norm"] * 0.15
        + df["Sales_norm"] * 0.40
        + df["单均价_norm"] * 0.10
    ).round(1)

    df["综合评分_norm"] = df["综合评分"]  # alias

    # ─── 排序 & 排名 ──────────────────────────────────────────
    df = df.sort_values("综合评分", ascending=False).reset_index(drop=True)
    df["排名"] = df.index + 1

    # ─── 侧边筛选 ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("**筛选条件**")
        plan_types = ["全部"] + df["计划类型"].dropna().unique().tolist()
        selected_plan = st.selectbox("计划类型", plan_types)
        channels = ["全部"] + df["渠道"].dropna().unique().tolist()
        selected_channel = st.selectbox("渠道", channels)
        keyword = st.text_input("🔍 搜索标题/内容关键词", "")

        # 权重调整
        st.markdown("---")
        st.markdown("**权重配置**")
        w_reach = st.slider("触达量权重", 0.0, 1.0, 0.35, 0.05)
        w_ctr = st.slider("CTR权重", 0.0, 1.0, 0.15, 0.05)
        w_sales = st.slider("订单Sales权重", 0.0, 1.0, 0.40, 0.05)
        w_apu = st.slider("单均价权重", 0.0, 1.0, 0.10, 0.05)

        # 重新计算评分
        total_w = w_reach + w_ctr + w_sales + w_apu
        df["综合评分"] = (
            df["触达_norm"] * w_reach
            + df["CTR_norm"] * w_ctr
            + df["Sales_norm"] * w_sales
            + df["单均价_norm"] * w_apu
        ).round(1)
        df = df.sort_values("综合评分", ascending=False).reset_index(drop=True)
        df["排名"] = df.index + 1

        if total_w == 0:
            st.warning("权重总和为 0，请调整权重")
        else:
            st.caption(f"权重合计: {total_w:.0%}")

    # ─── 筛选 ──────────────────────────────────────────────────
    dff = df.copy()
    if selected_plan != "全部":
        dff = dff[dff["计划类型"] == selected_plan]
    if selected_channel != "全部":
        dff = dff[dff["渠道"] == selected_channel]
    if keyword:
        kw = keyword.lower()
        dff = dff[
            dff["标题"].str.lower().str.contains(kw, na=False) |
            dff["内容"].str.lower().str.contains(kw, na=False)
        ]

    # ─── 顶部指标卡 ───────────────────────────────────────────
    total_rows = len(dff)
    total_score = dff["综合评分"].mean()
    top1_score = dff["综合评分"].max()
    avg_ctr = dff["CTR"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("上榜内容", f"{total_rows} 条")
    col2.metric("平均综合评分", f"{total_score:.1f}")
    col3.metric("最高综合评分", f"{top1_score:.1f}")
    col4.metric("平均 CTR", f"{avg_ctr:.2f}%")

    # ─── Tab 切换：卡片视图 / 表格视图 / 图表 ─────────────────
    tab1, tab2, tab3 = st.tabs(["🏆 卡片排行榜", "📋 数据表格", "📈 可视化图表"])

    with tab1:
        st.markdown(f"**{len(dff)} 条内容 · 按综合评分排序**")

        # 每行2张卡片
        cards = list(dff.itertuples())

        for i in range(0, len(cards), 2):
            cols = st.columns([1, 1], gap="medium")
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(cards):
                    break
                row = cards[idx]

                # 排名徽章颜色
                rank = row.排名
                if rank == 1:
                    badge_class = "rank-1"
                elif rank == 2:
                    badge_class = "rank-2"
                elif rank == 3:
                    badge_class = "rank-3"
                else:
                    badge_class = "rank-other"

                # 评分颜色
                score = row.综合评分
                if score >= 70:
                    score_color = MCD_RED
                elif score >= 40:
                    score_color = "#E07B00"
                else:
                    score_color = "#AAA"

                with col:
                    # 日期+渠道标签
                    date_str = str(row.发送日期)[:10] if pd.notna(row.发送日期) else ""
                    plan_type_short = str(row.计划类型)[:4] if pd.notna(row.计划类型) else ""
                    channel_short = str(row.渠道) if pd.notna(row.渠道) else ""

                    st.markdown(f"""
                    <div class="content-card">
                      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div style="flex:1;">
                          <span class="rank-badge {badge_class}">{rank}</span>
                          <span style="font-size:12px; color:#888; background:#F5F5F5; padding:2px 8px; border-radius:12px;">
                            {plan_type_short} · {channel_short}
                          </span>
                          <span style="font-size:12px; color:#AAA; margin-left:8px;">{date_str}</span>
                        </div>
                        <div>
                          <div class="card-score" style="color:{score_color};">{score}</div>
                          <div class="card-score-label">综合评分</div>
                        </div>
                      </div>
                      <div class="card-title">【标题】{row.标题}</div>
                      <div class="card-content">{row.内容[:200]}{'...' if len(str(row.内容)) > 200 else ''}</div>
                      <div class="card-meta">
                        <span>触达 {int(row.触达成功):,}</span>
                        <span>CTR {row.CTR:.2f}%</span>
                        <span>订单GC {int(row.订单GC):,}</span>
                        <span>订单Sales ¥{int(row.订单Sales):,}</span>
                        <span>单均价 ¥{row.单均价:.1f}</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab2:
        display_cols = ["排名", "标题", "内容", "计划类型", "渠道", "发送日期",
                         "触达成功", "CTR", "订单GC", "订单Sales", "单均价", "综合评分"]
        available = [c for c in display_cols if c in dff.columns]
        st.dataframe(
            dff[available],
            use_container_width=True,
            hide_index=True,
            height=600
        )
        csv_out = dff[available].to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 下载排行榜 CSV",
            csv_out,
            "麦当劳内容排行榜.csv",
            "text/csv",
            use_container_width=True
        )

    with tab3:
        # Top 10 柱状图
        top10 = dff.head(10)
        fig_bar = px.bar(
            top10,
            x="排名",
            y="综合评分",
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

        # 触达 vs 订单Sales 散点图
        fig_scatter = px.scatter(
            dff,
            x="触达成功",
            y="订单Sales",
            size="CTR",
            color="综合评分",
            color_continuous_scale=["#FFD700", "#DA291C"],
            hover_data=["标题"],
            hover_name="标题",
            title="触达量 vs 订单Sales（气泡大小=CTR，颜色=综合评分）"
        )
        fig_scatter.update_layout(
            template="plotly_white",
            height=450
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # 各指标 Top 5
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="section-title">📊 触达量 Top 5</div>', unsafe_allow_html=True)
            top_reach = dff.nlargest(5, "触达成功")[["排名", "标题", "触达成功", "CTR", "综合评分"]]
            st.dataframe(top_reach, hide_index=True, use_container_width=True)
        with c2:
            st.markdown('<div class="section-title">💰 订单Sales Top 5</div>', unsafe_allow_html=True)
            top_sales = dff.nlargest(5, "订单Sales")[["排名", "标题", "订单Sales", "单均价", "综合评分"]]
            st.dataframe(top_sales, hide_index=True, use_container_width=True)

else:
    # 空状态引导
    st.info("👆 请上传内容数据 CSV 文件开始分析")
    st.markdown("""
    **数据格式要求（CSV 列名）：**
    - `标题` — 内容标题
    - `内容` — 内容正文
    - `触达成功` — 触达人数
    - `点击人次` — 点击次数
    - `订单GC` — 订单数量
    - `订单Sales` — 订单金额
    - `计划类型` — 常规Plan / AARRPlan
    - `渠道` — APP Push / 企微1v1

    **综合评分权重（默认）：**
    - 触达量 35% + CTR 15% + 订单Sales 40% + 单均价 10%
    """)
