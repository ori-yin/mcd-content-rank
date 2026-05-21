"""
data_cleaning.py - 麦当劳内容排行榜：数据清洗
"""

import json
import re
import pandas as pd
from io import BytesIO


def extract_title_from_forms(forms):
    """从 forms 列表中提取标题"""
    if not isinstance(forms, list):
        return None
    for item in forms:
        if item.get('code') == 'thing1' and item.get('value'):
            return item['value']
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if code.startswith('thing') and value:
            return value
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if not code.startswith('time') and value:
            return value
    return None


def extract_text_from_forms(forms):
    """从 forms 列表中提取正文"""
    if not isinstance(forms, list):
        return None
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if code in ['thing5', 'short_thing5'] and value:
            return value
    for item in forms:
        code = item.get('code', '')
        value = item.get('value')
        if code.startswith('thing') and code != 'thing1' and value:
            return value
    return None


def parse_message(raw):
    """将原始 JSON 消息解析为标题和正文"""
    if pd.isna(raw) or not isinstance(raw, str):
        return pd.Series({'标题': '', '内容': ''})

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return pd.Series({'标题': '', '内容': ''})

    title = data.get('title')
    if not title:
        title = extract_title_from_forms(data.get('forms'))
    if not title:
        attachments = data.get('attachments')
        if isinstance(attachments, list) and len(attachments) > 0:
            title = attachments[0].get('name', '')

    text = data.get('text')
    if not text:
        text = extract_text_from_forms(data.get('forms'))

    if not title and text:
        first_part = re.split(r'[。！？\n]', str(text).strip())[0].strip()
        if len(first_part) > 0:
            title = first_part
        else:
            title = str(text)[:20]

    title = str(title).strip() if title else ''
    text = str(text).strip() if text else ''

    # 清洗特殊字符
    title = title.replace('?', '').replace('\r\n', '').replace('\n', '').replace('\r', '')
    text = text.replace('?', '').replace('\r\n', '').replace('\n', '').replace('\r', '')

    return pd.Series({'标题': title, '内容': text})


def clean_raw_csv(uploaded_file) -> pd.DataFrame:
    """
    1. 尝试多种编码读取原始 CSV
    2. 检查是否有至少 15 列
    3. 读取第 O 列（索引 14，即第 15 列）
    4. 解析 JSON，提取标题和内容
    5. 合并回原 DataFrame，删除原始 JSON 列
    """
    bytes_data = uploaded_file.read()

    # 尝试多种编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(BytesIO(bytes_data), encoding=enc, on_bad_lines='skip')
            break
        except Exception:
            continue

    if df is None:
        raise ValueError("无法读取 CSV 文件，请检查文件格式")

    # 检查是否有至少 15 列
    if df.shape[1] < 15:
        raise ValueError(f"CSV 只有 {df.shape[1]} 列，第 15 列（O列）不存在")

    # 读取第 O 列（索引 14）
    o_col = df.iloc[:, 14]

    # 执行解析
    parsed_df = o_col.apply(parse_message)

    # 合并回原 DataFrame，删除原始 JSON 列
    df['标题'] = parsed_df['标题']
    df['内容'] = parsed_df['内容']
    df = df.drop(df.columns[14], axis=1)

    return df


def read_cleaned_csv(uploaded_file) -> pd.DataFrame:
    """读取已清洗的 CSV，自动尝试多种编码"""
    try:
        return pd.read_csv(uploaded_file, encoding="gbk")
    except Exception:
        try:
            return pd.read_csv(uploaded_file, encoding="utf-8")
        except Exception:
            return pd.read_csv(uploaded_file, encoding="utf-8-sig")
