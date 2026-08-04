"""
llm_service.py - 麦当劳内容排行榜：LLM 内容分析服务
"""

import json
import re
import openai
import pandas as pd
from config import API_PROVIDERS, OWNER_COL
from scoring import safe_pct_rate, _plan_count_metric

# MiniMax 走 Anthropic 协议；非可选依赖，未安装时降级为返回错误
try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


# 注：本组定性特征基于历史"订单 GC 转化率"分析；2026-07 切换"下单转化率"后需复测。
# 注：本组特征仅描述历史样本的字面规律，不做因果归因；不可作为内容优劣的已证实结论。
CHANNEL_GUIDE = """【各渠道高转化文案特征（基于历史4848条数据分析）】
企微1v1（基准CTR 2.62%，下单转化率 14.29%）：
- 高CTR标题短(15字)、98%含利益点("领券""免费""任务")、内容1行、触达偏精准(median 1.3万)
- 低CTR标题长(17字)、仅5%含利益点、直接报价格("39.9元任选5")
APP Push（基准CTR 0.31%，下单转化率 14.21%）：
- 高CTR标题短(16字)、情感化("暖冬""一年一度""回归")、触达量大(median 9.4万)
- 低CTR标题长(15字)、产品描述型("鳞魂炸鸡""超满足4件套")
微信小程序订阅消息（基准CTR 4.01%，下单转化率 14.34% — 样本不足降级全量 P75）：
- 高CTR标题极短(9字)、44%含利益点、直接说优惠("3元脆薯饼券")
- 低CTR标题11字、仅7%含利益点、报套餐价("22.9元堡卷小食套餐")
短信（基准CTR 0.53%，下单转化率 13.13%）：
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
            f"｜下单转化率：{item['下单转化']:.2f}%"
            f"｜综合评分：{item['综合评分']:.2f}"
            f"｜排名：第{item['排名']}名"
        )

    return f"""你是麦当劳中国内容营销分析专家。请对以下内容逐条分析。

每条内容请输出：
- "rank_factor": 排名核心归因（15字内，如"标题CTA强+高转化"或"触达低拉低总分"）
- "highlight": 亮点（15字内）
- "weakness": 短板（15字内）
- "suggestion": 改进建议（30字内，含标题和正文建议，参考该渠道高转化特征）

分析纪律（必须遵守）：
- 仅基于上述字段做事实描述（如"CTR=0.30%"），不得用"因为…所以…"句式把相关性写成因果
- "rank_factor"和"suggestion"如含因果推断必须标注[假设]；客观指标字段（基于触达/点击/CTR/CVR/评分）保持事实
- 不得推测输入中未提供的人群、发送时段、优惠力度、商品等变量
- 改写类建议须标注[需A/B验证]，不可作为已证实结论推广

{CHANNEL_GUIDE}

