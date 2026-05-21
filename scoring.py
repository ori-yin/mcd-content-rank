"""
scoring.py - 麦当劳内容排行榜：评分算法
"""

import numpy as np
import pandas as pd
from config import (
    CTR_THRESHOLDS, GC_THRESHOLDS,
    CTR_UNKNOWN_THRESHOLD, GC_UNKNOWN_THRESHOLD, EXP,
)

PENALTY_BINS = [-1, 99, 499, 999, 4999, float("inf")]
PENALTY_LABELS = [0.1, 0.3, 0.5, 0.8, 1.0]


def piecewise_score_vec(G_col, threshold_col):
    """向量化版本：整列一次计算，比 apply 快 100 倍"""
    ratio = G_col / threshold_col
    return np.where(ratio >= 1, 100.0, 100.0 * ratio ** EXP)


def compute_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """计算 CTR、订单GC转化率、触达归一化"""
    df["CTR"] = (df["点击人次"] / df["触达成功"] * 100).round(2)
    df["CTR"] = df["CTR"].replace([float("inf"), -float("inf")], 0).fillna(0)

    df["订单GC转化率"] = (df["订单GC"] / df["点击人次"] * 100).round(2)
    df["订单GC转化率"] = df["订单GC转化率"].replace([float("inf"), -float("inf")], 0).fillna(0)

    df["触达_norm"] = ((df["触达成功"] / df["触达成功"].max()) ** 0.3) * 100
    return df


def compute_full_scores(df: pd.DataFrame) -> pd.DataFrame:
    """计算全量数据的综合评分（用于渠道均值，不受筛选影响）"""
    _ctr_thresh = df["渠道"].astype(str).map(CTR_THRESHOLDS).fillna(CTR_UNKNOWN_THRESHOLD)
    df["CTR_score_full"] = piecewise_score_vec(df["CTR"], _ctr_thresh)

    _gc_thresh = df["渠道"].astype(str).map(GC_THRESHOLDS).fillna(GC_UNKNOWN_THRESHOLD)
    df["GC_score_full"] = piecewise_score_vec(df["订单GC转化率"], _gc_thresh)

    df["综合评分_full"] = (
        df["触达_norm"] * 0.2 + df["CTR_score_full"] * 0.50 + df["GC_score_full"] * 0.30
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

    _dff_gc_thresh = dff["渠道"].astype(str).map(GC_THRESHOLDS).fillna(GC_UNKNOWN_THRESHOLD)
    dff["GC_score"] = piecewise_score_vec(dff["订单GC转化率"], _dff_gc_thresh)

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
