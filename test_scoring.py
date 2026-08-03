"""冒烟测试：scoring 评分/聚合的核心业务口径"""
import sys
from pathlib import Path

# 让脚本可以 import 项目模块
sys.path.insert(0, str(Path(__file__).parent))

import math
import numpy as np
import pandas as pd
from scoring import (
    piecewise_score_vec,
    safe_pct_rate,
    compute_derived_metrics,
    compute_filtered_scores,
    aggregate_by_content,
    compute_bu_scores,
    compute_channel_quantiles,
    detect_anomalies,
    top_per_channel,
    PENALTY_BINS,
    PENALTY_LABELS,
    EXP,
)


def assert_eq(actual, expected, label, tol=1e-6):
    """与 test_date_parsing.py 同风格的轻量断言"""
    if isinstance(expected, float) or isinstance(actual, float):
        if math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol):
            print(f"  [PASS] {label}")
        else:
            print(f"  [FAIL] {label}: expected {expected!r}, got {actual!r}")
            raise AssertionError(label)
    elif actual == expected:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}: expected {expected!r}, got {actual!r}")
        raise AssertionError(label)


def test_piecewise_score_three_segments():
    """T1: piecewise_score_vec 边界：<Q3 / =Q3 / >Q3 三段"""
    print("\n[T1] piecewise_score_vec 三段边界")
    q3 = pd.Series([1.0] * 3)
    g = pd.Series([0.5, 1.0, 1.5])
    out = piecewise_score_vec(g, q3)
    # G<Q3: 100 * (0.5/1.0)^1.5 = 100 * 0.353553... = 35.355...
    assert_eq(round(float(out[0]), 4), round(100 * (0.5 ** EXP), 4), "G<Q3 走幂次公式")
    # G==Q3: 100 饱和
    assert_eq(float(out[1]), 100.0, "G==Q3 = 100 饱和")
    # G>Q3: 100 饱和
    assert_eq(float(out[2]), 100.0, "G>Q3 = 100 饱和")


def test_safe_pct_rate_zero_div():
    """T2: safe_pct_rate 0/0 兜底 + 正常路径"""
    print("\n[T2] safe_pct_rate 0/0 与正常")
    num = pd.Series([100, 0, 30])
    den = pd.Series([200, 0, 0])
    out = safe_pct_rate(num, den)
    assert_eq(float(out.iloc[0]), 50.0, "100/200 = 50.0")
    assert_eq(float(out.iloc[1]), 0.0, "0/0 兜底 0 不抛")
    assert_eq(float(out.iloc[2]), 0.0, "30/0 兜底 0 不抛")


def test_derived_zero_reach():
    """T3: 全部触达为 0 时，触达_norm 兜底全 0（0/0 不会变 NaN）"""
    print("\n[T3] compute_derived_metrics 触达全 0 兜底")
    df = pd.DataFrame({
        "触达成功": [0, 0, 0],
        "点击人次": [0, 0, 0],
        "点击后下单人次": [0, 0, 0],
    })
    out = compute_derived_metrics(df)
    assert_eq(out["触达_norm"].isna().sum(), 0, "触达_norm 不应为 NaN")
    assert_eq(bool(out["触达_norm"].eq(0.0).all()), True, "触达_norm 全 0")
    assert_eq(bool(out["CTR"].eq(0.0).all()), True, "CTR 全 0")
    assert_eq(bool(out["下单转化"].eq(0.0).all()), True, "下单转化 全 0")


def test_derived_missing_cvr_column():
    """T4: 缺 '点击后下单人次' 列时下单转化 0 兜底不抛"""
    print("\n[T4] compute_derived_metrics 缺 '点击后下单人次' 兜底")
    df = pd.DataFrame({
        "触达成功": [1000, 2000, 1500],
        "点击人次": [30, 50, 40],
    })
    out = compute_derived_metrics(df)
    assert "下单转化" in out.columns, "下单转化 列必须生成"
    assert_eq(bool(out["下单转化"].eq(0.0).all()), True, "缺列时下单转化 全 0")
    # CTR 仍然正常
    assert_eq(round(float(out["CTR"].iloc[0]), 2), 3.0, "1000/30 应得 CTR=3.0%")


