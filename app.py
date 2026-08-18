"""
app.py - 麦当劳内容排行榜
"""
from pathlib import Path
import html as _html
import streamlit as st
import pandas as pd
from datetime import timedelta

from config import MCD_RED, MCD_GOLD, OWNER_COL, API_PROVIDERS, PAGE_SIZE, DEFAULT_W_REACH, DEFAULT_W_CTR, DEFAULT_W_GC, CTR_THRESHOLDS, CVR_THRESHOLDS, THEMES
from styles import get_css
from data_cleaning import clean_raw_csv, read_cleaned_csv, clean_raw_xlsx, read_cleaned_xlsx, _parse_date_column, DATE_COL
from scoring import compute_derived_metrics, compute_full_scores, compute_filtered_scores, safe_pct_rate, piecewise_score_vec, aggregate_by_content, compute_bu_scores, detect_anomalies, top_n_overall, compute_channel_baseline, PENALTY_BINS, PENALTY_LABELS, _plan_count_metric
from llm_service import analyze_content


def filter_by_plan_id(_df, query):
    """按 Plan ID 筛选（侧边栏输入框）。

    输入格式：多个 ID 用空格/逗号/中文逗号分隔，全部子串匹配。
    粘贴完整 ID（如 P202606300004）可精确定位；只输片段（如 P2026063）
    会模糊匹配 —— 但数据中 Plan ID 有两种前缀（P2: 95 个, NP: 149 个），
    片段可能同时命中两种，见侧边栏 help 文案。

    业务位置：必须在 aggregate_by_content 之前调用。否则聚合后只看得见
    content 级的行，搜 ID 反而不直观。
    """
    if not query or "plan_id" not in _df.columns:
        return _df
    pids = [p for p in query.lower().replace(",", " ").replace("，", " ").split() if p]
    if not pids:
        return _df
    s = _df["plan_id"].astype(str).str.lower()
    mask = pd.Series(False, index=_df.index)
    for p in pids:
        mask |= s.str.contains(p, na=False, regex=False)
    return _df[mask]


def _build_fingerprint(date_range, mode, sort_order, selected_plan, selected_channel,
                       selected_owner, keyword, plan_id_query, norm_reach, norm_ctr, norm_gc):
    """AI 缓存指纹：文件/筛选/排序/权重 任一变化即清空，避免位置索引张冠李戴。

    同一指纹被「AI 总结」与「卡片 AI 解读」两处共用 —— 集中在一处避免两份
    tuple 漂移（之前 diff 已经加过 plan_id_query 这种字段，两边忘改任一就会
    触发跨场景缓存错位）。
    """
    return (
        st.session_state.get("last_file_id"), mode, sort_order,
        selected_plan, selected_channel, selected_owner, keyword, plan_id_query,
        tuple(date_range) if isinstance(date_range, list) else date_range,
        round(norm_reach, 4), round(norm_ctr, 4), round(norm_gc, 4),
    )


def _build_channel_summary_table(channel_baseline, dff):
    """构造渠道汇总表（v5：3 模块静态表）

    列：渠道｜计划数｜触达成功｜点击人次｜CTR｜CTR基期均值｜CTR上四分位
    排序：全部 → APP Push → 企微1v1 → 短信 → 其他渠道
    列值都是数字（None 表示无基期数据）；渲染时 st.dataframe 用 column_config 加 % + 右对齐

    channel_baseline：scoring.compute_channel_baseline(df) 输出
                     index=渠道，columns=[CTR均值, CTR P75]
                     None / 空 时基期两列填 None
    dff：当前周期已聚合的 DataFrame（aggregate_by_content 之后）
    """
    from llm_service import aggregate_channel_stats, CHANNEL_DISPLAY_ORDER

    stats = aggregate_channel_stats(dff)
    if stats.empty:
        return pd.DataFrame()

    # 全部行：全渠道汇总
    total_reach = int(stats["触达"].sum())
    total_click = int(stats["点击"].sum())
    total_plans = int(stats["计划数量"].sum())
    total_ctr = (total_click / total_reach * 100) if total_reach > 0 else 0.0

    def _baseline_for(ch):
        if channel_baseline is None or channel_baseline.empty or ch not in channel_baseline.index:
            return None, None
        return round(float(channel_baseline.loc[ch, "CTR均值"]), 2), round(float(channel_baseline.loc[ch, "CTR P75"]), 2)

    rows = [{
        "渠道": "全部",
        "计划数": total_plans,
        "触达成功": total_reach,
        "点击人次": total_click,
        "CTR": round(total_ctr, 2),
        "CTR基期均值": _baseline_for("全部")[0],
        "CTR上四分位": _baseline_for("全部")[1],
    }]

    ordered_rows = []
    other_rows = []
    for _, row in stats.iterrows():
        ch = str(row["渠道"])
        bm, bp = _baseline_for(ch)
        r = {
            "渠道": ch,
            "计划数": int(row["计划数量"]),
            "触达成功": int(row["触达"]),
            "点击人次": int(row["点击"]),
            "CTR": round(float(row["CTR"]), 2),
            "CTR基期均值": bm,
            "CTR上四分位": bp,
        }
        if ch in CHANNEL_DISPLAY_ORDER:
            ordered_rows.append(r)
        else:
            other_rows.append(r)

    rows.extend(ordered_rows)
    rows.extend(other_rows)
    return pd.DataFrame(rows)


