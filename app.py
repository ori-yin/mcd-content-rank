# -*- coding: utf-8 -*-
"""诊断版 app：输出编码检测详细错误信息"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime, timedelta
import io
import sys

# ─── 全局配置 ───────────────────────────────────────────────
COLUMN_ALIASES = {
    '日期': 'send_date', '推送日期': 'send_date', 'senddate': 'send_date',
    '渠道': 'channel', '推送渠道': 'channel',
    '计划名称': 'plan_name', 'plan name': 'plan_name', 'plan_name': 'plan_name',
    '计划ID': 'plan_id', 'Plan ID': 'plan_id', 'planid': 'plan_id',
    '推送成功': 'reach', '新推送人数': 'reach',
    '点击': 'clicks', '点击人数': 'clicks', '点击数': 'clicks',
    '下单': 'orders', '下单人数': 'orders', '订单': 'orders',
    '销售': 'sales', 'Sales': 'sales', 'sales': 'sales',
    '销售额': 'sales',
    'Owner': 'owner', '计划Owner': 'owner', 'owner': 'owner',
    '消息ID': 'message_id', 'message_id': 'message_id',
    '标题': 'title', 'title': 'title', '标题': 'title',
    '内容': 'body', 'body': 'body', '正文': 'body',
}
OPT_COLS = ['owner', 'title', 'body', 'message_id']

# ─── 诊断版 read_csv ─────────────────────────────────────────
def read_csv_diagnostic(uploaded_file):
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"]
    uploaded_file.seek(0)
    raw_bytes = uploaded_file.getvalue()
    total_len = len(raw_bytes)
    st.session_state['_debug_info'] = f"文件大小: {total_len} bytes"

    for enc in encodings:
        try:
            file_io = io.BytesIO(raw_bytes)
            df = pd.read_csv(file_io, encoding=enc, dtype=str)
            df = df.loc[:, ~df.columns.str.strip().eq("")]
            if df.shape[0] == 0:
                return None, "文件为空（0 行），请检查 CSV 内容"
            st.session_state['_debug_info'] += f"\n成功编码: {enc}, 行数={df.shape[0]}, 列数={df.shape[1]}"
            return df, None
        except Exception as e:
            st.session_state['_debug_info'] += f"\n[{enc}] 失败: {type(e).__name__}: {str(e)[:200]}"
            pass
    return None, "无法识别文件编码，请将 CSV 保存为 UTF-8 格式后重试"


def read_csv_flexible(uploaded_file):
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"]
    uploaded_file.seek(0)
    raw_bytes = uploaded_file.getvalue()
    for enc in encodings:
        try:
            file_io = io.BytesIO(raw_bytes)
            df = pd.read_csv(file_io, encoding=enc, dtype=str)
            df = df.loc[:, ~df.columns.str.strip().eq("")]
            if df.shape[0] == 0:
                return None, "文件为空（0 行），请检查 CSV 内容"
            return df, None
        except Exception:
            pass
    return None, "无法识别文件编码，请将 CSV 保存为 UTF-8 格式后重试"


def normalize_columns(df):
    rename_map = {}
    for col in df.columns:
        col_s = str(col).strip()
        if col_s in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col_s]
    return df.rename(columns=rename_map)


def normalize_values(df):
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    return df


# ─── 主程序 ─────────────────────────────────────────────────
st.set_page_config(page_title="内容排行榜-诊断版", page_icon="🔍")

st.title("🔍 内容排行榜 - 诊断版")
st.caption("诊断版：显示编码检测详细过程，帮助定位问题")

# 调试信息展示区
if '_debug_info' in st.session_state:
    st.text_area("诊断信息（实时更新）", st.session_state['_debug_info'], height=120, disabled=True)

uploaded = st.file_uploader(":inbox_tray: 上传推送数据 CSV", type=["csv"])

if not uploaded:
    st.info(":point_up: 请上传推送数据 CSV 文件开始分析")
    st.stop()

# 用诊断版本
df_raw, err = read_csv_diagnostic(uploaded)
if err:
    st.error(f"读取文件失败：{err}")
    st.text("详细诊断信息见上方文本框")
    st.stop()

df_raw = normalize_columns(df_raw)
df_raw = normalize_values(df_raw)

if "send_date" in df_raw.columns:
    df_raw["send_date"] = pd.to_datetime(df_raw["send_date"], errors="coerce")

needed = ["reach", "clicks", "orders", "sales"]
missing = [c for c in needed if c not in df_raw.columns]
if missing:
    st.error(f"缺少必要字段：{missing}，请确认 CSV 包含正确列名")
    st.dataframe(df_raw.head(3))
    st.stop()

st.success(f"读取成功！共 {len(df_raw)} 行，已识别列：{list(df_raw.columns)}")
st.dataframe(df_raw.head(5))