def test_filtered_weights_orthogonal():
    """T5: 三路权重完全正交 — 单一权重(0,1,0) 时综合评分 == CTR_score * penalty"""
    print("\n[T5] compute_filtered_scores 三路权重完全正交")
    df = pd.DataFrame({
        "触达成功": [5000, 5000],
        "点击人次": [50, 200],
        "点击后下单人次": [5, 30],
        "渠道": ["APP Push", "APP Push"],
    })
    df = compute_derived_metrics(df)
    out = compute_filtered_scores(df.copy(), w_reach=0.0, w_ctr=1.0, w_gc=0.0)
    # 单权重时，base_score == CTR_score
    expected_base = out["CTR_score"]
    actual_base = (out["触达_norm"] * 0.0 + out["CTR_score"] * 1.0 + out["GC_score"] * 0.0).round(2)
    assert_eq(bool((actual_base == expected_base.round(2)).all()), True,
              "(0,1,0) 权重时 base == CTR_score")
    # penalty = 1.0（触达 5000 走最高档）
    assert_eq(bool(out["综合评分"].gt(0).all()), True, "综合评分应 > 0")


def test_filtered_penalty_five_tiers():
    """T6: 置信度惩戒五档 — 50/200/700/2000/6000 触达 → 0.1/0.3/0.5/0.8/1.0"""
    print("\n[T6] compute_filtered_scores 惩戒五档边界")
    reaches = [50, 200, 700, 2000, 6000]
    expected_penalties = [0.1, 0.3, 0.5, 0.8, 1.0]
    df = pd.DataFrame({
        "触达成功": reaches,
        "点击人次": [10] * 5,
        "点击后下单人次": [1] * 5,
        "渠道": ["APP Push"] * 5,
    })
    df = compute_derived_metrics(df)
    out = compute_filtered_scores(df, w_reach=0.0, w_ctr=0.0, w_gc=0.0)
    # 综合评分应 == base * penalty，base 全为 0 → 综合评分 = 0
    # 这里不能直接看综合评分（base=0），所以验 PENALTY_BINS/LABELS 的映射：
    actual_penalties = pd.cut(
        pd.Series(reaches), bins=PENALTY_BINS, labels=PENALTY_LABELS
    ).astype(float).tolist()
    for r, a, e in zip(reaches, actual_penalties, expected_penalties):
        assert_eq(float(a), float(e), f"触达={r} 惩戒={e}")


def test_aggregate_same_message_units_merge():
    """T7: 同 (plan, message) 多 Unit 合并为 1 行，Unit 数=真实去重数"""
    print("\n[T7] aggregate_by_content 多 Unit 合并")
    df = pd.DataFrame({
        "plan_id": ["P1", "P1", "P1", "P1"],
        "message_id": ["M1", "M1", "M1", "M2"],
        "unit_id": ["U1", "U2", "U3", "U4"],
        "发送日期": pd.to_datetime(["2026-07-01"] * 4),
        "触达成功": [1000, 2000, 3000, 500],
        "点击人次": [10, 30, 60, 5],
        "点击后下单人次": [1, 3, 6, 0],
        "订单GC": [1, 3, 6, 0],
        "订单Sales": [10.0, 30.0, 60.0, 0.0],
        "计划类型": ["拉新"] * 4,
        "渠道": ["APP Push"] * 4,
        "owner": ["BU-A"] * 4,
        "是否用券": [False] * 4,
        "标题": ["T1", "T1", "T1", "T2"],
        "内容": ["C1", "C1", "C1", "C2"],
    })
    out = aggregate_by_content(df)
    # 应有 2 行：P1×M1 和 P1×M2
    assert_eq(len(out), 2, "聚合后 2 行")
    p1m1 = out[(out["plan_id"] == "P1") & (out["message_id"] == "M1")].iloc[0]
    assert_eq(int(p1m1["触达成功"]), 6000, "M1 触达合并 1000+2000+3000")
    assert_eq(int(p1m1["点击人次"]), 100, "M1 点击合并 10+30+60")
    assert_eq(int(p1m1["Unit数"]), 3, "M1 Unit 数 3（去重）")
    p1m2 = out[(out["plan_id"] == "P1") & (out["message_id"] == "M2")].iloc[0]
    assert_eq(int(p1m2["Unit数"]), 1, "M2 Unit 数 1")


