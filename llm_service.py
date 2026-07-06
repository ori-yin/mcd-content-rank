"""
llm_service.py - 麦当劳内容排行榜：LLM 内容分析服务
"""

import json
import re
import openai
import pandas as pd
from config import API_PROVIDERS, OWNER_COL


CHANNEL_GUIDE = """【各渠道高转化文案特征（基于历史4848条数据分析）】
企微1v1（基准CTR 2.62%，GC转化率 18.5%）：
- 高CTR标题短(15字)、98%含利益点("领券""免费""任务")、内容1行、触达偏精准(median 1.3万)
- 低CTR标题长(17字)、仅5%含利益点、直接报价格("39.9元任选5")
APP Push（基准CTR 0.31%，GC转化率 69.5%）：
- 高CTR标题短(16字)、情感化("暖冬""一年一度""回归")、触达量大(median 9.4万)
- 低CTR标题长(15字)、产品描述型("鳞魂炸鸡""超满足4件套")
微信小程序订阅消息（基准CTR 4.01%，GC转化率 41.0%）：
- 高CTR标题极短(9字)、44%含利益点、直接说优惠("3元脆薯饼券")
- 低CTR标题11字、仅7%含利益点、报套餐价("22.9元堡卷小食套餐")
短信（基准CTR 0.53%，GC转化率 26.7%）：
- 高CTR偏提醒型("核销提醒""用券提醒")
- 低CTR偏拉新型("早餐9.9拉新")"""


def build_analysis_prompt(items: list) -> str:
    """构建批量分析 prompt"""
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(
            f"【{i}】标题：{item['标题']}"
            f"｜正文：{item['内容']}"
            f"｜渠道：{item['渠道']}"
            f"｜触达：{item['触达成功']}"
            f"｜点击：{item['点击人次']}"
            f"｜CTR：{item['CTR']:.2f}%"
            f"｜GC：{item['订单GC']}"
            f"｜GC转化率：{item['订单GC转化率']:.2f}%"
            f"｜综合评分：{item['综合评分']:.2f}"
            f"｜排名：第{item['排名']}名"
        )

    return f"""你是麦当劳中国内容营销分析专家。请对以下内容逐条分析。

每条内容请输出：
- "rank_factor": 排名核心归因（15字内，如"标题CTA强+高转化"或"触达低拉低总分"）
- "highlight": 亮点（15字内）
- "weakness": 短板（15字内）
- "suggestion": 改进建议（30字内，含标题和正文建议，参考该渠道高转化特征）

{CHANNEL_GUIDE}

严格输出 JSON 数组，不要其他文字。共{len(items)}条：
{chr(10).join(lines)}"""


def call_llm(api_key: str, provider: str, model: str, prompt: str) -> list:
    """调用 LLM API 并返回解析后的结果"""
    provider_config = API_PROVIDERS.get(provider)
    if not provider_config:
        return []

    base_url = provider_config["base_url"]
    client = openai.OpenAI(api_key=api_key, base_url=base_url) if base_url else openai.OpenAI(api_key=api_key)

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )
    raw = resp.choices[0].message.content.strip()

    # 清理 markdown 代码块
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # 尝试提取 JSON 数组
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 如果解析失败，尝试逐行解析
        try:
            # 尝试修复常见的 JSON 格式问题
            raw = raw.replace("'", '"')  # 单引号替换为双引号
            raw = re.sub(r',\s*}', '}', raw)  # 移除末尾逗号
            raw = re.sub(r',\s*]', ']', raw)  # 移除数组末尾逗号
            return json.loads(raw)
        except:
            return None


def analyze_content(api_key: str, provider: str, model: str, items: list) -> list:
    """批量分析内容，返回结构化结果列表"""
    if not api_key:
        return [{"error": "请先填写 API Key"}] * len(items)

    prompt = build_analysis_prompt(items)

    try:
        results = call_llm(api_key, provider, model, prompt)
        if results is None:
            return [{"error": "AI 返回内容解析失败，请重试"}] * len(items)
        if not isinstance(results, list):
            results = [results]
        # 补齐或截断
        default = {"rank_factor": "—", "highlight": "—", "weakness": "—", "suggestion": "—"}
        results = (results + [default] * len(items))[:len(items)]
        for r in results:
            for k, v in default.items():
                r.setdefault(k, v)
        return results
    except Exception as e:
        return [{"error": f"API调用失败: {str(e)[:80]}"}] * len(items)


# ═══════════════════════════════════════════════════════════════
# AI 总结分析功能
# ═══════════════════════════════════════════════════════════════

def aggregate_channel_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按渠道聚合数据"""
    if df.empty:
        return pd.DataFrame()

    agg = df.groupby('渠道').agg(
        触达=('触达成功', 'sum'),
        点击=('点击人次', 'sum'),
        GC=('订单GC', 'sum'),
        计划数量=('综合评分', 'size')
    ).reset_index()

    agg['CTR'] = (agg['点击'] / agg['触达'] * 100).replace([float('inf'), float('-inf')], 0).round(2).fillna(0)
    agg['GC转化率'] = (agg['GC'] / agg['点击'] * 100).replace([float('inf'), float('-inf')], 0).round(2).fillna(0)

    return agg


def aggregate_bu_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按 BU 聚合数据"""
    if df.empty or OWNER_COL not in df.columns:
        return pd.DataFrame()

    agg = df.groupby(OWNER_COL).agg(
        计划数量=('综合评分', 'size'),
        触达=('触达成功', 'sum'),
        点击=('点击人次', 'sum'),
        GC=('订单GC', 'sum'),
        均值综合评分=('综合评分', 'mean')
    ).reset_index()

    agg['CTR'] = (agg['点击'] / agg['触达'] * 100).replace([float('inf'), float('-inf')], 0).round(2).fillna(0)
    agg['GC转化率'] = (agg['GC'] / agg['点击'] * 100).replace([float('inf'), float('-inf')], 0).round(2).fillna(0)

    return agg


