"""
app.py - 麦当劳内容排行榜
"""
import html as _html
import streamlit_mermaid as stmd
import streamlit as st
import pandas as pd
from datetime import timedelta

from config import MCD_RED, MCD_GOLD, MCD_BG, OWNER_COL
from styles import get_css
from data_cleaning import clean_raw_csv, read_cleaned_csv
from scoring import compute_derived_metrics, compute_full_scores, compute_filtered_scores

st.set_page_config(
    page_title="麦当劳内容排行榜",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── 注入样式 ─────────────────────────────────────────────────
st.markdown(get_css(), unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────
st.markdown(f"""
<div class="mcd-header">
  <h1>麦当劳内容排行榜</h1>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 文件上传 + 清洗模式选择
# ═══════════════════════════════════════════════════════════════

with st.expander("数据源", expanded=(st.session_state.get("last_file_id") is None)):
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
        df = read_cleaned_csv(uploaded)

    # ─── 解析日期列 ────────────────────────────────────────────
    date_col = "发送日期"
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # ─── 计算衍生指标 ─────────────────────────────────────────
    df = compute_derived_metrics(df)

    # ─── 计算全量综合评分（用于渠道均值）─────────────────────────
    df = compute_full_scores(df)
    channel_avg_score = df.groupby("渠道")["综合评分_full"].mean().to_dict() if "渠道" in df.columns else {}

    # ─── 侧边筛选 ─────────────────────────────────────────────
    with st.sidebar:
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

        # ─── 权重配置 ─────────────────────────────────────────────
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

    # ─── 应用筛选 ─────────────────────────────────────────────
    dff = df

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
        title_candidates = [c for c in ["标题", "消息标题"] if c in dff.columns]
        if title_candidates:
            mask |= dff[title_candidates[0]].astype(str).str.lower().str.contains(kw, na=False)
        if "内容" in dff.columns:
            mask |= dff["内容"].astype(str).str.lower().str.contains(kw, na=False)
        dff = dff[mask]

    # ─── 计算筛选后的综合评分 ──────────────────────────────────
    dff = compute_filtered_scores(dff, norm_reach, norm_ctr, norm_gc)

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
    tab1, tab2, tab3 = st.tabs(["卡片排行榜", "算法说明", "数据表格"])

    # ═══════════════════════════════════════════════════════════
    # Tab 1: 卡片排行榜
    # ═══════════════════════════════════════════════════════════
    with tab1:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据，请调整筛选条件")
        else:
            cards = list(dff.itertuples())

            # 分页
            if st.session_state.get("card_total") != len(cards):
                st.session_state.card_page = 1
                st.session_state.card_total = len(cards)
            PAGE_SIZE = 50
            total_pages = max(1, (len(cards) + PAGE_SIZE - 1) // PAGE_SIZE)
            if "card_page" not in st.session_state:
                st.session_state.card_page = 1
            page = st.session_state.card_page
            page_cards = cards[(page-1)*PAGE_SIZE : page*PAGE_SIZE]

            # 合并渲染：拼成一个 HTML 字符串
            html_parts = []
            for row in page_cards:
                rank = row.排名
                badge_class = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(rank, "rank-other")

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
                impact_parts = []
                if reach_norm < 33:
                    impact_parts.append("触达偏低({:.1f})".format(reach_norm))
                elif reach_norm > 67:
                    impact_parts.append("触达偏高({:.1f})".format(reach_norm))
                if ctr_score_t < 33:
                    impact_parts.append("CTR偏低({:.1f})".format(ctr_score_t))
                elif ctr_score_t > 67:
                    impact_parts.append("CTR偏高({:.1f})".format(ctr_score_t))
                if gc_score_t < 33:
                    impact_parts.append("GC转化率偏低({:.1f})".format(gc_score_t))
                elif gc_score_t > 67:
                    impact_parts.append("GC转化率偏高({:.1f})".format(gc_score_t))
                impact = " / ".join(impact_parts) if impact_parts else "各项均衡"
                formula = "({:.1f}x{:.2f} + {:.1f}x{:.2f} + {:.1f}x{:.2f}) x {:.1f} = {:.2f}  [{}]".format(
                    reach_norm, w_reach, ctr_score_t, w_ctr, gc_score_t, w_gc,
                    penalty_coef_t, score, penalty_label
                )
                tooltip_text = _html.escape(impact + chr(10) + formula)

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

            # 底部翻页
            pcol1, pcol2, pcol3 = st.columns([1, 3, 1])
            with pcol1:
                if page > 1:
                    if st.button("⬅ 上一页", use_container_width=True):
                        st.session_state.card_page = page - 1
                        st.rerun()
            with pcol2:
                st.markdown(f"<div style='text-align:center; color:#888; font-size:13px; padding-top:6px;'>第 {page} / {total_pages} 页，共 {len(cards)} 条</div>", unsafe_allow_html=True)
            with pcol3:
                if page < total_pages:
                    if st.button("下一页 ➡", use_container_width=True):
                        st.session_state.card_page = page + 1
                        st.rerun()

    # ═══════════════════════════════════════════════════════════
    # Tab 2: 算法说明
    # ═══════════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-title">综合评分算法说明</div>', unsafe_allow_html=True)
        stmd.st_mermaid("""
flowchart TD
    A[原始数据] --> B[计算衍生指标]
    B --> C["CTR分 CTR_score"]
    B --> D["GC分 GC_score"]
    A --> G["触达分 = (触达/最大触达)^0.3 x 100"]
    C --> E1{"CTR < 渠道Q3?"}
    E1 -->|是| E2["100 x (CTR/Q3)^1.5"]
    E1 -->|否| E3["100 饱和"]
    D --> F1{"GC率 < 渠道Q3?"}
    F1 -->|是| F2["100 x (GC率/Q3)^1.5"]
    F1 -->|否| F3["100 饱和"]
    G --> H["加权求和"]
    E2 --> H
    E3 --> H
    F2 --> H
    F3 --> H
    H --> I["base = 触达 x0.2 + CTR x0.5 + GC x0.3"]
    I --> J["置信度惩戒"]
    J --> J1{"触达量"}
    J1 -->|"< 100"| J2["x 0.1"]
    J1 -->|"100~499"| J3["x 0.3"]
    J1 -->|"500~999"| J4["x 0.5"]
    J1 -->|"1000~4999"| J5["x 0.8"]
    J1 -->|">=5000"| J6["x 1.0"]
    J2 --> K["综合评分"]
    J3 --> K
    J4 --> K
    J5 --> K
    J6 --> K
    style K fill:#DA291C,color:#fff,font-weight:bold
    style I fill:#FFC000,color:#000
    style H fill:#FFC000,color:#000
""", height=650)

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

    # ═══════════════════════════════════════════════════════════
    # Tab 3: 数据表格
    # ═══════════════════════════════════════════════════════════
    with tab3:
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