def _split_ai_sections(text):
    """从 AI 输出提取 ## 一、整体效果 和 ## 二、数据异常 两段正文

    容错：AI 可能在前面加废话或在后面追加其他段落；用正则精确切片。
    """
    import re
    m1 = re.search(r"##\s*一、整体效果\s*\n(.+?)(?=^##\s|\Z)", text or "", re.MULTILINE | re.DOTALL)
    m2 = re.search(r"##\s*二、数据异常\s*\n(.+?)(?=^##\s|\Z)", text or "", re.MULTILINE | re.DOTALL)
    return (m1.group(1).strip() if m1 else ""), (m2.group(1).strip() if m2 else "")

st.set_page_config(
    page_title="内容排行榜",
    page_icon="static/favicon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── 注入样式 ─────────────────────────────────────────────────
st.markdown(get_css(), unsafe_allow_html=True)
# ═══════════════════════════════════════════════════════════════
# 文件上传 + 清洗模式选择
# ═══════════════════════════════════════════════════════════════

if "ds_expanded" not in st.session_state:
    st.session_state.ds_expanded = True

# 优先从 session_state 恢复已处理的数据（避免页面 reload 后丢失）
df = st.session_state.get("processed_df")
# 日期列常量统一用 data_cleaning.DATE_COL（已支持列名模糊映射）
date_col = DATE_COL

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

# 只在换文件/换模式/首次 时清洗+评分，其余 rerun 直接用缓存（避免每次交互全量重算）
if uploaded is not None:
    current_file_id = uploaded.file_id
    _cache_valid = (
        "processed_df" in st.session_state
        and st.session_state.get("last_file_id") == current_file_id
        and st.session_state.get("last_mode") == mode
    )

    if not _cache_valid:
        # 换文件：弹气球 + 清缓存 + rerun（清洗放到 rerun 后，与原行为一致）
        if st.session_state.get("last_file_id") != current_file_id:
            st.session_state.last_file_id = current_file_id
            st.session_state.pop("processed_df", None)
            st.session_state.ds_expanded = False
            st.balloons()
            st.rerun()

        is_xlsx = uploaded.name.lower().endswith('.xlsx')

        # ─── 读取数据 ───────────────────────────────────────────────
        if mode == "原始数据（含 JSON 列，需清洗）":
            import base64
            _gif_b64 = base64.b64encode((Path(__file__).parent / "static" / "loading.gif").read_bytes()).decode()
            _loading = st.empty()
            _loading.markdown(f'<div style="text-align:center;padding:24px 0;"><img src="data:image/gif;base64,{_gif_b64}" width="200" /></div>', unsafe_allow_html=True)
            try:
                if is_xlsx:
                    df = clean_raw_xlsx(uploaded)
                else:
                    df = clean_raw_csv(uploaded)
            except ValueError as e:
                _loading.empty()
                st.error(str(e))
                st.stop()
            _loading.empty()
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

        # ─── 解析日期列（4 个 load 函数内已做智能解析；此处保留兜底，处理未来新增路径）──
        if date_col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            df[date_col] = _parse_date_column(df[date_col])

        # ─── 计算衍生指标 ─────────────────────────────────────────
        df = compute_derived_metrics(df)

        # ─── 计算全量综合评分（用于渠道均值）─────────────────────────
        df = compute_full_scores(df)

        # 清洗成功后才更新指纹 + 缓存（失败时 last_mode 不变，便于重试）
        st.session_state.last_mode = mode
        st.session_state.processed_df = df

if df is not None:
    # 渠道均值在「筛选后聚合后」按当前窗口重算（见下方），不在此处缓存
    channel_avg_score = {}

    # ─── 侧边筛选 ─────────────────────────────────────────────
    with st.sidebar:
        import base64
        _svg_b64 = base64.b64encode((Path(__file__).parent / "static" / "mcdonalds.svg").read_bytes()).decode()
        st.markdown(f'<div style="text-align:center;padding:12px 0 16px 0;"><img src="data:image/svg+xml;base64,{_svg_b64}" width="120" /></div><hr style="margin:0 0 24px 0; border:none; border-top:1px solid #E8E8E8;">', unsafe_allow_html=True)

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
            # 只点了开始日期时 Streamlit 会先 rerun 一次，此时 date_range 只有 1 个元素，
            # 若不处理会退化成「不筛选」而突然显示全量数据。补成「起点 ~ 数据最新日」，
            # 让起点继续生效，并在 UI 上提示当前统计窗口
            if isinstance(date_range, (list, tuple)) and len(date_range) == 1:
                st.caption(f"未选结束日期，暂按 {date_range[0]:%m-%d} 至 {max_dt:%m-%d} 统计")
        else:
            min_dt = max_dt = None
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
            w_gc = st.slider("下单转化率权重", 0.0, 1.0, DEFAULT_W_GC, 0.05)

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
            def _on_provider_change():
                # 仅新 provider 有预填 key 时才覆盖，避免用户已输入的 key 被清空
                _new_default = API_PROVIDERS[st.session_state["ai_provider"]].get("api_key", "")
                if _new_default:
                    st.session_state["ai_api_key"] = _new_default

            ai_provider = st.selectbox(
                "API Provider", list(API_PROVIDERS.keys()), index=0,
                key="ai_provider", on_change=_on_provider_change,
            )
            ai_model = st.selectbox("模型", API_PROVIDERS[ai_provider]["models"])
            _default_key = API_PROVIDERS[ai_provider].get("api_key", "")
            ai_api_key = st.text_input(
                "API Key",
                value=st.session_state.get("ai_api_key", _default_key),
                type="password", key="ai_api_key",
            )
        if st.button("内容分析", use_container_width=True, key="ai_sidebar_btn"):
            st.session_state.ai_page_clicked = True

        if st.button("AI 总结", use_container_width=True, key="ai_summary_btn"):
            st.session_state.ai_summary_clicked = True

        # ─── Plan ID 搜索 ──────────────────────────────────────────
        st.markdown("---")
        plan_id_query = st.text_input(
            "Plan ID",
            "",
            placeholder="部分匹配，多个用空格分隔",
            help="粘贴完整 Plan ID 可精确定位；也支持片段模糊匹配（注意数据含 P / NP 两种前缀，片段可能同时命中）"
        )

        # ─── 配色主题 ──────────────────────────────────────────────
        st.markdown("---")
        with st.expander("配色主题", expanded=False):
            selected_theme = st.selectbox("主题", list(THEMES.keys()), index=0)

    # ─── 注入主题覆盖 CSS ───────────────────────────────────────
    _t = THEMES[selected_theme]
    st.markdown(f"""
<style>
  html, body, .stApp {{ background: {_t['bg']}; color: {_t['text']}; }}
  [data-testid="stSidebar"] {{ background: {_t['sidebar_bg']} !important; border-right: 1px solid {_t['border']}; border-top: 3px solid {_t['gold']}; }}
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] label, [data-testid="stSidebar"] p {{ color: {_t['text']} !important; }}
  [data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stTextInput label, [data-testid="stSidebar"] .stDateInput label,
  [data-testid="stSidebar"] .stSlider label {{ color: {_t['text_sub']} !important; }}
  [data-testid="stSidebar"] hr {{ border-color: {_t['border']} !important; }}
  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{ background: {_t['border']} !important; }}
  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [aria-valuenow] {{ background: {_t['accent']} !important; }}
  [data-testid="stSidebar"] .stSelectbox > div > div,
  [data-testid="stSidebar"] .stTextInput > div > div,
  [data-testid="stSidebar"] .stDateInput > div > div {{ background: {_t['sidebar_bg']} !important; border: 1px solid {_t['border']} !important; color: {_t['text']} !important; }}
  [data-testid="stSidebar"] [data-baseweb="select"] span {{ color: {_t['text']} !important; }}
  [data-testid="stSidebar"] [data-baseweb="input"] {{ color: {_t['text']} !important; }}
  div[data-testid="stMetricValue"] {{ color: {_t['text_sub']} !important; }}
  div[data-testid="stMetricLabel"] {{ color: {_t['text_muted']} !important; }}
  .stTabs [data-baseweb="tab-list"] {{ border-bottom: 1px solid {_t['border']}; }}
  .stTabs [data-baseweb="tab"] {{ color: {_t['text_muted']} !important; }}
  .stTabs [data-baseweb="tab"]:hover {{ color: {_t['text']} !important; }}
  .stTabs [aria-selected="true"] {{ color: {_t['text']} !important; border-bottom: 2px solid {_t['accent']} !important; }}
  .mcd-header {{ border-bottom: 1px solid {_t['border']}; }}
  .mcd-header h1 {{ color: {_t['accent']}; }}
  .rank-1 {{ background: {_t['gold']}33; color: {_t['gold']}; border-color: {_t['gold']}; }}
  .rank-2 {{ background: {_t['border']}; color: {_t['text_sub']}; }}
  .rank-3 {{ background: {_t['gold']}33; color: {_t['gold']}; border-color: {_t['gold']}55; }}
  .rank-other {{ background: {_t['border']}; color: {_t['text_muted']}; }}
  .content-card {{ background: {_t['card_bg']}; border: 1px solid {_t['border']}; }}
  .content-card:hover {{ border-color: {_t['text_muted']}; }}
  .card-title {{ color: {_t['text']}; }}
  .card-content {{ color: {_t['text_sub']}; }}
  .card-meta {{ color: {_t['text_sub']}; }}
  .card-meta span {{ background: {_t['bg']}; }}
  .card-score {{ color: {_t['accent']}; }}
  .card-score-label {{ color: {_t['text_muted']}; }}
  .section-title {{ color: {_t['text']}; border-bottom: 1px solid {_t['border']}; }}
  .stDataFrame thead th {{ background: {_t['bg']} !important; color: {_t['text_sub']} !important; border-bottom: 2px solid {_t['border']} !important; }}
  .stDataFrame tbody td {{ color: {_t['text']} !important; border-color: {_t['border']} !important; }}
  .stDataFrame tbody tr:hover {{ background: {_t['gold']}22 !important; }}
  .score-info-wrap .info-icon {{ background: {_t['border']}; color: {_t['text_muted']}; }}
  .score-info-wrap:hover .info-icon {{ background: {_t['accent']}; color: #FFF; }}
  .ai-card {{ background: {_t['card_bg']}; border: 1px solid {_t['border']}; border-left: 3px solid {_t['gold']}; }}
  .ai-card-title {{ color: {_t['text']}; }}
  .ai-tag {{ background: {_t['bg']}; color: {_t['text_sub']}; }}
  .ai-tag-btn {{ background: {_t['accent']}15; color: {_t['accent']}; border: 1px solid {_t['accent']}33; }}
  .ai-tag-btn:hover {{ background: {_t['accent']}; color: #FFFFFF; border-color: {_t['accent']}; }}
  .ai-has-tip:hover {{ background: {_t['accent']}; color: #FFFFFF; border-color: {_t['accent']}; }}
  .stButton > button {{ border: 1px solid {_t['border']} !important; background: {_t['card_bg']} !important; color: {_t['text']} !important; }}
  .stButton > button:hover {{ border-color: {_t['accent']} !important; color: {_t['accent']} !important; }}
  .mcd-header div {{ color: {_t['accent']}; }}
  [data-testid="stSidebar"] .stDownloadButton > button {{ background: {_t['accent']} !important; }}
</style>
""", unsafe_allow_html=True)

    # ─── 应用筛选 ─────────────────────────────────────────────
    dff = df

    if date_range is not None:
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_dt, end_dt = date_range
        elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
            # 范围选择的中间态：按「已选起点 ~ 数据最新日」统计，不退回全量
            start_dt = date_range[0]
            end_dt = max_dt if max_dt is not None else start_dt
        elif not isinstance(date_range, (list, tuple)):
            # 单日期选择：按当天过滤
            start_dt = end_dt = date_range
        else:
            start_dt = end_dt = None
        if start_dt is not None and pd.notna(start_dt) and pd.notna(end_dt):
            # 右开区间：+1天再取 < ，既能覆盖 end 当天的时分秒，又不会把次日 00:00 算进来
            dff = dff[
                (dff[date_col] >= pd.to_datetime(start_dt)) &
                (dff[date_col] < pd.to_datetime(end_dt) + timedelta(days=1))
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
            mask |= dff[title_candidates[0]].astype(str).str.lower().str.contains(kw, na=False, regex=False)
        if "内容" in dff.columns:
            mask |= dff["内容"].astype(str).str.lower().str.contains(kw, na=False, regex=False)
        dff = dff[mask]

    dff = filter_by_plan_id(dff, plan_id_query)

    # ─── 内容级聚合：一张卡 = 一个 Plan × 一条文案 ──────────────
    # 必须在筛选之后：日期筛选决定统计窗口（窗口决定展示哪些卡片）
    # 但 2026-08-18 起指标已固定化（per-channel Q3 阈值），窗口变化不再影响分数
    # 业务语义见 scoring.py 顶部「内容级聚合」注释
    dff = aggregate_by_content(dff)
    # 聚合后重算 CTR / 下单转化 / 触达分数（先求和再算率）
    dff = compute_derived_metrics(dff)

    # ─── 计算筛选后的综合评分 ──────────────────────────────────
    dff = compute_filtered_scores(dff, norm_reach, norm_ctr, norm_gc)

    # 渠道均值必须与卡片同粒度：用聚合后的当前窗口重算，否则和卡片分数不可比
    channel_avg_score = (
        dff.groupby("渠道")["综合评分"].mean().to_dict()
        if "渠道" in dff.columns and len(dff) else {}
    )

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

    # ─── AI 总结分析 ────────────────────────────────────────────
    _summary_fp = _build_fingerprint(
        date_range, mode, sort_order,
        selected_plan, selected_channel, selected_owner, keyword, plan_id_query,
        norm_reach, norm_ctr, norm_gc,
    )

    # 共享准备：当前 period / 渠道基期（全量上传数据按日聚合）/ Top 3 / 异常 / 渠道汇总表
    current_period = None
    if date_range is not None and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        _s, _e = date_range
        if pd.notna(_s) and pd.notna(_e):
            current_period = (_s, _e)
    channel_baseline = compute_channel_baseline(df)
    top3_df = top_n_overall(dff)
    anomalies_df = detect_anomalies(dff)
    _channel_table = _build_channel_summary_table(channel_baseline, dff)

    # 数字列配置：百分比列加 % 后缀、整数列加千分位；都右对齐
    _pct_cols = st.column_config.NumberColumn(format="%.2f%%", alignment="right")
    _int_cols = st.column_config.NumberColumn(format="%,.0f", alignment="right")

    def _render_ai_summary(ai_summary_text):
        """渲染 3 模块：整体效果 / 数据异常 / Top 3（v5）"""
        overall, anomaly = _split_ai_sections(ai_summary_text)
        st.markdown("## 一、整体效果")
        st.markdown(overall if overall else "（暂无）")
        st.dataframe(
            _channel_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "计划数": _int_cols,
                "触达成功": _int_cols,
                "点击人次": _int_cols,
                "CTR": _pct_cols,
                "CTR基期均值": _pct_cols,
                "CTR上四分位": _pct_cols,
            },
        )

        st.markdown("## 二、数据异常")
        st.markdown(anomaly if anomaly else "（暂无）")
        if not anomalies_df.empty:
            st.dataframe(anomalies_df, use_container_width=True, hide_index=True)

        st.markdown("## 三、Top 3 内容（综合评分 ≥ 80）")
        if top3_df.empty:
            st.caption("（无评分 ≥ 80 的内容）")
        else:
            _top3_disp = top3_df.rename(columns={
                "plan_id": "Plan ID",
                "订单Sales": "Sales",
                "内容": "正文",
            })
            _show_cols = [c for c in ["渠道", "Plan ID", "标题", "正文", "CTR", "Sales"] if c in _top3_disp.columns]
            st.dataframe(
                _top3_disp[_show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "CTR": _pct_cols,
                    "Sales": _int_cols,
                },
            )

    if st.session_state.pop("ai_summary_clicked", False):
        if not ai_api_key:
            st.warning("请先在侧边栏「AI配置」中填写 API Key")
        else:
            from llm_service import aggregate_channel_stats, analyze_summary
            channel_stats = aggregate_channel_stats(dff)

            with st.expander("AI 总结分析", expanded=False):
                with st.spinner("AI 正在分析..."):
                    summary_result = analyze_summary(
                        ai_api_key, ai_provider, ai_model,
                        channel_stats,
                        current_period,
                        channel_baseline, anomalies_df,
                    )
                st.session_state.ai_summary_result = summary_result
                st.session_state.ai_summary_fp = _summary_fp
                # 缓存 Top 3 用于重渲染（空表也缓存，让 UI 决定渲染与否）
                st.session_state.ai_summary_top_df = top3_df.copy() if not top3_df.empty else pd.DataFrame()
                _render_ai_summary(summary_result)
    else:
        _cached = st.session_state.get("ai_summary_result")
        if _cached is not None and st.session_state.get("ai_summary_fp") == _summary_fp:
            with st.expander("AI 总结分析", expanded=False):
                _render_ai_summary(_cached)

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
            total_pages = max(1, (len(cards) + PAGE_SIZE - 1) // PAGE_SIZE)
            if "card_page" not in st.session_state:
                st.session_state.card_page = 1
            page = st.session_state.card_page
            page_cards = cards[(page-1)*PAGE_SIZE : page*PAGE_SIZE]

            # AI 结果缓存指纹：文件/筛选/排序/权重 任一变化即清空，避免位置索引张冠李戴
            _ai_fp = _build_fingerprint(
                date_range, mode, sort_order,
                selected_plan, selected_channel, selected_owner, keyword, plan_id_query,
                norm_reach, norm_ctr, norm_gc,
            )
            if st.session_state.get("ai_results_fp") != _ai_fp:
                st.session_state.ai_page_results = {}
                st.session_state.ai_results_fp = _ai_fp

            # 合并渲染：拼成一个 HTML 字符串（AI 标签/tooltip 样式由 styles.py 统一管理）
            _ai_results = st.session_state.get("ai_page_results", {})
            html_parts = []
            for _gi, row in enumerate(page_cards):
                rank = row.排名
                badge_class = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(rank, "rank-other")

                score = row.综合评分
                if score >= 60:
                    score_color = _t["score_high"]
                else:
                    score_color = _t["score_low"]

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

                reach_score = getattr(row, '触达_score', 0)
                ctr_score_t = getattr(row, 'CTR_score', 0)
                gc_score_t = getattr(row, 'cvr_score', 0)
                base_score_t = round(reach_score * norm_reach + ctr_score_t * norm_ctr + gc_score_t * norm_gc, 2)
                impact_parts = []
                if reach_score < 33:
                    impact_parts.append("触达偏低({:.1f})".format(reach_score))
                elif reach_score > 67:
                    impact_parts.append("触达偏高({:.1f})".format(reach_score))
                if ctr_score_t < 33:
                    impact_parts.append("CTR偏低({:.1f})".format(ctr_score_t))
                elif ctr_score_t > 67:
                    impact_parts.append("CTR偏高({:.1f})".format(ctr_score_t))
                if gc_score_t < 33:
                    impact_parts.append("下单转化率偏低({:.1f})".format(gc_score_t))
                elif gc_score_t > 67:
                    impact_parts.append("下单转化率偏高({:.1f})".format(gc_score_t))
                impact = " / ".join(impact_parts) if impact_parts else "各项均衡"
                formula = "({:.1f}x{:.2f} + {:.1f}x{:.2f} + {:.1f}x{:.2f}) x {:.1f} = {:.2f}  [{}]".format(
                    reach_score, norm_reach, ctr_score_t, norm_ctr, gc_score_t, norm_gc,
                    penalty_coef_t, score, penalty_label
                )
                tooltip_text = _html.escape(impact + chr(10) + formula)

                date_val = getattr(row, '发送日期', None)
                date_str = str(date_val)[:10] if date_val is not None and not (isinstance(date_val, float) and date_val != date_val) else ""
                # 卡片日期 = 内容实际投放日，不是侧边栏选的筛选范围
                # 单日投放：显示 2026-07-06
                # 跨天投放：显示 07-01~07-26 · 26天（聚合后起始日期~结束日期）
                _days = int(getattr(row, '天数', 1) or 1)
                if _days > 1:
                    _end_val = getattr(row, '结束日期', None)
                    _end_str = str(_end_val)[:10] if _end_val is not None else ""
                    if _end_str and _end_str != date_str:
                        date_str = f"{date_str[5:]}~{_end_str[5:]} · {_days}天"
                _unit_cnt = int(getattr(row, 'Unit数', 0) or 0)
                channel_short = str(getattr(row, '渠道', '') or '')
                owner_short = str(getattr(row, OWNER_COL, '') or '') if hasattr(row, OWNER_COL) else ''
                plan_type_short = str(getattr(row, '计划类型', '') or '')
                plan_id_short = str(getattr(row, 'plan_id', '') or '') if hasattr(row, 'plan_id') else ''
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
                try: cvr_rate = float(getattr(row, '下单转化', 0))
                except: cvr_rate = 0.0

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
                      <span style="font-size:12px; color:#888; background:#F5F5F5; padding:2px 8px; border-radius:12px;">{_html.escape(channel_short)}</span>
                      <span style="font-size:12px; color:#AAA;"> · {_html.escape(owner_short)} · {_html.escape(plan_type_short)} · {_html.escape(date_str)}</span>
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
                  <div class="card-title">{_html.escape(title[:80])}{'...' if len(title) > 80 else ''}</div>
                  <div class="card-content">{_html.escape(content[:200])}{'...' if len(content) > 200 else ''}</div>
                  <div class="card-meta">
                    <span>触达 {reach:,}</span>
                    <span>点击 {clicks_val:,}</span>
                    <span>CTR {ctr_val:.2f}%</span>
                    <span>GC {gc_val:,}</span>
                    <span>Sales {int(sales_val):,}</span>
                    <span>下单转化率 {cvr_rate:.2f}%</span>
                    {f'<span style="color:{_t["text_muted"]};">{_unit_cnt} Unit</span>' if _unit_cnt > 1 else ''}
                    {f'<span style="color:{_t["text_muted"]};">{_html.escape(plan_id_short)}</span>' if plan_id_short else ''}
                    {_ai_tag_html}
                  </div>
                </div>
                """)

            grid_html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">' + "".join(html_parts) + '</div>'
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
                    # 用 update 合并而非覆盖：分析新页时保留其它页结果，翻回去不丢
                    _prev_ai = st.session_state.get("ai_page_results", {})
                    _prev_ai.update({_ai_page_start + i: r for i, r in enumerate(_results)})
                    st.session_state.ai_page_results = _prev_ai
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
                    计划数量=_plan_count_metric(dff),
                    触达=("触达成功", "sum"),
                    点击=("点击人次", "sum"),
                    点击后下单=("点击后下单人次", "sum"),
                    GC=("订单GC", "sum"),
                    Sales=("订单Sales", "sum"),
                    均值综合评分=("综合评分", "mean"),
                ).reset_index()

                _bu_agg["CTR"] = safe_pct_rate(_bu_agg["点击"], _bu_agg["触达"])
                _bu_agg["下单转化"] = safe_pct_rate(_bu_agg["点击后下单"], _bu_agg["点击"])

                # ─── BU 综合评分：与内容榜使用同一组归一权重 ───────
                _bu_agg = compute_bu_scores(
                    _bu_agg, norm_reach=norm_reach, norm_ctr=norm_ctr, norm_gc=norm_gc
                )

                # ─── 卡片渲染 ─────────────────────────────────────
                bu_html_parts = []
                for row in _bu_agg.itertuples():
                    rank = row.排名
                    badge_class = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(rank, "rank-other")
                    score = row.BU综合评分
                    if score >= 70:
                        score_color = _t["score_high"]
                    elif score >= 40:
                        score_color = _t["score_med"]
                    else:
                        score_color = _t["score_low"]

                    bu_name = str(getattr(row, _bu_col, '') or '')
                    plan_cnt = int(getattr(row, '计划数量', 0) or 0)
                    reach = int(getattr(row, '触达', 0) or 0)
                    clicks = int(getattr(row, '点击', 0) or 0)
                    ctr_val = float(getattr(row, 'CTR', 0) or 0)
                    gc_val = int(getattr(row, 'GC', 0) or 0)
                    sales_val = float(getattr(row, 'Sales', 0) or 0)
                    cvr_rate = float(getattr(row, '下单转化', 0) or 0)
                    wavg = float(getattr(row, '均值综合评分', 0) or 0)

                    # 归一化值 + 置信度惩戒（用于 tooltip）
                    _ctr_norm = float(getattr(row, 'CTR_norm', 0) or 0)
                    _reach_norm = float(getattr(row, '触达_norm', 0) or 0)
                    _cvr_norm = float(getattr(row, '下单转化_norm', 0) or 0)
                    _base = _ctr_norm * norm_ctr + _reach_norm * norm_reach + _cvr_norm * norm_gc
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
                        f"CTR {ctr_val:.2f}% → {_ctr_norm:.1f} × {norm_ctr:.2f} = {(_ctr_norm * norm_ctr):.1f}\n"
                        f"触达 {reach:,} → {_reach_norm:.1f} × {norm_reach:.2f} = {(_reach_norm * norm_reach):.1f}\n"
                        f"下单转化率 {cvr_rate:.2f}% → {_cvr_norm:.1f} × {norm_gc:.2f} = {(_cvr_norm * norm_gc):.1f}\n"
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
                              <div style="font-size:14px; font-weight:600; color:#141413;">{_html.escape(bu_name)}</div>
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
                        <span>下单转化率 {cvr_rate:.2f}%</span>
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
    D  [label="下单转化分\n下单转化_score"];
    G  [label="触达分 =\n(触达/最大触达)^0.3 × 100"];
    E1 [label="CTR < 渠道Q3?", shape=diamond, fillcolor="#FFF8F0", color="#FFC000"];
    E2 [label="100 × (CTR/Q3)^1.5"];
    E3 [label="100 饱和"];
    F1 [label="下单转化率 < 渠道Q3?", shape=diamond, fillcolor="#FFF8F0", color="#FFC000"];
    F2 [label="100 × (下单转化率/Q3)^1.5"];
    F3 [label="100 饱和"];
    H  [label="加权求和", fillcolor="#FFC000", color="#E0A800", fontcolor="#000000"];
    I  [label="base =\n触达×0.25 + CTR×0.5 + 下单转化率×0.25", fillcolor="#FFC000", color="#E0A800", fontcolor="#000000"];
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
            _ctr_rows = "".join(
                f'<tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">{ch}</td><td style="padding:6px 4px; text-align:right; font-weight:600;">{v}%</td></tr>'
                if i < len(CTR_THRESHOLDS) - 1 else
                f'<tr><td style="padding:6px 4px; color:#888;">{ch}</td><td style="padding:6px 4px; text-align:right; font-weight:600;">{v}%</td></tr>'
                for i, (ch, v) in enumerate(CTR_THRESHOLDS.items())
            )
            _cvr_rows = "".join(
                f'<tr style="border-bottom:1px solid #F0F0F0;"><td style="padding:6px 4px; color:#888;">{ch}</td><td style="padding:6px 4px; text-align:right; font-weight:600;">{v}%</td></tr>'
                if i < len(CVR_THRESHOLDS) - 1 else
                f'<tr><td style="padding:6px 4px; color:#888;">{ch}</td><td style="padding:6px 4px; text-align:right; font-weight:600;">{v}%</td></tr>'
                for i, (ch, v) in enumerate(CVR_THRESHOLDS.items())
            )
            st.markdown(f"""
<div style="display:flex; gap:16px; flex-wrap:wrap; margin-top:8px;">
  <div style="flex:1; min-width:180px; background:#fff; border:1px solid #EFEFEF; border-radius:12px; padding:16px 20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
    <div style="font-size:12px; font-weight:700; color:#DA291C; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:10px;">渠道 CTR Q3 阈值</div>
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
      {_ctr_rows}
    </table>
  </div>
  <div style="flex:1; min-width:180px; background:#fff; border:1px solid #EFEFEF; border-radius:12px; padding:16px 20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
    <div style="font-size:12px; font-weight:700; color:#DA291C; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:10px;">渠道 下单转化率 Q3 阈值</div>
    <table style="width:100%; border-collapse:collapse; font-size:13px;">
      {_cvr_rows}
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
                         date_col, "天数", "Unit数", owner_c,
                         "触达成功", "点击人次", "CTR", "订单GC", "订单Sales", "下单转化", "综合评分"]
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