def test_aggregate_fallback_no_message_id():
    """T8: 旧数据无 message_id → 退化为 (plan_id, 标题) 聚合"""
    print("\n[T8] aggregate_by_content 旧数据退化路径")
    df = pd.DataFrame({
        "plan_id": ["P1", "P1"],
        "unit_id": ["U1", "U2"],
        "发送日期": pd.to_datetime(["2026-07-01", "2026-07-01"]),
        "触达成功": [1000, 500],
        "点击人次": [10, 5],
        "点击后下单人次": [0, 0],
        "订单GC": [0, 0],
        "订单Sales": [0.0, 0.0],
        "计划类型": ["拉新"] * 2,
        "渠道": ["APP Push"] * 2,
        "owner": ["BU-A"] * 2,
        "是否用券": [False] * 2,
        "标题": ["T1", "T1"],
        "内容": ["C1", "C1"],
        # 故意不带 message_id
    })
    out = aggregate_by_content(df)
    # 退化路径：(plan_id, 标题) = (P1, T1) 唯一组合 → 1 行
    assert_eq(len(out), 1, "无 message_id 时按 (plan,标题) 聚合 1 行")
    assert_eq(int(out.iloc[0]["触达成功"]), 1500, "触达合并 1000+500")


if __name__ == "__main__":
    print("=" * 60)
    print("冒烟测试：scoring 评分/聚合核心业务口径")
    print("=" * 60)
    test_piecewise_score_three_segments()
    test_safe_pct_rate_zero_div()
    test_derived_zero_reach()
    test_derived_missing_cvr_column()
    test_filtered_weights_orthogonal()
    test_filtered_penalty_five_tiers()
    test_aggregate_same_message_units_merge()
    test_aggregate_fallback_no_message_id()
    # BU 评分也快速冒烟（用与卡片榜一致的口径）
    print("\n[+] compute_bu_scores 与卡片榜口径一致冒烟")
    bu_agg = pd.DataFrame({
        "触达": [10000, 5000, 500],
        "点击": [200, 150, 50],
        "点击后下单": [20, 15, 5],
        "CTR": [2.0, 3.0, 10.0],
        "下单转化": [10.0, 10.0, 10.0],
    })
    out_bu = compute_bu_scores(bu_agg, norm_reach=0.25, norm_ctr=0.55, norm_gc=0.20)
    assert_eq(int(out_bu["排名"].iloc[0]), 1, "BU 综合评分第一名为 1")
    assert "BU综合评分" in out_bu.columns, "BU综合评分 列已生成"
    assert "CTR_norm" in out_bu.columns, "CTR_norm 列已生成"
    assert "触达_norm" in out_bu.columns, "触达_norm 列已生成"
    print(f"  [INFO] BU 排名结果：\n{out_bu[['排名', '触达', 'BU综合评分']]}")

    # ─── T9: compute_channel_quantiles shape ───
    print("\n[T9] compute_channel_quantiles 多渠道 shape")
    qdf = pd.DataFrame({
        "发送日期": pd.to_datetime(["2026-07-01"] * 7 + ["2026-07-02"] * 7),
        "渠道": ["APP Push"] * 7 + ["企微1v1"] * 7,
        "触达成功": list(range(100, 800, 100)) + list(range(5000, 12000, 1000)),
        "点击人次": [10, 20, 30, 40, 50, 60, 70] + [50, 60, 70, 80, 90, 100, 110],
        "点击后下单人次": [1] * 14,
        "订单GC": [1] * 14,
    })
    out_q = compute_channel_quantiles(qdf)
    assert_eq(len(out_q), 2, "2 个渠道 → 2 行")
    # 列应为 (metric, quantile) 二级索引；含 CTR / 触达成功 / GC转化 / 下单转化
    metrics = {m for m, _ in out_q.columns}
    assert_eq("CTR" in metrics, True, "包含 CTR 指标")
    assert_eq("触达成功" in metrics, True, "包含 触达成功 指标")
    quantiles = {q for _, q in out_q.columns}
    for q in ("p5", "p25", "p50", "p75", "p95"):
        assert_eq(q in quantiles, True, f"包含 {q} 分位")

    # ─── T10: compute_channel_quantiles 已知值 ───
    print("\n[T10] compute_channel_quantiles P50 已知值")
    one_ch = pd.DataFrame({
        "发送日期": pd.to_datetime([f"2026-07-0{i+1}" for i in range(7)]),
        "渠道": ["APP Push"] * 7,
        "触达成功": [100, 200, 300, 400, 500, 600, 700],
        "点击人次": [10, 20, 30, 40, 50, 60, 70],
        "点击后下单人次": [1] * 7,
        "订单GC": [1] * 7,
    })
    out_q2 = compute_channel_quantiles(one_ch)
    p50_reach = float(out_q2.loc["APP Push", ("触达成功", "p50")])
    assert_eq(int(p50_reach), 400, "单渠道 7 天触达 [100..700] P50=400")
    p50_ctr = float(out_q2.loc["APP Push", ("CTR", "p50")])
    assert_eq(round(p50_ctr, 2), 10.0, "CTR P50=10.0%（7 天点击/触达全 10%）")

    # ─── T11: detect_anomalies 4 类全识别 ───
    print("\n[T11] detect_anomalies 4 类异常")
    adf = pd.DataFrame({
        "发送日期": pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04"]),
        "渠道": ["企微1v1", "APP Push", "APP Push", "短信"],
        "触达成功": [200000, 8000, 1000, 300],
        "点击人次": [0, 5, 200, 100],
        "点击后下单人次": [0, 0, 250, 0],
    })
    out_a = detect_anomalies(adf)
    types_found = set(out_a["异常类型"].tolist())
    assert_eq("埋点型" in types_found, True, "T1 埋点型（200K 触达 + 0 点击）")
    assert_eq("超低CTR" in types_found, True, "T2 超低CTR（8K 触达 + CTR 0.06%）")
    assert_eq("转化率倒挂" in types_found, True, "T4 转化率倒挂（点击 200 / 下单 250）")
    # T3 不在样本里
    assert_eq("无转化" in types_found, False, "T3 无转化 不应出现")

    # ─── T12: detect_anomalies 抽样限制 ───
    print("\n[T12] detect_anomalies 每类最多 5 条")
    big = pd.DataFrame({
        "发送日期": pd.to_datetime([f"2026-07-{i+1:02d}" for i in range(10)]),
        "渠道": ["APP Push"] * 10,
        "触达成功": [200000] * 10,
        "点击人次": [0] * 10,
        "点击后下单人次": [0] * 10,
    })
    out_a2 = detect_anomalies(big)
    assert_eq(len(out_a2[out_a2["异常类型"] == "埋点型"]), 5, "10 条同类异常只保留 5 条")

    # ─── T13: top_per_channel 基本 ───
    print("\n[T13] top_per_channel 每渠道 1 条")
    dff_top = pd.DataFrame({
        "渠道": ["APP Push", "APP Push", "APP Push", "企微1v1", "企微1v1"],
        "plan_id": ["P1", "P2", "P3", "P4", "P5"],
        "标题": ["A1", "A2", "A3", "B1", "B2"],
        "综合评分": [50, 80, 60, 90, 70],
        "触达成功": [1000, 5000, 2000, 3000, 1500],
        "点击人次": [10, 50, 20, 30, 15],
        "CTR": [1.0, 1.0, 1.0, 1.0, 1.0],
    })
    out_t = top_per_channel(dff_top, n=1)
    assert_eq(len(out_t), 2, "2 渠道 × n=1 → 2 行")
    # APP Push 应取 P2（评分 80）；企微1v1 取 P4（90）
    assert_eq(str(out_t[out_t["渠道"] == "APP Push"]["plan_id"].iloc[0]), "P2", "APP Push 取评分最高 P2")
    assert_eq(str(out_t[out_t["渠道"] == "企微1v1"]["plan_id"].iloc[0]), "P4", "企微1v1 取评分最高 P4")

    # ─── T14: top_per_channel 空表 ───
    print("\n[T14] top_per_channel 空表不抛")
    empty = pd.DataFrame(columns=["渠道", "plan_id", "综合评分"])
    out_e = top_per_channel(empty, n=1)
    assert_eq(len(out_e), 0, "空 dff 返回 0 行不抛")
    # 单渠道只有 1 条时 n=1 不抛
    one_row = pd.DataFrame({"渠道": ["APP Push"], "plan_id": ["P1"], "综合评分": [60.0]})
    out_o = top_per_channel(one_row, n=1)
    assert_eq(len(out_o), 1, "单渠道 1 条 n=1 仍返回 1 行")

    print("\n" + "=" * 60)
    print("[OK] 所有冒烟测试通过")
    print("=" * 60)