def format_channel_stats_for_prompt(stats: pd.DataFrame, historical_stats: pd.DataFrame = None) -> str:
    """格式化渠道数据为 prompt 文本"""
    lines = []

    if historical_stats is not None and not historical_stats.empty:
        lines.append("【当前周期渠道数据】")
    for _, row in stats.iterrows():
        line = f"- {row['渠道']}：计划 {row['计划数量']}个，触达 {row['触达']}，点击 {row['点击']}，CTR {row['CTR']}%，GC转化率 {row['GC转化率']}%"
        if historical_stats is not None and not historical_stats.empty:
            hist = historical_stats[historical_stats['渠道'] == row['渠道']]
            if not hist.empty:
                hist_row = hist.iloc[0]
                ctr_diff = row['CTR'] - hist_row['CTR']
                reach_diff = row['触达'] - hist_row['触达']
                click_diff = row['点击'] - hist_row['点击']
                line += f"（CTR较上期{'+' if ctr_diff >= 0 else ''}{ctr_diff:.2f}%，触达{'+' if reach_diff >= 0 else ''}{reach_diff}，点击{'+' if click_diff >= 0 else ''}{click_diff}）"
        lines.append(line)

    if historical_stats is not None and not historical_stats.empty:
        lines.append("")
        lines.append("【上周期渠道数据】")
        for _, row in historical_stats.iterrows():
            lines.append(f"- {row['渠道']}：计划 {row['计划数量']}个，触达 {row['触达']}，点击 {row['点击']}，CTR {row['CTR']}%，GC转化率 {row['GC转化率']}%")

    return "\n".join(lines)


def format_bu_stats_for_prompt(stats: pd.DataFrame, historical_stats: pd.DataFrame = None) -> str:
    """格式化 BU 数据为 prompt 文本"""
    lines = []

    if historical_stats is not None and not historical_stats.empty:
        lines.append("【当前周期 BU 数据】")
    for _, row in stats.iterrows():
        line = f"- {row[OWNER_COL]}：计划 {row['计划数量']}个，触达 {row['触达']}，点击 {row['点击']}，CTR {row['CTR']}%，GC转化率 {row['GC转化率']}%，均值评分 {row['均值综合评分']:.2f}"
        if historical_stats is not None and not historical_stats.empty:
            hist = historical_stats[historical_stats[OWNER_COL] == row[OWNER_COL]]
            if not hist.empty:
                hist_row = hist.iloc[0]
                ctr_diff = row['CTR'] - hist_row['CTR']
                reach_diff = row['触达'] - hist_row['触达']
                click_diff = row['点击'] - hist_row['点击']
                line += f"（CTR较上期{'+' if ctr_diff >= 0 else ''}{ctr_diff:.2f}%，触达{'+' if reach_diff >= 0 else ''}{reach_diff}，点击{'+' if click_diff >= 0 else ''}{click_diff}）"
        lines.append(line)

    if historical_stats is not None and not historical_stats.empty:
        lines.append("")
        lines.append("【上周期 BU 数据】")
        for _, row in historical_stats.iterrows():
            lines.append(f"- {row[OWNER_COL]}：计划 {row['计划数量']}个，触达 {row['触达']}，点击 {row['点击']}，CTR {row['CTR']}%，GC转化率 {row['GC转化率']}%，均值评分 {row['均值综合评分']:.2f}")

    return "\n".join(lines)


def build_summary_prompt(channel_stats: pd.DataFrame, bu_stats: pd.DataFrame,
                         historical_channel: pd.DataFrame = None,
                         historical_bu: pd.DataFrame = None) -> str:
    """构建总结分析 prompt"""

    channel_data = format_channel_stats_for_prompt(channel_stats, historical_channel)
    bu_data = format_bu_stats_for_prompt(bu_stats, historical_bu)

    return f"""基于以下数据，用markdown格式输出分析结果，不要输出总标题。

渠道数据：
{channel_data}

BU数据：
{bu_data}

要求：
1. 渠道总结：概况+表格(渠道/触达/点击/CTR/较上期变化)+好差分析
2. BU总结：概况+表格(BU/计划数/触达/点击/CTR/较上期变化)+好差分析（简单概括即可）
3. 有上期数据时计算涨跌，用+/-表示
4. 不要编造数据，直接开始分析"""


def call_llm_text(api_key: str, provider: str, model: str, prompt: str) -> str:
    """调用 LLM API 并返回文本结果"""
    provider_config = API_PROVIDERS.get(provider)
    if not provider_config:
        return "错误：未找到对应的 API 配置"

    base_url = provider_config["base_url"]
    client = openai.OpenAI(api_key=api_key, base_url=base_url) if base_url else openai.OpenAI(api_key=api_key)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        result = resp.choices[0].message.content.strip()
        if not result:
            return "AI 返回了空内容，请稍后重试"
        return result
    except Exception as e:
        return f"API调用失败: {str(e)}"


def analyze_summary(api_key: str, provider: str, model: str,
                    channel_stats: pd.DataFrame, bu_stats: pd.DataFrame,
                    historical_channel: pd.DataFrame = None,
                    historical_bu: pd.DataFrame = None) -> str:
    """调用 AI 进行总结分析"""
    if not api_key:
        return "请先填写 API Key"

    prompt = build_summary_prompt(
        channel_stats, bu_stats, historical_channel, historical_bu
    )

    return call_llm_text(api_key, provider, model, prompt)
