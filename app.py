"""
app.py - 麦当劳内容排行榜
"""
import html as _html
import streamlit as st
import pandas as pd
from datetime import timedelta

from config import MCD_RED, MCD_GOLD, MCD_BG, OWNER_COL, API_PROVIDERS, PAGE_SIZE, DEFAULT_API_KEY, DEFAULT_W_REACH, DEFAULT_W_CTR, DEFAULT_W_GC
from styles import get_css
from data_cleaning import clean_raw_csv, read_cleaned_csv, clean_raw_xlsx, read_cleaned_xlsx
from scoring import compute_derived_metrics, compute_full_scores, compute_filtered_scores
from llm_service import analyze_content

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
  <h1>内容排行榜</h1>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 文件上传 + 清洗模式选择
# ═══════════════════════════════════════════════════════════════

if "ds_expanded" not in st.session_state:
    st.session_state.ds_expanded = True

# 优先从 session_state 恢复已处理的数据（避免页面 reload 后丢失）
df = st.session_state.get("processed_df")
date_col = "发送日期"

with st.expander("数据源", expanded=st.session_state.ds_expanded):
    col_left, col_right = st.columns([1, 1])
    with col_left:
        mode = st.radio(
            "数据类型",
            ["原始数据（含 JSON 列，需清洗）", "已清洗数据（直接使用）"],
            horizontal=True,
            help="原始数据：上传含 JSON 消息列的文件；已清洗数据：上传已完成解析的文件"
        )
    with col_right:
        uploaded = st.file_uploader(
            "上传文件",
            type=["csv", "xlsx"],
            help="CSV 支持 UTF-8/GBK 编码；XLSX 完整保留 emoji"
        )

# 只在首次上传或文件变化时触发气球
if uploaded is not None:
    current_file_id = uploaded.file_id
    if st.session_state.get("last_file_id") != current_file_id:
        st.session_state.last_file_id = current_file_id
        st.session_state.ds_expanded = False
        st.balloons()

    is_xlsx = uploaded.name.lower().endswith('.xlsx')

    # ─── 读取数据 ───────────────────────────────────────────────
    if mode == "原始数据（含 JSON 列，需清洗）":
        with st.spinner("正在运行数据清洗脚本..."):
            try:
                if is_xlsx:
                    df = clean_raw_xlsx(uploaded)
                else:
                    df = clean_raw_csv(uploaded)
            except ValueError as e:
                st.error(str(e))
                st.stop()
    else:
        try:
            if is_xlsx:
                df = read_cleaned_xlsx(uploaded)
            else:
                df = read_cleaned_csv(uploaded)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"文件读取失败：{e}")
            st.stop()

    # ─── 解析日期列 ────────────────────────────────────────────
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # ─── 计算衍生指标 ─────────────────────────────────────────
    df = compute_derived_metrics(df)

    # ─── 计算全量综合评分（用于渠道均值）─────────────────────────
    df = compute_full_scores(df)

    # 存入 session_state，页面 reload 后可直接恢复
    st.session_state.processed_df = df

if df is not None:
    channel_avg_score = df.groupby("渠道")["综合评分_full"].mean().to_dict() if "渠道" in df.columns else {}

    # ─── 侧边筛选 ─────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
<div style="margin-bottom:20px; padding-bottom:14px; border-bottom:1px solid #E8E8E8;">
  <div style="font-size:14px; font-weight:700; color:{MCD_RED}; letter-spacing:-0.01em;">McDonald's</div>
