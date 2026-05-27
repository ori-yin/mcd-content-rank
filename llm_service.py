"""
llm_service.py - 麦当劳内容排行榜：LLM 内容分析服务
"""

import json
import re
import openai
from config import API_PROVIDERS


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
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def analyze_content(api_key: str, provider: str, model: str, items: list) -> list:
    """批量分析内容，返回结构化结果列表"""
    if not api_key:
        return [{"error": "请先填写 API Key"}] * len(items)

    prompt = build_analysis_prompt(items)

    try:
        results = call_llm(api_key, provider, model, prompt)
        if not isinstance(results, list):
            results = [results]
        # 补齐或截断
        default = {"rank_factor": "—", "highlight": "—", "weakness": "—", "suggestion": "—"}
        results = (results + [default] * len(items))[:len(items)]
        for r in results:
            for k, v in default.items():
                r.setdefault(k, v)
        return results
    except json.JSONDecodeError as e:
        return [{"error": f"JSON解析失败: {str(e)[:50]}"}] * len(items)
    except Exception as e:
        return [{"error": f"API调用失败: {str(e)[:80]}"}] * len(items)
