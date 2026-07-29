"""
scoring.py - 麦当劳内容排行榜：评分算法
"""

import numpy as np
import pandas as pd
from config import (
    CTR_THRESHOLDS, CVR_THRESHOLDS,
    CTR_UNKNOWN_THRESHOLD, CVR_UNKNOWN_THRESHOLD, EXP,
    DEFAULT_W_REACH, DEFAULT_W_CTR, DEFAULT_W_GC,
)
from data_cleaning import DATE_COL

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



def piecewise_score_vec(G_col, threshold_col):
    """向量化版本：整列一次计算，比 apply 快 100 倍"""
    ratio = G_col / threshold_col
    return np.where(ratio >= 1, 100.0, 100.0 * ratio ** EXP)


def safe_pct_rate(num, denom):
    """聚合安全百分比：sum(分子) / sum(分母) × 100，处理 0/0 情况"""
    return (num / denom * 100).replace([float("inf"), -float("inf")], 0).round(2).fillna(0)


def compute_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """计算 CTR、下单转化、触达归一化"""
    df["CTR"] = (df["点击人次"] / df["触达成功"] * 100).round(2)
    df["CTR"] = df["CTR"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # 缺"点击后下单人次"列时按 0 处理（旧 CSV 容错）；df.get 返回 0 标量 → 全 0 Series
    df["下单转化"] = (df.get("点击后下单人次", 0) / df["点击人次"] * 100).round(2)
    df["下单转化"] = df["下单转化"].replace([float("inf"), -float("inf")], 0).fillna(0)

    # 触达_max=0（全部触达为0）时 0/0=NaN，整列评分会变 NaN，这里兜底为 0
    _reach_max = df["触达成功"].max()
    if pd.isna(_reach_max) or _reach_max == 0:
        df["触达_norm"] = 0.0
    else:
        df["触达_norm"] = ((df["触达成功"] / _reach_max) ** 0.3) * 100
    return df


def compute_full_scores(df: pd.DataFrame) -> pd.DataFrame:
    """计算全量数据的综合评分（用于渠道均值，不受筛选影响）"""
    _ctr_thresh = df["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    df["CTR_score_full"] = piecewise_score_vec(df["CTR"], _ctr_thresh)

    _cvr_thresh = df["渠道"].astype(str).map(CVR_THRESHOLDS).fillna(CVR_UNKNOWN_THRESHOLD)
    df["GC_score_full"] = piecewise_score_vec(df["下单转化"], _cvr_thresh)

    df["综合评分_full"] = (
        df["触达_norm"] * DEFAULT_W_REACH + df["CTR_score_full"] * DEFAULT_W_CTR + df["GC_score_full"] * DEFAULT_W_GC
    ) * pd.cut(
        df["触达成功"].fillna(0),
        bins=PENALTY_BINS,
        labels=PENALTY_LABELS,
    ).astype(float)
    return df


def compute_filtered_scores(dff: pd.DataFrame, w_reach: float, w_ctr: float, w_gc: float) -> pd.DataFrame:
    """计算筛选后的分段评分和综合评分"""
    _dff_ctr_thresh = dff["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    dff["CTR_score"] = piecewise_score_vec(dff["CTR"], _dff_ctr_thresh)

    _dff_cvr_thresh = dff["渠道"].astype(str).map(CVR_THRESHOLDS).fillna(CVR_UNKNOWN_THRESHOLD)
    dff["GC_score"] = piecewise_score_vec(dff["下单转化"], _dff_cvr_thresh)

    base_score = (
        dff["触达_norm"] * w_reach
        + dff["CTR_score"] * w_ctr
        + dff["GC_score"] * w_gc
    ).round(2)

    reach_raw = dff["触达成功"].fillna(0)
    penalty = pd.cut(
        reach_raw,
        bins=PENALTY_BINS,
        labels=PENALTY_LABELS,
    ).astype(float)
    dff["综合评分"] = base_score * penalty
    return dff