</div>
""", unsafe_allow_html=True)

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
        with st.expander("权重配置", expanded=False):
            w_reach = st.slider("触达权重", 0.0, 1.0, DEFAULT_W_REACH, 0.05)
            w_ctr = st.slider("CTR权重", 0.0, 1.0, DEFAULT_W_CTR, 0.05)
            w_gc = st.slider("GC转化率权重", 0.0, 1.0, DEFAULT_W_GC, 0.05)

        # ─── 排序 ────────────────────────────────────────────────
        sort_order = st.radio("排序", ["降序", "升序"], index=0, horizontal=True)

        total_w = w_reach + w_ctr + w_gc
        if total_w == 0:
            st.warning("权重总和为 0，请调整权重")
            norm_reach, norm_ctr, norm_gc = 0, 0, 0
        else:
            norm_reach = w_reach / total_w
            norm_ctr = w_ctr / total_w
            norm_gc = w_gc / total_w

        # ─── AI API 配置 ──────────────────────────────────────────
        st.markdown("---")
        with st.expander("AI 配置", expanded=False):
            ai_provider = st.selectbox("API Provider", list(API_PROVIDERS.keys()), index=0)
            ai_model = st.selectbox("模型", API_PROVIDERS[ai_provider]["models"])
            ai_api_key = st.text_input("API Key", value=DEFAULT_API_KEY, type="password")
        if st.button("AI分析", use_container_width=True, key="ai_sidebar_btn"):
            st.session_state.ai_page_clicked = True

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
    tab1, tab_bu, tab2, tab3 = st.tabs(["卡片排行榜", "BU排行榜", "算法说明", "数据表格"])

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
            PAGE_SIZE = 10
            total_pages = max(1, (len(cards) + PAGE_SIZE - 1) // PAGE_SIZE)
            if "card_page" not in st.session_state:
                st.session_state.card_page = 1
            page = st.session_state.card_page
            page_cards = cards[(page-1)*PAGE_SIZE : page*PAGE_SIZE]

            # 合并渲染：拼成一个 HTML 字符串（CSS 内联到 iframe 内）
            _ai_results = st.session_state.get("ai_page_results", {})
            _ai_css = f"""<style>