严格输出 JSON 数组，不要其他文字。共{len(items)}条：
{chr(10).join(lines)}"""


def call_llm(api_key: str, provider: str, model: str, prompt: str) -> list:
    """调用 LLM API 并返回解析后的结果"""
    provider_config = API_PROVIDERS.get(provider)
    if not provider_config:
        return []

    # MiniMax 走 Anthropic 协议（其他 provider 走 OpenAI 协议）
    if provider == "MiniMax":
        if not _HAS_ANTHROPIC:
            return None
        base_url = provider_config["base_url"]
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=60)
        resp = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        # 过滤 text block 拼成字符串，thinking 块跳过
        text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        raw = "\n".join(text_parts).strip()
        # 走与 OpenAI 路径相同的 JSON 解析
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            try:
                raw = raw.replace("'", '"')
                raw = re.sub(r',\s*}', '}', raw)
                raw = re.sub(r',\s*]', ']', raw)
                return json.loads(raw)
            except:
                return None

    base_url = provider_config["base_url"]
    client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=60) if base_url else openai.OpenAI(api_key=api_key, timeout=60)

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
        点击后下单=('点击后下单人次', 'sum'),
        订单GC=('订单GC', 'sum'),
        计划数量=_plan_count_metric(df),
    ).reset_index()
    if "订单Sales" in df.columns:
        agg["订单Sales"] = df.groupby('渠道')["订单Sales"].sum().values
    else:
        agg["订单Sales"] = 0.0

    agg['CTR'] = safe_pct_rate(agg['点击'], agg['触达'])
    agg['下单转化'] = safe_pct_rate(agg['点击后下单'], agg['点击'])

    return agg


# 渠道显示顺序：硬编码（"全部" 永远在第 1 行；之后是用户指定的 4 个固定渠道；其他渠道随意）
CHANNEL_DISPLAY_ORDER = ["APP Push", "企微1v1", "短信"]


def format_channel_stats_for_prompt(stats: pd.DataFrame,
                                     channel_baseline: pd.DataFrame = None,
                                     current_period: tuple = None) -> str:
    """格式化渠道数据为 prompt 文本（v5：3 模块 + 全部行 + 基期均值/P75）

    行结构：全部（首行）→ APP Push → 企微1v1 → 短信 → 其他渠道（随意）
    每行：渠道｜计划数｜触达成功｜点击人次｜CTR ｜ CTR基期均值 / CTR上四分位
    "全部"行无渠道维度，基期两列显示 "—"
    其他渠道指 stats 中存在但不在 CHANNEL_DISPLAY_ORDER 里的，按 stats 原顺序排在末尾

    channel_baseline 是 scoring.compute_channel_baseline(df) 输出：
    index=渠道，columns=[CTR均值, CTR P75]，全量上传数据按日聚合后的算术平均/P75
    """
    if stats is None or stats.empty:
        return "（无渠道数据）"

    def _fmt_period(period):
        if period is None:
            return "（日期未指定）"
        s, e = period
        try:
            return f"{s.strftime('%Y-%m-%d')} ~ {e.strftime('%Y-%m-%d')}"
        except Exception:
            return str(period)

    cur_label = _fmt_period(current_period)

    def _baseline_for(ch: str):
        if channel_baseline is None or channel_baseline.empty or ch not in channel_baseline.index:
            return "—", "—"
        return f"{float(channel_baseline.loc[ch, 'CTR均值']):.2f}%", f"{float(channel_baseline.loc[ch, 'CTR P75']):.2f}%"

    # 全部行：全渠道总触达/总点击/总 CTR（不是各渠道 CTR 平均）
    total_reach = int(stats["触达"].sum())
    total_click = int(stats["点击"].sum())
    total_plans = int(stats["计划数量"].sum())
    total_ctr = (total_click / total_reach * 100) if total_reach > 0 else 0.0

    lines = []
    all_bm, all_bp = _baseline_for("全部")
    lines.append(
        f"- 全部：计划 {total_plans}个，触达成功 {total_reach:,}，点击人次 {total_click:,}，"
        f"CTR {total_ctr:.2f}% ｜ CTR基期均值 {all_bm} / CTR上四分位 {all_bp}"
    )

    # 各渠道行：按 CHANNEL_DISPLAY_ORDER 优先输出，其余按 stats 原顺序排末尾

    seen = set()
    ordered_lines = []
    others_lines = []
    for _, row in stats.iterrows():
        ch = str(row["渠道"])
        seen.add(ch)
        bm, bp = _baseline_for(ch)
        line = (
            f"- {ch}：计划 {int(row['计划数量'])}个，触达成功 {int(row['触达']):,}，点击人次 {int(row['点击']):,}，"
            f"CTR {float(row['CTR']):.2f}% ｜ "
            f"CTR基期均值 {bm} / CTR上四分位 {bp}"
        )
        if ch in CHANNEL_DISPLAY_ORDER:
            ordered_lines.append(line)
        else:
            others_lines.append(line)

    lines.extend(ordered_lines)
    lines.extend(others_lines)
    return "\n".join(lines)


def format_anomalies(anomalies_df: pd.DataFrame) -> str:
    """把 detect_anomalies 输出拼成"数据质量提示 + 异常明细"两段（已按严重度排序）。"""
    if anomalies_df is None or anomalies_df.empty:
        return "（未发现疑似异常数据）"

    type_label_map = {
        "埋点型": "🔴 埋点异常：触达≥10万且点击=0（最严重）",
        "超低CTR": "🟡 CTR<0.1%且触达≥5千（投放疑似失效）",
        "无转化": "🟠 点击≥200且下单=0（疑似优惠/链接失效）",
        "转化率倒挂": "🔴 转化率倒挂：下单>点击（数据计算错误）",
    }
    summary_lines = []
    for atype, label in type_label_map.items():
        cnt = int((anomalies_df["异常类型"] == atype).sum())
        if cnt > 0:
            summary_lines.append(f"- {label}：{cnt} 条")

    detail_lines = ["【疑似异常明细（按严重度排序）】"]
    for _, r in anomalies_df.iterrows():
        atype = str(r.get("异常类型", "—"))
        ch = str(r.get("渠道", "—"))
        pid = str(r.get("日期", "—"))
        reach = int(r.get("触达", 0) or 0)
        click = int(r.get("点击", 0) or 0)
        order = int(r.get("下单", 0) or 0)
        hint = str(r.get("提示", ""))
        detail_lines.append(
            f"- [{atype}] 渠道={ch}, 日期={pid}, 触达={reach:,}, 点击={click:,}, 下单={order:,}"
        )
        detail_lines.append(f"    建议：{hint}")
    return "\n".join(summary_lines + detail_lines)


def build_summary_prompt(channel_stats: pd.DataFrame,
                         current_period: tuple = None,
                         channel_baseline: pd.DataFrame = None,
                         anomalies_df: pd.DataFrame = None) -> str:
    """构建总结分析 prompt（v5：3 模块 + 渠道基期均值/P75 + AI 只写 2 段）

    AI 输出仅 2 段（整体效果 / 数据异常），Top 3 内容由系统静态渲染，
    AI 不参与。基期 = 全量上传数据按日聚合后的 CTR 算术平均 + P75
    （来自 channel_baseline，对抗小样本噪声）。
    """
    channel_data = format_channel_stats_for_prompt(channel_stats, channel_baseline, current_period)
    anomalies_text = format_anomalies(anomalies_df)

    cur = "未指定"
    if current_period is not None:
        try:
            s, e = current_period
            cur = f"{s.strftime('%Y-%m-%d')} ~ {e.strftime('%Y-%m-%d')}"
        except Exception:
            cur = str(current_period)

    return f"""你是给麦当劳内容运营写周报的助手。给你现期渠道数据，请只输出 2 段：

