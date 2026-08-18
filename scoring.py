"""
scoring.py - 麦当劳内容排行榜：评分算法
"""

import numpy as np
import pandas as pd
from config import (
    CTR_THRESHOLDS, CVR_THRESHOLDS,
    CTR_UNKNOWN_THRESHOLD, CVR_UNKNOWN_THRESHOLD, EXP,
    REACH_THRESHOLDS, REACH_UNKNOWN_THRESHOLD, REACH_EXP,
    DEFAULT_W_REACH, DEFAULT_W_CTR, DEFAULT_W_GC,
    OWNER_COL,
)
from data_cleaning import DATE_COL

OWNER_COL_DEFAULT = OWNER_COL

PENALTY_BINS = [-1, 99, 499, 999, 4999, float("inf")]
PENALTY_LABELS = [0.1, 0.3, 0.5, 0.8, 1.0]

# ═══════════════════════════════════════════════════════════════
# 数据源字段语义（2026-07 起）
#
#   旧的 SQL 输出（cnn0727 及更早）只有 15 列：
#     Plan ID → 1 条文案（一对一）
#   新的 SQL 输出（7/27 起）多 2 列，共 17 列：
#     Plan ID → Unit ID (1..N) → Message ID (文案)
#
#   新增 2 列的语义：
#     Unit ID    同一文案的「千人千面」分组
#                推送文案完全相同，点击后落地页菜单按用户喜好不同
#                业务上 = 同一次投放的批次切分，不是不同人群
#                上游约 20% 行用字符串 "[NULL]" 占位（业务上等同空值，
#                表示「这条 Plan 没有 Unit 拆分」），按 Unit 去重时忽略
#     Message ID 文案本身的唯一 ID
#                与「消息内容」字段一一对应（254 个 Message ↔ 254 种文案）
#                18 位数字，超过 float64 的 2^53 安全整数范围，必须保持字符串
#
#   数据源变更让"一个 Plan 多个 Unit 同文案"和"一个 Plan 多个 Unit 异文案"
#   两类情况并存 —— 见 README.md「列名要求」与「数据源变更历史」两节。
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 内容级聚合
#
#   一张卡片 = 一个 Plan × 一条文案（Message）
#
#   为什么合并 Unit：
#     同一文案按 Unit 拆分后投放（7/06 那条短信拆 7 个 Unit 是典型例子）。
#     若不合并：① 一条文案会按 Unit 数重复占榜（最多一天 7 个榜位）
#              ② Unit 之间的 CTR 差异来自人群/落地页，不是文案差异，
#                 会被读成"文案优劣"，污染内容排行榜的语义
#
#   为什么日期不参与聚合：
#     同一文案往往投多天（7/01~7/26 共 26 天）。每日触达/CTR 差异是真实
#     业务现象（如主投日 vs 收尾日），必须按窗口保留。
#     统计窗口由侧边栏「日期范围」控制 —— 窗口内的投放合并计算。
#
#   聚合键顺序：新数据用 (plan_id, message_id)；旧数据无 message_id，
#              退化为 (plan_id, 消息标题) —— 旧格式 1 Plan 1 文案，等价
# ═══════════════════════════════════════════════════════════════
AGG_SUM_COLS = ["预计触达", "触达成功", "点击人次", "点击后下单人次", "订单GC", "订单Sales"]
AGG_FIRST_COLS = ["计划类型", "渠道", "owner", "是否用券", "plan名称", "标题", "内容", "消息标题"]
# 上游 unit_id 用字符串 "[NULL]" 作为空值占位（业务上 = 无 Unit），
# 按 Unit 数去重时忽略。_normalize_id_columns 已把 "nan"/"None" 等转成 ""，
# 这里只需再排除 "[NULL]" 字面量和空字符串
_NULL_UNIT_TOKENS = frozenset(("[NULL]", ""))
# 内部列：预归一化后的 unit_id 副本，供 groupby 聚合直接 nunique
_UNIT_NORM_COL = "_unit_norm"