.ai-tag-btn {{ background:#F8F7F5; color:{MCD_RED}; font-size:12px; font-weight:600; padding:3px 10px; border-radius:6px; border:none; display:inline-block; }}
.ai-tag-btn:hover {{ background:{MCD_RED}; color:#FFF; border-color:{MCD_RED}; }}
.ai-has-tip {{ position:relative; cursor:help; display:inline-block; }}
.ai-tip {{ visibility:hidden; opacity:0; position:absolute; bottom:calc(100% + 10px); left:50%; transform:translateX(-50%); background:rgba(30,30,30,0.95); color:#FFF; border-radius:10px; padding:12px 16px; font-size:12px; font-weight:400; line-height:1.8; min-width:260px; max-width:360px; box-shadow:0 4px 20px rgba(0,0,0,0.25); z-index:9999; pointer-events:none; transition:opacity 0.15s; }}
.ai-tip::after {{ content:''; position:absolute; top:100%; left:50%; transform:translateX(-50%); border:6px solid transparent; border-top-color:rgba(30,30,30,0.95); }}
.ai-has-tip:hover .ai-tip {{ visibility:visible; opacity:1; }}
</style>"""
            html_parts = []
            for _gi, row in enumerate(page_cards):
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
                if reach_raw_t <= 99:
                    penalty_coef_t, penalty_label = 0.1, "置信度低(x0.1)"
                elif reach_raw_t <= 499:
                    penalty_coef_t, penalty_label = 0.3, "置信度低(x0.3)"
                elif reach_raw_t <= 999:
                    penalty_coef_t, penalty_label = 0.5, "置信度中(x0.5)"
                elif reach_raw_t <= 4999:
                    penalty_coef_t, penalty_label = 0.8, "置信度较高(x0.8)"
                else:
                    penalty_coef_t, penalty_label = 1.0, "置信度高(x1.0)"

                reach_norm = getattr(row, '触达_norm', 0)
                ctr_score_t = getattr(row, 'CTR_score', 0)
                gc_score_t = getattr(row, 'GC_score', 0)
                base_score_t = reach_norm * norm_reach + ctr_score_t * norm_ctr + gc_score_t * norm_gc
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
                    reach_norm, norm_reach, ctr_score_t, norm_ctr, gc_score_t, norm_gc,
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

                # AI 解读标签：有结果时带 tooltip
                _card_gi = (page - 1) * PAGE_SIZE + _gi
                _card_ai = _ai_results.get(_card_gi)
                if _card_ai and "error" not in _card_ai:
                    _ai_tip = (
                        f"归因：{_card_ai.get('rank_factor','—')}\n"
                        f"亮点：{_card_ai.get('highlight','—')}\n"
                        f"短板：{_card_ai.get('weakness','—')}\n"
                        f"建议：{_card_ai.get('suggestion','—')}"
                    )
                    _ai_tip_escaped = _html.escape(_ai_tip).replace("\n", "<br>")
                    _ai_tag_html = f"""<span class="ai-tag-btn ai-has-tip">✨ AI<div class="ai-tip">{_ai_tip_escaped}</div></span>"""
                elif _card_ai and "error" in _card_ai:
                    _ai_tag_html = f"""<span class="ai-tag-btn" style="opacity:0.5;" title="{_html.escape(_card_ai['error'])}">⚠ AI失败</span>"""
                else:
                    _ai_tag_html = """<span class="ai-tag-btn">✨ AI</span>"""

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
                    {_ai_tag_html}
                  </div>
                </div>
                """)

            grid_html = _ai_css + '<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">' + "".join(html_parts) + '</div>'
            st.html(grid_html)

            # ─── 底部翻页 ───────────────────────────────────────────
            st.markdown(f"""
<style>
div[data-testid="stHorizontalBlock"]:last-of-type .stButton > button {{
  height:35px !important; min-height:35px !important; padding:0 12px !important;
  border-radius:6px !important; font-size:13px !important; font-weight:600 !important;
  border:1px solid #E0E0E0 !important; background:#fff !important; color:#333 !important;
}}
div[data-testid="stHorizontalBlock"]:last-of-type .stButton > button:hover {{ border-color:{MCD_RED} !important; color:{MCD_RED} !important; }}
div[data-testid="stHorizontalBlock"]:last-of-type [data-testid="stWidgetLabel"] {{ display:none !important; }}
div[data-testid="stHorizontalBlock"]:last-of-type .stNumberInput {{ max-width:50px !important; flex:none !important; }}
div[data-testid="stHorizontalBlock"]:last-of-type .stNumberInput input {{
  height:35px !important; min-height:35px !important; padding:0 4px !important;
  border-radius:6px !important; font-size:13px !important; text-align:center !important;
}}
</style>
""", unsafe_allow_html=True)
            _pg = st.container(horizontal=True, gap="small")
            with _pg:
                if page > 1:
                    if st.button("‹ 上一页", key="pg_prev"):
                        st.session_state.card_page = page - 1
                        st.rerun()
                st.markdown(f"<span style='font-size:12px;color:#999;white-space:nowrap;'>第 {page}/{total_pages} 页 · {len(cards)} 条</span>", unsafe_allow_html=True)
                jump_page = st.number_input("跳页", min_value=1, max_value=total_pages, value=page, step=1, label_visibility="collapsed", key="pg_jump")
                if st.button("Go", key="pg_go"):
                    if jump_page != page:
                        st.session_state.card_page = jump_page
                        st.rerun()
                if page < total_pages:
                    if st.button("下一页 ›", key="pg_next"):
                        st.session_state.card_page = page + 1
                        st.rerun()

            # ─── AI 解读本页（由侧边栏按钮触发）──────────────────
            _ai_page_start = (page - 1) * PAGE_SIZE
            _ai_page_end = min(_ai_page_start + PAGE_SIZE, len(cards))

            if st.session_state.pop("ai_page_clicked", False):
                if not ai_api_key:
                    st.warning("请先在侧边栏「AI配置」中填写 API Key")
                else:
                    _page_items = dff.iloc[_ai_page_start:_ai_page_end].to_dict("records")
                    with st.status(f"AI 正在分析第 {page} 页（{_ai_page_end - _ai_page_start} 条）...", expanded=True) as _status:
                        _results = analyze_content(ai_api_key, ai_provider, ai_model, _page_items)
                        _status.update(label="AI 分析完成", state="complete", expanded=False)
                    st.session_state.ai_page_results = {
                        _ai_page_start + i: r for i, r in enumerate(_results)
                    }
                    st.rerun()

    # ═══════════════════════════════════════════════════════════
    # Tab BU: BU 排行榜
    # ═══════════════════════════════════════════════════════════
    with tab_bu:
        if total_rows == 0:
            st.warning("当前筛选条件下无数据，请调整筛选条件")
        else:
            _bu_col = OWNER_COL
            if _bu_col not in dff.columns:
                st.warning(f"数据中缺少「{_bu_col}」列，无法生成 BU 排行榜")
            else:
                # ─── 按 BU 聚合 ─────────────────────────────────
                _bu_agg = dff.groupby(_bu_col).agg(
                    计划数量=("综合评分", "size"),
                    触达=("触达成功", "sum"),
                    点击=("点击人次", "sum"),
                    GC=("订单GC", "sum"),
                    Sales=("订单Sales", "sum"),
                    均值综合评分=("综合评分", "mean"),
                ).reset_index()

                _bu_agg["CTR"] = (_bu_agg["点击"] / _bu_agg["触达"] * 100).round(2).fillna(0)
                _bu_agg["GC转化率"] = (_bu_agg["GC"] / _bu_agg["点击"] * 100).round(2).fillna(0)

                # ─── BU 综合评分（min-max 归一化 × 权重 + 置信度惩戒）──
                def _norm(s):
                    _min, _max = s.min(), s.max()
                    return ((s - _min) / (_max - _min) * 100).round(2) if _max > _min else pd.Series(50, index=s.index)

                _bu_agg["CTR_norm"] = _norm(_bu_agg["CTR"])
                _bu_agg["触达_norm"] = ((_bu_agg["触达"] / _bu_agg["触达"].max()) ** 0.3 * 100).round(2)
                _bu_agg["GC_norm"] = _norm(_bu_agg["GC转化率"])

                _bu_base = (
                    _bu_agg["CTR_norm"] * 0.50
                    + _bu_agg["触达_norm"] * 0.25
                    + _bu_agg["GC_norm"] * 0.25
                ).round(2)

                # 置信度惩戒（与卡片排行榜一致）
                _bu_penalty = pd.cut(
                    _bu_agg["触达"].fillna(0),
                    bins=[-1, 99, 499, 999, 4999, float("inf")],
                    labels=[0.1, 0.3, 0.5, 0.8, 1.0],
                ).astype(float)
                _bu_agg["BU综合评分"] = (_bu_base * _bu_penalty).round(2)

                _bu_agg = _bu_agg.sort_values("BU综合评分", ascending=False).reset_index(drop=True)
                _bu_agg["排名"] = _bu_agg.index + 1

                # ─── 卡片渲染 ─────────────────────────────────────
                bu_html_parts = []
                for row in _bu_agg.itertuples():
                    rank = row.排名
                    badge_class = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(rank, "rank-other")
                    score = row.BU综合评分
                    if score >= 75:
                        score_color = "#00A04A"
                    elif score >= 40:
                        score_color = "#C79200"
                    else:
                        score_color = "#DA291C"

                    bu_name = str(getattr(row, _bu_col, '') or '')
                    plan_cnt = int(getattr(row, '计划数量', 0) or 0)
                    reach = int(getattr(row, '触达', 0) or 0)
                    clicks = int(getattr(row, '点击', 0) or 0)
                    ctr_val = float(getattr(row, 'CTR', 0) or 0)
                    gc_val = int(getattr(row, 'GC', 0) or 0)
                    sales_val = float(getattr(row, 'Sales', 0) or 0)
                    gc_rate = float(getattr(row, 'GC转化率', 0) or 0)
                    wavg = float(getattr(row, '均值综合评分', 0) or 0)

                    # 归一化值 + 置信度惩戒（用于 tooltip）
                    _ctr_norm = float(getattr(row, 'CTR_norm', 0) or 0)
                    _reach_norm = float(getattr(row, '触达_norm', 0) or 0)
                    _gc_norm = float(getattr(row, 'GC_norm', 0) or 0)
                    _base = _ctr_norm * 0.50 + _reach_norm * 0.25 + _gc_norm * 0.25
                    if reach <= 99:
                        _penalty_coef, _penalty_label = 0.1, "置信度低(x0.1)"
                    elif reach <= 499:
                        _penalty_coef, _penalty_label = 0.3, "置信度低(x0.3)"
                    elif reach <= 999:
                        _penalty_coef, _penalty_label = 0.5, "置信度中(x0.5)"
                    elif reach <= 4999:
                        _penalty_coef, _penalty_label = 0.8, "置信度较高(x0.8)"
                    else:
                        _penalty_coef, _penalty_label = 1.0, "置信度高(x1.0)"
                    _bu_tooltip = (
                        f"CTR {ctr_val:.2f}% → {_ctr_norm:.1f} × 0.50 = {(_ctr_norm * 0.50):.1f}\n"
                        f"触达 {reach:,} → {_reach_norm:.1f} × 0.25 = {(_reach_norm * 0.25):.1f}\n"
                        f"GC转化率 {gc_rate:.2f}% → {_gc_norm:.1f} × 0.25 = {(_gc_norm * 0.25):.1f}\n"
                        f"基础分 {_base:.1f} × {_penalty_coef} = {score:.1f}  [{_penalty_label}]\n"
                        f"内容均值 = {wavg:.1f}"
                    )
                    _bu_tooltip_escaped = _html.escape(_bu_tooltip).replace("\n", "<br>")

                    bu_html_parts.append(f"""
                    <div class="content-card">
                      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div style="flex:1;">
                          <div style="display:flex; align-items:center; gap:8px;">
                            <span class="rank-badge {badge_class}">{rank}</span>
                            <div>
                              <div style="font-size:14px; font-weight:600; color:#141413;">{bu_name}</div>
                              <div style="font-size:12px; color:#6b6a64;">{plan_cnt} 个计划</div>
                            </div>
                          </div>
                        </div>
                        <div>
                          <div style="display:flex;align-items:flex-start;justify-content:flex-end;gap:0;">
                            <div class="card-score" style="color:{score_color};">{score:.1f}</div>
                            <div class="score-info-wrap">
                              <span class="info-icon">i</span>
                              <div class="score-tooltip">{_bu_tooltip_escaped}</div>
                            </div>
                          </div>
                          <div class="card-score-label">均值 {wavg:.1f}</div>
                        </div>
                      </div>
                      <div class="card-meta" style="margin-top:14px;">
                        <span>触达 {reach:,}</span>
                        <span>点击 {clicks:,}</span>
                        <span>CTR {ctr_val:.2f}%</span>
                        <span>GC {gc_val:,}</span>
                        <span>Sales {int(sales_val):,}</span>
                        <span>GC转化率 {gc_rate:.2f}%</span>
                      </div>
                    </div>
                    """)

                bu_grid = '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px;">' + "".join(bu_html_parts) + '</div>'
                st.html(bu_grid)

    # ═══════════════════════════════════════════════════════════
    # Tab 2: 算法说明
    # ═══════════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-title">综合评分算法说明</div>', unsafe_allow_html=True)
        dot_src = r"""
digraph G {
    rankdir=TB;
    graph [fontname="Microsoft YaHei,PingFang SC,sans-serif", bgcolor="transparent", pad="0.2"];
    node  [fontname="Microsoft YaHei,PingFang SC,sans-serif", fontsize=11, style=filled, fillcolor="#F8F8F8", color="#CCCCCC", shape=box, penwidth=1.2, margin="0.15,0.08"];
    edge  [fontname="Microsoft YaHei,PingFang SC,sans-serif", fontsize=9, color="#999999"];

    A  [label="原始数据", fillcolor="#F0F0F0", color="#AAAAAA"];
    B  [label="计算衍生指标"];
    C  [label="CTR分\nCTR_score"];
    D  [label="GC分\nGC_score"];
    G  [label="触达分 =\n(触达/最大触达)^0.3 × 100"];
    E1 [label="CTR < 渠道Q3?", shape=diamond, fillcolor="#FFF8F0", color="#FFC000"];
    E2 [label="100 × (CTR/Q3)^1.5"];
    E3 [label="100 饱和"];
    F1 [label="GC率 < 渠道Q3?", shape=diamond, fillcolor="#FFF8F0", color="#FFC000"];
    F2 [label="100 × (GC率/Q3)^1.5"];
    F3 [label="100 饱和"];
    H  [label="加权求和", fillcolor="#FFC000", color="#E0A800", fontcolor="#000000"];
    I  [label="base =\n触达×0.25 + CTR×0.5 + GC×0.25", fillcolor="#FFC000", color="#E0A800", fontcolor="#000000"];
    J  [label="置信度惩戒"];
    J1 [label="触达量", shape=diamond, fillcolor="#FFF8F0", color="#FFC000"];
    J2 [label="× 0.1"];
    J3 [label="× 0.3"];
    J4 [label="× 0.5"];
    J5 [label="× 0.8"];
    J6 [label="× 1.0"];
    K  [label="综合评分", fillcolor="#DA291C", color="#B82015", fontcolor="#FFFFFF", penwidth=2];

    A -> B;
    A -> G;
    B -> C;
    B -> D;
    C -> E1;
    D -> F1;
    E1 -> E2 [label="是"];
    E1 -> E3 [label="否"];
    F1 -> F2 [label="是"];
    F1 -> F3 [label="否"];
    E2 -> H;
    E3 -> H;
    F2 -> H;
    F3 -> H;
    G  -> H;
    H  -> I;
    I  -> J;
    J  -> J1;
    J1 -> J2 [label="< 100"];
    J1 -> J3 [label="100~499"];
    J1 -> J4 [label="500~999"];
    J1 -> J5 [label="1000~4999"];
    J1 -> J6 [label=">=5000"];
    J2 -> K;
    J3 -> K;
    J4 -> K;
    J5 -> K;
    J6 -> K;
}
"""
        st.graphviz_chart(dot_src, use_container_width=True)

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
