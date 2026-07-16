"""冒烟测试：验证 Excel/CSV 日期解析在 4 种场景下都正常"""
import sys
import io
import datetime
from pathlib import Path

# 让脚本可以 import 项目模块
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from data_cleaning import _parse_date_column, _map_columns, _coerce_numeric_columns, DATE_COL


def assert_eq(actual, expected, label):
    if actual == expected:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}: expected {expected!r}, got {actual!r}")
        raise AssertionError(label)


def test_string_dates():
    """场景1：CSV 字符串日期 '2024-01-15' / '2024/01/20'"""
    print("\n[1] 字符串日期")
    s = pd.Series(["2024-01-15", "2024/01/20", "2024.01.25", None])
    out = _parse_date_column(s)
    assert_eq(out.iloc[0], pd.Timestamp("2024-01-15"), "ISO 格式")
    assert_eq(out.iloc[1], pd.Timestamp("2024-01-20"), "斜杠格式")
    assert_eq(out.iloc[2], pd.Timestamp("2024-01-25"), "点号格式")
    assert pd.isna(out.iloc[3]), "None 应保持空"
    print("  类型:", out.dtype)


def test_datetime_objects():
    """场景2：openpyxl 读取 Excel 日期格式单元格，返回 datetime 对象"""
    print("\n[2] datetime 对象（Excel 日期单元格）")
    s = pd.Series([datetime.datetime(2024, 1, 15), datetime.datetime(2024, 1, 20)])
    out = _parse_date_column(s)
    assert_eq(out.iloc[0], pd.Timestamp("2024-01-15"), "datetime 对象 1")
    assert_eq(out.iloc[1], pd.Timestamp("2024-01-20"), "datetime 对象 2")
    print("  类型:", out.dtype)


def test_excel_serial_numbers():
    """场景3：Excel 数字日期序列号（45292 = 2024-01-01, 用 1899-12-30 起点绕过 1900 闰年 bug）"""
    print("\n[3] Excel 日期序列号")
    # Excel 45292 = 2024-01-01
    s = pd.Series([45292.0, 45322.0, 45352.0])  # 2024-01-01, 2024-01-31, 2024-03-01
    out = _parse_date_column(s)
    assert_eq(out.iloc[0], pd.Timestamp("2024-01-01"), "序列号 45292 -> 2024-01-01")
    assert_eq(out.iloc[1], pd.Timestamp("2024-01-31"), "序列号 45322 -> 2024-01-31")
    assert_eq(out.iloc[2], pd.Timestamp("2024-03-01"), "序列号 45352 -> 2024-03-01")
    print("  类型:", out.dtype)


def test_non_date_numbers():
    """场景4：超大数字（不是日期）应原样返回。
    Excel 序列号最大约 73050 (2100-01-01)，超过即视为真实数值列。"""
    print("\n[4] 非日期数字列（超过 73050 的触达/点击量）")
    s = pd.Series([999999, 1234567, 8888888])  # 真实触达量级
    out = _parse_date_column(s)
    assert_eq(out.iloc[0], 999999, "超大数字 999999 不应被解析为日期")
    assert out.dtype == "int64" or out.dtype == "float64", f"应保持数值类型, got {out.dtype}"


def test_click_count_floats():
    """场景 4b：浮点型触达列（如 12345.0）会落入 Excel 序列号范围
    —— 这正是 _coerce_numeric_columns 必须豁免日期列的原因。"""
    print("\n[4b] 浮点型触达 vs 日期 — _coerce_numeric_columns 校验")
    # 验证：日期列被 _parse_date_column 转 datetime 后，
    # _coerce_numeric_columns 不会再把它转回 float
    df = pd.DataFrame({
        "发送日期": pd.to_datetime([45292, 45322], unit="D", origin="1899-12-30"),  # 已转 datetime
        "触达成功": [12345.0, 67890.0],  # 浮点数列
    })
    df2 = _coerce_numeric_columns(df.copy())
    assert pd.api.types.is_datetime64_any_dtype(df2["发送日期"]), "日期列必须保持 datetime"
    assert_eq(df2["触达成功"].dtype, "float64", "触达成功 转为 float64")
    print("  日期 dtype:", df2["发送日期"].dtype)


def test_column_mapping():
    """场景5：列名模糊匹配（send_date → 发送日期）"""
    print("\n[5] 列名模糊匹配")
    df = pd.DataFrame({
        "send_date": ["2024-01-15"],
        "channel_name": ["APP Push"],
        "owner": ["Tom"],
    })
    out = _map_columns(df)
    assert_eq(DATE_COL in out.columns, True, "send_date -> 发送日期 映射成功")
    assert_eq("渠道" in out.columns, True, "channel_name -> 渠道 映射成功")
    print("  映射后列名:", [str(c) for c in out.columns])


def test_coerce_skips_date():
    """场景6：完整流程——先 _parse_date_column 转 datetime，再 _coerce_numeric_columns 不能误转日期列"""
    print("\n[6] 完整流程：parse_date → coerce_numeric 串行")
    df = pd.DataFrame({
        "发送日期": [45292.0, 45322.0],  # Excel 序列号
        "触达成功": ["100", "200"],        # 字符串数字
    })
    # 真实 load 流程：先解析日期，再 coerce 数值
    df[DATE_COL] = _parse_date_column(df[DATE_COL])
    df = _coerce_numeric_columns(df)
    assert_eq(df["触达成功"].dtype, "float64", "触达成功 字符串数字应转 float64")
    assert pd.api.types.is_datetime64_any_dtype(df["发送日期"]), \
        f"发送日期应保持 datetime，实际是 {df['发送日期'].dtype}"
    assert_eq(df["发送日期"].iloc[0], pd.Timestamp("2024-01-01"), "日期列值正确")
    print("  发送日期 dtype:", df["发送日期"].dtype)


if __name__ == "__main__":
    print("=" * 60)
    print("冒烟测试：data_cleaning 日期解析兼容性")
    print("=" * 60)
    test_string_dates()
    test_datetime_objects()
    test_excel_serial_numbers()
    test_non_date_numbers()
    test_click_count_floats()
    test_column_mapping()
    test_coerce_skips_date()
    print("\n" + "=" * 60)
    print("[OK] 所有冒烟测试通过")
    print("=" * 60)