def _normalize_unit_ids(df: pd.DataFrame) -> None:
    """就地构造 _unit_norm：把 "[NULL]" 和空值统一成 NaN，其余保留字符串形式。

    一次性做完整列归一化，避免 groupby 时对每个 group 重复 astype/str.strip。
    后续 ("_unit_norm", "nunique") + dropna 默认行为即可得到真实 Unit 数。
    """
    if "unit_id" not in df.columns or _UNIT_NORM_COL in df.columns:
        return
    norm = df["unit_id"].astype(str).str.strip()
    df[_UNIT_NORM_COL] = norm.where(~norm.isin(_NULL_UNIT_TOKENS))


def _content_keys(df: pd.DataFrame) -> list:
    """确定内容级聚合键。新数据用 (Plan, Message)；
    旧数据（无 message_id）退化为 (Plan, 标题) ——
    旧格式 1 Plan 对应 1 条文案，行为与「按 Plan 聚合」等价"""
    if "plan_id" not in df.columns:
        return []
    if "message_id" in df.columns:
        return ["plan_id", "message_id"]
    for title_col in ("消息标题", "标题"):
        if title_col in df.columns:
            return ["plan_id", title_col]
    return ["plan_id"]


def _plan_count_metric(df: pd.DataFrame):
    """聚合「计划数量」时使用的指标：plan_id 存在时按唯一 ID 计数（口径与卡片一致），
    否则退回 size（兼容未走 aggregate_by_content 的旧数据路径）。

    返回 pandas groupby agg 接受的元组，供三处复用：
      - app.py BU 排行榜
      - llm_service.aggregate_channel_stats
      - llm_service.aggregate_bu_stats
    """
    return ("plan_id", "nunique") if "plan_id" in df.columns else ("综合评分", "size")


def aggregate_by_content(df: pd.DataFrame, date_col: str = DATE_COL) -> pd.DataFrame:
    """按「Plan × 文案」聚合成内容级卡片。

    业务定义见文件顶部「内容级聚合」注释。指标先求和再算率：CTR 必须是
    sum(点击)/sum(触达)，不能对各行 CTR 取平均，否则小触达行会被赋予与
    大触达行相同的权重。

    聚合后新增/保留的字段：
        Unit数       真实 Unit 数（已排除 [NULL] 占位），用于卡片显示「N Unit」
        天数         当前筛选窗口内该文案覆盖的天数，用于卡片显示「07-01~07-26 · 26天」
        起始日期/结束日期  天数 > 1 时展示日期区间，单日投放时只显示发送日期
        发送日期       等于起始日期（保留旧字段名，下游卡片/表格取数逻辑不用改）
    """
    keys = _content_keys(df)
    if not keys or df.empty:
        return df

    _normalize_unit_ids(df)

    agg_map = {}
    for c in AGG_SUM_COLS:
        if c in df.columns:
            agg_map[c] = (c, "sum")
    for c in AGG_FIRST_COLS:
        if c in df.columns and c not in keys:
            agg_map[c] = (c, "first")
    if _UNIT_NORM_COL in df.columns:
        # 用预归一化列 + nunique + dropna 默认行为，向量化一次完成
        agg_map["Unit数"] = (_UNIT_NORM_COL, "nunique")
    if date_col in df.columns:
        agg_map["天数"] = (date_col, "nunique")
        agg_map["起始日期"] = (date_col, "min")
        agg_map["结束日期"] = (date_col, "max")

    out = df.groupby(keys, dropna=False, as_index=False).agg(**agg_map)

    # 保留 发送日期 列名（卡片/表格/AI 既有取数逻辑不用改），用起始日期作单日投放日期
    if "起始日期" in out.columns:
        out[date_col] = out["起始日期"]
        out = out.drop(columns=["起始日期"])  # 内部聚合产物，不再保留
    if "Unit数" not in out.columns:
        out["Unit数"] = 0
    if "天数" not in out.columns:
        out["天数"] = 1
    # 清理内部辅助列，避免污染下游
    if _UNIT_NORM_COL in out.columns:
        out = out.drop(columns=[_UNIT_NORM_COL])
    return out