## 一、整体效果
一句话（≤ 80 字）。结构：
"现期 {cur} 共 N 个渠道 N 个计划，触达成功 X 万次、CTR X%。较基期（上传全量数据按日聚合）：N 个渠道超基期均值 / 达上四分位 / 低于基期均值。"

判断口径（必须用基期两列，不要凭感觉）：
- 现期 CTR ≥ 上四分位 → "达上四分位"
- 上四分位 > 现期 CTR ≥ 基期均值 → "超基期均值"
- 现期 CTR < 基期均值 → "低于基期均值"

## 二、数据异常
1 句结论 + 列出每类异常数量。
- 未发现异常 → 直接写"未发现疑似异常数据"
- 有异常 → "检测到 N 类 X 条疑似异常" + 每类一行"类型：N 条（建议：…）"

---

【字段口径】
- 触达成功 = 触达；点击人次 = 点击；CTR = 点击 ÷ 触达 × 100%
- 下单转化率 = 点击后下单人次 ÷ 点击人次 × 100%

【基期口径】
- 基期 = 上传的全部数据按日聚合（不算术平均外的口径）
- 基期均值 = 各渠道每日 CTR 的算术平均（不被大触达加权）
- 上四分位 = 各渠道每日 CTR 的 P75

【现期渠道数据 · {cur}】
{channel_data}
（每行末尾：CTR基期均值 = 算术平均，CTR上四分位 = P75）

【异常监控（系统检测）】
{anomalies_text}

---

强约束：
- 严格只输出 "## 一、整体效果" 和 "## 二、数据异常" 两段；禁止任何额外标题或段落（包括"修正："、"最终结论："、"总结："等任何追加内容）
- 任何"建议推广/调权"必须标注 [需A/B验证]
- 不要使用"因为…所以…"因果句式，只描述字面规律
- Top 3 内容由系统静态渲染，**你不需要写 Top 3**"""


def call_llm_text(api_key: str, provider: str, model: str, prompt: str) -> str:
    """调用 LLM API 并返回文本结果"""
    provider_config = API_PROVIDERS.get(provider)
    if not provider_config:
        return "错误：未找到对应的 API 配置"

    # MiniMax 走 Anthropic 协议
    if provider == "MiniMax":
        if not _HAS_ANTHROPIC:
            return "错误：未安装 anthropic SDK，无法调用 MiniMax"
        base_url = provider_config["base_url"]
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url, timeout=60)
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            text_parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
            result = "\n".join(text_parts).strip()
            if not result:
                return "AI 返回了空内容，请稍后重试"
            return result
        except Exception as e:
            return f"API调用失败: {str(e)}"

    base_url = provider_config["base_url"]
    client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=60) if base_url else openai.OpenAI(api_key=api_key, timeout=60)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
        )
        result = resp.choices[0].message.content.strip()
        if not result:
            return "AI 返回了空内容，请稍后重试"
        return result
    except Exception as e:
        return f"API调用失败: {str(e)}"


def analyze_summary(api_key: str, provider: str, model: str,
                    channel_stats: pd.DataFrame,
                    current_period: tuple = None,
                    channel_baseline: pd.DataFrame = None,
                    anomalies_df: pd.DataFrame = None) -> str:
    """调用 AI 进行总结分析（v5：3 模块 + 渠道基期 + AI 只写 2 段）"""
    if not api_key:
        return "请先填写 API Key"

    prompt = build_summary_prompt(
        channel_stats,
        current_period,
        channel_baseline, anomalies_df,
    )

    return call_llm_text(api_key, provider, model, prompt)