def piecewise_score_vec(G_col, threshold_col, exp=None):
    """向量化版本：整列一次计算，比 apply 快 100 倍

    exp: 幂次。默认 None 走全局 EXP=1.5（CTR/CVR 用，先慢后快）。
         触达场景传 0.5（先快后慢，边际效用递减）。
    """
    _exp = exp if exp is not None else EXP
    ratio = G_col / threshold_col
    return np.where(ratio >= 1, 100.0, 100.0 * ratio ** _exp)


def safe_pct_rate(num, denom):
    """聚合安全百分比：sum(分子) / sum(分母) × 100，处理 0/0 情况"""
    return (num / denom * 100).replace([float("inf"), -float("inf")], 0).round(2).fillna(0)


def compute_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """计算 CTR、下单转化、触达分数（per-channel Q3, EXP=0.5）

    触达分数 = piecewise(reach, REACH_THRESHOLDS[渠道], exp=0.5)
    2026-08-18 之前用"窗口内 max"做 max-min 归一化，导致日期筛选改变窗口 max
    时分数跟着变。改为 per-channel 固定 Q3 阈值后，分数完全独立于日期筛选。
    """
    df["CTR"] = (df["点击人次"] / df["触达成功"] * 100).round(2)
    df["CTR"] = df["CTR"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # 缺"点击后下单人次"列时按 0 处理（旧 CSV 容错）；df.get 返回 0 标量 → 全 0 Series
    df["下单转化"] = (df.get("点击后下单人次", 0) / df["点击人次"] * 100).round(2)
    df["下单转化"] = df["下单转化"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # 触达_score: per-channel 固定 Q3, EXP=0.5 (√x, 先快后慢)
    # 分母是 config 里的固定阈值（不再用窗口 max），所以日期筛选不影响分数
    # 缺 "渠道" 列时按 UNKNOWN 阈值兜底（旧 CSV 容错）
    if "渠道" in df.columns:
        _reach_thresh = df["渠道"].astype(str).map(REACH_THRESHOLDS).fillna(REACH_UNKNOWN_THRESHOLD)
    else:
        _reach_thresh = pd.Series(REACH_UNKNOWN_THRESHOLD, index=df.index)
    df["触达_score"] = piecewise_score_vec(df["触达成功"], _reach_thresh, exp=REACH_EXP)
    return df


def compute_full_scores(df: pd.DataFrame) -> pd.DataFrame:
    """计算全量数据的综合评分（用于渠道均值，不受筛选影响）

    注：2026-08-18 之前用 触达_norm（窗口内 max 归一化），存在窗口联动问题。
    现改用 触达_score（per-channel 固定 Q3），与 compute_filtered_scores 口径一致。
    """
    _ctr_thresh = df["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    df["CTR_score_full"] = piecewise_score_vec(df["CTR"], _ctr_thresh)

    _cvr_thresh = df["渠道"].astype(str).map(CVR_THRESHOLDS).fillna(CVR_UNKNOWN_THRESHOLD)
    df["cvr_score_full"] = piecewise_score_vec(df["下单转化"], _cvr_thresh)

    df["综合评分_full"] = (
        df["触达_score"] * DEFAULT_W_REACH + df["CTR_score_full"] * DEFAULT_W_CTR + df["cvr_score_full"] * DEFAULT_W_GC
    ) * pd.cut(
        df["触达成功"].fillna(0),
        bins=PENALTY_BINS,
        labels=PENALTY_LABELS,
    ).astype(float)
    return df


def compute_filtered_scores(dff: pd.DataFrame, w_reach: float, w_ctr: float, w_gc: float) -> pd.DataFrame:
    """计算筛选后的分段评分和综合评分

    触达子分用 触达_score（per-channel Q3, EXP=0.5），不再受日期筛选影响。
    CTR/GC 子分仍按当前窗口数据计算（同 Plan 内日聚合，分母是 Plan 自己）。
    """
    _dff_ctr_thresh = dff["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    dff["CTR_score"] = piecewise_score_vec(dff["CTR"], _dff_ctr_thresh)

    _dff_cvr_thresh = dff["渠道"].astype(str).map(CVR_THRESHOLDS).fillna(CVR_UNKNOWN_THRESHOLD)
    dff["cvr_score"] = piecewise_score_vec(dff["下单转化"], _dff_cvr_thresh)

    base_score = (
        dff["触达_score"] * w_reach
        + dff["CTR_score"] * w_ctr
        + dff["cvr_score"] * w_gc
    ).round(2)

    reach_raw = dff["触达成功"].fillna(0)
    penalty = pd.cut(
        reach_raw,
        bins=PENALTY_BINS,
        labels=PENALTY_LABELS,
    ).astype(float)
    dff["综合评分"] = base_score * penalty
    return dff


def compute_bu_scores(bu_agg: pd.DataFrame, norm_reach: float, norm_ctr: float, norm_gc: float) -> pd.DataFrame:
    """BU 排行榜评分：保留原 Q3 / 触达幂次 / 置信度惩戒算法，
    仅把基础分改为当前归一权重（与内容榜口径一致）。

    入参 bu_agg 必须已经包含：
        - CTR、下单转化（已 sum 后算率）
        - 触达（按 BU 汇总的原始值，本函数会再算一次触达_norm）
    """
    # ── 分段评分：低于 Q3 → 100×(值/Q3)^1.5，达标 → 100 饱和 ──────
    _bu_ctr_q3 = bu_agg["CTR"].quantile(0.75)
    _bu_cvr_q3 = bu_agg["下单转化"].quantile(0.75)

    bu_agg["CTR_norm"] = (
        piecewise_score_vec(bu_agg["CTR"], _bu_ctr_q3) if _bu_ctr_q3 > 0 else 50.0
    )
    bu_agg["下单转化_norm"] = (
        piecewise_score_vec(bu_agg["下单转化"], _bu_cvr_q3) if _bu_cvr_q3 > 0 else 50.0
    )

    # ── 触达归一化：与内容榜同口径（幂次 0.3，最大触达分母） ──────
    _bu_reach_max = bu_agg["触达"].max()
    if pd.isna(_bu_reach_max) or _bu_reach_max == 0:
        bu_agg["触达_norm"] = 0.0
    else:
        bu_agg["触达_norm"] = ((bu_agg["触达"] / _bu_reach_max) ** 0.3 * 100).round(2)

    # ── 基础分：当前归一权重（与内容榜保持一致） ──────────────────
    _bu_base = (
        bu_agg["CTR_norm"] * norm_ctr
        + bu_agg["触达_norm"] * norm_reach
        + bu_agg["下单转化_norm"] * norm_gc
    ).round(2)

    # ── 置信度惩戒（与卡片排行榜一致） ────────────────────────────
    _bu_penalty = pd.cut(
        bu_agg["触达"].fillna(0),
        bins=PENALTY_BINS,
        labels=PENALTY_LABELS,
    ).astype(float)
    bu_agg["BU综合评分"] = (_bu_base * _bu_penalty).round(2)

    bu_agg = bu_agg.sort_values("BU综合评分", ascending=False).reset_index(drop=True)
    bu_agg["排名"] = bu_agg.index + 1
    return bu_agg


# ═══════════════════════════════════════════════════════════════
# AI 总结辅助函数（2026-08-03 新增）
#
# 三个函数都是纯函数，输入/输出都是 DataFrame；不修改入参、不写文件。
# 给 build_summary_prompt 提供：
#   - 渠道 5 分位基线（健康度判断）
#   - 异常数据检测（埋点/转化率倒挂等）
#   - 每渠道 Top N（让 AI 能引用具体 Plan/标题）
# ═══════════════════════════════════════════════════════════════

# 异常检测阈值（保守起步，后续按运营经验调）
ANOMALY_REACH_MIN = 100_000       # T1 埋点型：触达下界
ANOMALY_CTR_MIN_REACH = 5_000     # T2 超低 CTR：触达下界
ANOMALY_CTR_FLOOR = 0.001         # T2 超低 CTR：CTR 下界
ANOMALY_CLICK_MIN = 200           # T3 超低转化：点击下界
ANOMALY_SAMPLE_LIMIT = 5          # 每类异常最多保留明细条数


def compute_channel_quantiles(df: pd.DataFrame) -> pd.DataFrame:
    """按渠道 + 日聚合 → 5 分位（P5/P25/P50/P75/P95）。

    用于给 AI 注入"渠道基线"——回答"这个渠道 CTR 算高算低"。

    入参 df 必须是原始逐行数据（含 发送日期 / 渠道 / 触达成功 / 点击人次 /
    点击后下单人次 / 订单GC）。缺关键列时返回空 DataFrame。
    """
    required = {"发送日期", "触达成功", "点击人次"}
    if not required.issubset(df.columns) or df.empty:
        return pd.DataFrame()

    has_channel = "渠道" in df.columns
    daily = df.groupby(
        ["发送日期"] + (["渠道"] if has_channel else []),
        dropna=False,
    ).agg(
        触达成功=("触达成功", "sum"),
        点击人次=("点击人次", "sum"),
    ).reset_index()

    if "点击后下单人次" in df.columns:
        _sub = df.groupby(
            ["发送日期"] + (["渠道"] if has_channel else []),
            dropna=False,
        )["点击后下单人次"].sum().reset_index()
        daily = daily.merge(_sub, on=["发送日期"] + (["渠道"] if has_channel else []), how="left")
        daily["下单转化"] = safe_pct_rate(daily["点击后下单人次"], daily["点击人次"])
    if "订单GC" in df.columns:
        _gc = df.groupby(
            ["发送日期"] + (["渠道"] if has_channel else []),
            dropna=False,
        )["订单GC"].sum().reset_index()
        daily = daily.merge(_gc, on=["发送日期"] + (["渠道"] if has_channel else []), how="left")
        daily["GC转化"] = safe_pct_rate(daily["订单GC"], daily["点击人次"])

    daily["CTR"] = safe_pct_rate(daily["点击人次"], daily["触达成功"])

    metric_cols = [c for c in ("CTR", "触达成功", "点击人次", "下单转化", "GC转化") if c in daily.columns]

    if not has_channel:
        # 无渠道列时按"全部"占位，确保下游能 unstack
        daily["渠道"] = "全部"
        has_channel = True

    qs = [0.05, 0.25, 0.50, 0.75, 0.95]
    q_label_map = {0.05: "p5", 0.25: "p25", 0.50: "p50", 0.75: "p75", 0.95: "p95"}
    out = daily.groupby("渠道")[metric_cols].quantile(qs)
    out = out.unstack(level=-1)
    out.columns = pd.MultiIndex.from_tuples(
        [(m, q_label_map[q]) for m, q in out.columns],
        names=["metric", "quantile"],
    )
    return out


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """检测 4 类疑似异常数据，标注不过滤。

    T1 埋点型：触达 ≥ 10万 且 点击 = 0
    T2 超低 CTR：触达 ≥ 5千 且 CTR < 0.1%
    T3 超低转化：点击 ≥ 200 且 下单 = 0
    T4 转化率倒挂：下单 > 点击（必为数据 bug）

    返回 DataFrame 列：[plan_id, 渠道, 日期, 触达, 点击, 下单, CTR, 异常类型, 提示]
    每类最多 ANOMALY_SAMPLE_LIMIT 行；按严重度排序（埋点型 > 转化率倒挂 > 超低 CTR > 无转化）。
    """
    _cols = ["plan_id", "渠道", "日期", "触达", "点击", "下单", "CTR", "异常类型", "提示"]
    rows = []
    if df.empty:
        return pd.DataFrame(columns=_cols)

    for _, r in df.iterrows():
        reach = float(r.get("触达成功", 0) or 0)
        click = float(r.get("点击人次", 0) or 0)
        order = float(r.get("点击后下单人次", 0) or 0)
        ctr = (click / reach) if reach > 0 else 0.0
        channel = str(r.get("渠道", "—") or "—")
        date = str(r.get("发送日期", "—"))[:10]
        pid = str(r.get("plan_id", "—") or "—")

        if reach >= ANOMALY_REACH_MIN and click == 0:
            rows.append([pid, channel, date, int(reach), 0, 0, 0.0, "埋点型", "触达大但点击=0，疑似埋点异常，复核埋点"])
        elif reach >= ANOMALY_CTR_MIN_REACH and ctr < ANOMALY_CTR_FLOOR:
            rows.append([pid, channel, date, int(reach), int(click), 0, round(ctr * 100, 2), "超低CTR", "CTR<0.1% 偏低，检查投放时段/人群"])
        elif click >= ANOMALY_CLICK_MIN and order == 0:
            rows.append([pid, channel, date, int(reach), int(click), 0, round(ctr * 100, 2), "无转化", "点击≥200但下单=0，可能优惠/链接失效"])
        elif click > 0 and order > click:
            rows.append([pid, channel, date, int(reach), int(click), int(order), round(ctr * 100, 2), "转化率倒挂", "下单>点击，必为数据计算错误"])

    if not rows:
        return pd.DataFrame(columns=_cols)

    out = pd.DataFrame(rows, columns=_cols)
    # 每类最多保留 ANOMALY_SAMPLE_LIMIT 条
    out = out.groupby("异常类型", group_keys=False).head(ANOMALY_SAMPLE_LIMIT).reset_index(drop=True)
    # 严重度排序：埋点型 > 转化率倒挂 > 超低 CTR > 无转化
    severity_order = {"埋点型": 0, "转化率倒挂": 1, "超低CTR": 2, "无转化": 3}
    if not out.empty and "异常类型" in out.columns:
        out["_sev"] = out["异常类型"].map(severity_order).fillna(99)
        out = out.sort_values(["_sev", "触达"], ascending=[True, False]).drop(columns="_sev").reset_index(drop=True)
    return out


def top_per_channel(dff: pd.DataFrame, n: int = 1) -> pd.DataFrame:
    """每渠道取 Top N（按综合评分）。

    入参 dff 是 aggregate_by_content 之后的 DataFrame。
    渠道 < n 条时返回该渠道全部。
    """
    if dff.empty or "渠道" not in dff.columns or "综合评分" not in dff.columns or n < 1:
        return dff.iloc[0:0].copy()

    keep_cols = [c for c in [
        "渠道", "plan_id", "标题", "消息标题", "综合评分",
        "触达成功", "点击人次", "CTR", "下单转化", "订单GC", OWNER_COL_DEFAULT,
    ] if c in dff.columns]

    sorted_df = dff.sort_values("综合评分", ascending=False, kind="mergesort")
    out = sorted_df.groupby("渠道", group_keys=False).head(n)[keep_cols].reset_index(drop=True)
    return out


# ═══════════════════════════════════════════════════════════════
# 周报模块辅助（2026-08-04 新增）
#
# 两个函数：
#   - top_n_overall：综合评分 ≥ 阈值 的全局 Top N（替代原来的每渠道 Top 1）
#   - compute_channel_baseline：渠道 CTR 基期（按日聚合算术平均 + P75）
# ═══════════════════════════════════════════════════════════════

# Top 3 阈值：综合评分 < 此值不进 Top 3，"内容都烂"时不渲染 Top 段
TOP_N_DEFAULT_MIN_SCORE = 80.0
TOP_N_DEFAULT_N = 3


def top_n_overall(dff: pd.DataFrame,
                  min_score: float = TOP_N_DEFAULT_MIN_SCORE,
                  n: int = TOP_N_DEFAULT_N) -> pd.DataFrame:
    """全局 Top N（按综合评分降序，先按阈值筛选）。

    业务定义（v5 周报）：用户要"陈列 3 个综合评分高的内容"，且
    "如果内容都特别烂就没啥好 top3"。所以默认 min_score=80，n=3。
    阈值/数量可由调用方覆盖。

    入参 dff 是 aggregate_by_content + compute_filtered_scores 之后的结果。
    没达标时返回空 DataFrame（不报错），让 UI 决定是否渲染。
    """
    if dff.empty or "综合评分" not in dff.columns or n < 1:
        return dff.iloc[0:0].copy()

    qualified = dff[dff["综合评分"] >= min_score]
    if qualified.empty:
        return qualified.iloc[0:0].copy()

    keep_cols = [c for c in [
        "渠道", "plan_id", "标题", "内容",
        "综合评分", "触达成功", "点击人次",
        "CTR", "订单Sales",
    ] if c in qualified.columns]

    sorted_q = qualified.sort_values("综合评分", ascending=False, kind="mergesort")
    out = sorted_q.head(n)[keep_cols].reset_index(drop=True)
    return out


def compute_channel_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """渠道 CTR 基期（按日聚合：算术平均 + P75）

    业务定义（v5 周报）：用户判断"渠道最近好不好"的两个参考点。
      - 基期 CTR 均值：按日算 CTR 后取算术平均（不被大触达加权，对抗小样本噪声）
      - 上四分位 CTR：按日算 CTR 后取 P75

    入参 df 是**未筛选的全量上传数据**（与 compute_channel_quantiles 同口径）。
    返回 DataFrame：index=渠道，columns=[CTR均值, CTR P75]。
    缺关键列/空表时返回空 DataFrame（columns 与正常输出一致，方便 UI 跳过）。
    """
    empty_cols = ["CTR均值", "CTR P75"]
    required = {"发送日期", "渠道", "触达成功", "点击人次"}
    if not required.issubset(df.columns) or df.empty:
        return pd.DataFrame(columns=empty_cols)

    daily = df.groupby(
        ["发送日期", "渠道"], dropna=False,
    ).agg(
        触达成功=("触达成功", "sum"),
        点击人次=("点击人次", "sum"),
    ).reset_index()

    daily["CTR"] = safe_pct_rate(daily["点击人次"], daily["触达成功"])

    # 按日 CTR 算渠道均值/P75（每日 0 触达的渠道会被 safe_pct_rate 兜成 0 拉低均值）
    grp = daily.groupby("渠道")["CTR"]
    out = pd.DataFrame({
        "CTR均值": grp.mean().round(2),
        "CTR P75": grp.quantile(0.75).round(2),
    })

    # "全部" 行：每日全渠道总点击/总触达 → 每日全渠道 CTR → mean/P75
    # 口径与各渠道行不同（各渠道：按日先 CTR 再 mean；全部：按日先总 CTR 再 mean）
    daily_all = df.groupby("发送日期").agg(
        触达=("触达成功", "sum"),
        点击=("点击人次", "sum"),
    ).reset_index()
    daily_all["CTR"] = safe_pct_rate(daily_all["点击"], daily_all["触达"])
    out.loc["全部"] = [
        round(float(daily_all["CTR"].mean()), 2),
        round(float(daily_all["CTR"].quantile(0.75)), 2),
    ]
    return out
