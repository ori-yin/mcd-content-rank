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


def aggregate_bu_stats(df: pd.DataFrame) -> pd.DataFrame:
    """按 BU 聚合数据"""
    if df.empty or OWNER_COL not in df.columns:
        return pd.DataFrame()

    agg = df.groupby(OWNER_COL).agg(
        计划数量=_plan_count_metric(df),
        触达=('触达成功', 'sum'),
        点击=('点击人次', 'sum'),
        点击后下单=('点击后下单人次', 'sum'),
        订单GC=('订单GC', 'sum'),
        均值综合评分=('综合评分', 'mean')
    ).reset_index()

    agg['CTR'] = safe_pct_rate(agg['点击'], agg['触达'])
    agg['下单转化'] = safe_pct_rate(agg['点击后下单'], agg['点击'])

    return agg


def format_channel_stats_for_prompt(stats: pd.DataFrame, historical_stats: pd.DataFrame = None,
                                     current_period: tuple = None, historical_period: tuple = None) -> str:
    """格式化渠道数据为 prompt 文本（2026-08-03 v3：双段式 + 日期）"""
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
    hist_label = _fmt_period(historical_period)

    lines = [f"【现期渠道数据 · {cur_label}】"]
    for _, row in stats.iterrows():
        gc_val = int(row.get("订单GC", 0) or 0)
        sales_val = float(row.get("订单Sales", 0) or 0)
        lines.append(
            f"- {row['渠道']}：计划 {int(row['计划数量'])}个，"
            f"触达 {int(row['触达']):,}，点击 {int(row['点击']):,}，"
            f"CTR {float(row['CTR']):.2f}%，下单转化率 {float(row['下单转化']):.2f}%，"
            f"GC {gc_val:,}，Sales {int(sales_val):,}"
        )

    if historical_stats is not None and not historical_stats.empty:
        lines.append("")
        lines.append(f"【基期渠道数据 · {hist_label}】")
        for _, row in historical_stats.iterrows():
            gc_val = int(row.get("订单GC", 0) or 0)
            sales_val = float(row.get("订单Sales", 0) or 0)
            lines.append(
                f"- {row['渠道']}：计划 {int(row['计划数量'])}个，"
                f"触达 {int(row['触达']):,}，点击 {int(row['点击']):,}，"
                f"CTR {float(row['CTR']):.2f}%，下单转化率 {float(row['下单转化']):.2f}%，"
                f"GC {gc_val:,}，Sales {int(sales_val):,}"
            )

    return "\n".join(lines)


def format_bu_stats_for_prompt(stats: pd.DataFrame, historical_stats: pd.DataFrame = None) -> str:
    """格式化 BU 数据为 prompt 文本"""
    lines = []

    if historical_stats is not None and not historical_stats.empty:
        lines.append("【当前周期 BU 数据】")
    for _, row in stats.iterrows():
        line = f"- {row[OWNER_COL]}：计划 {row['计划数量']}个，触达 {row['触达']}，点击 {row['点击']}，CTR {row['CTR']}%，下单转化率 {row['下单转化']}%，均值评分 {row['均值综合评分']:.2f}"
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
            lines.append(f"- {row[OWNER_COL]}：计划 {row['计划数量']}个，触达 {row['触达']}，点击 {row['点击']}，CTR {row['CTR']}%，下单转化率 {row['下单转化']}%，均值评分 {row['均值综合评分']:.2f}")

    return "\n".join(lines)


def format_quantile_baseline(quantiles_df: pd.DataFrame) -> str:
    """把 compute_channel_quantiles 输出拼成渠道基线段。

    每渠道输出 4 个指标（CTR / 触达成功 / GC转化 / 下单转化）的 P5/P25/P50/P75/P95。
    """
    if quantiles_df is None or quantiles_df.empty:
        return "（无渠道基线数据）"

    lines = []
    for ch in quantiles_df.index:
        sub = quantiles_df.loc[ch]
        parts = []
        for metric in ("CTR", "触达成功", "GC转化", "下单转化"):
            if (metric, "p5") in sub.index:
                # 注：MultiIndex 列是 (metric, quantile)，取 scalar 用 [metric, label]
                p5 = sub[(metric, "p5")]
                p50 = sub[(metric, "p50")]
                p95 = sub[(metric, "p95")]
                if metric == "触达成功":
                    parts.append(f"{metric} P5={int(p5):,} P50={int(p50):,} P95={int(p95):,}")
                else:
                    parts.append(f"{metric} P5={p5:.2f}% P50={p50:.2f}% P95={p95:.2f}%")
        if parts:
            lines.append(f"- {ch}：" + " ｜ ".join(parts))
    return "\n".join(lines)


def format_top_per_channel(top_df: pd.DataFrame) -> str:
    """把 top_per_channel 输出拼成"具体 Top 内容"段（v2：含标题+正文）。"""
    if top_df is None or top_df.empty:
        return "（无 Top 内容）"

    lines = []
    for _, r in top_df.iterrows():
        ch = str(r.get("渠道", "—"))
        pid = str(r.get("plan_id", "—"))
        score = float(r.get("综合评分", 0) or 0)
        ctr = float(r.get("CTR", 0) or 0)
        reach = int(r.get("触达成功", 0) or 0)
        click = int(r.get("点击人次", 0) or 0)
        title = str(r.get("标题", "") or r.get("消息标题", "") or "").strip()[:80]
        content = str(r.get("内容", "") or "").strip()[:150]
        lines.append(f"- **{ch}** · plan_id=`{pid}` · 综合评分 {score:.2f} · CTR {ctr:.2f}% · 触达 {reach:,} · 点击 {click:,}")
        if title:
            lines.append(f"  标题：{title}")
        if content:
            lines.append(f"  正文：{content}")
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


def build_summary_prompt(channel_stats: pd.DataFrame, bu_stats: pd.DataFrame,
                         historical_channel: pd.DataFrame = None,
                         historical_bu: pd.DataFrame = None,
                         current_period: tuple = None,
                         historical_period: tuple = None,
                         quantile_baseline: pd.DataFrame = None,
                         top_per_channel_df: pd.DataFrame = None,
                         anomalies_df: pd.DataFrame = None) -> str:
    """构建总结分析 prompt（v4：异常放最前 + Sales 放最后 + 表格只写数字）"""

    from config import CTR_THRESHOLDS, CVR_THRESHOLDS  # 延迟导入避免循环

    channel_data = format_channel_stats_for_prompt(channel_stats, historical_channel,
                                                  current_period, historical_period)
    quantile_text = format_quantile_baseline(quantile_baseline)
    top_text = format_top_per_channel(top_per_channel_df)
    anomalies_text = format_anomalies(anomalies_df)

    # 阈值对照表（双基线：config 阈值 + 5 分位）
    thres_lines = ['【健康度双基线 · 用于好差判定】']
    thres_lines.append("- config 阈值（来自 config.CTR_THRESHOLDS，按渠道设的 Q3 达标线）：")
    for ch, t in CTR_THRESHOLDS.items():
        thres_lines.append(f"  - {ch}：CTR ≥ {t}% 为达标；CTR < {t}% 为不达标")

    def _fmt_period(period):
        if period is None:
            return "未指定"
        s, e = period
        try:
            return f"{s.strftime('%Y-%m-%d')} ~ {e.strftime('%Y-%m-%d')}"
        except Exception:
            return str(period)

    cur = _fmt_period(current_period)
    hist = _fmt_period(historical_period)

    return f"""基于以下数据，用markdown格式输出分析结果。

【字段口径说明】
- 触达 = 触达成功；点击 = 点击人次；CTR = 点击 ÷ 触达 × 100%
- 下单转化率 = 点击后下单人次 ÷ 点击人次 × 100%
- GC = 订单GC；Sales = 订单Sales（元）

【时间口径】
- 现期：{cur}
- 基期：{hist}（用于上下文）

{chr(10).join(thres_lines)}

【5 分位基线（来自上传全量数据按日聚合）】
{quantile_text}

【异常监控（系统检测）】
{anomalies_text}

{channel_data}

要求：
1. 先写 1 段总览（不写标题）：把【现期渠道数据】里所有渠道的 CTR、阈值、达标判断、与基期对比（含具体日期）整合在一段话
2. 接着写 ## 异常监控：1 句结论 + 表格（异常类型 / 渠道 / 日期 / 数量 / 处理建议）
3. Top 内容由系统另起静态表格展示，AI 不要重复写

强约束：
- 渠道基线判定：CTR < config 阈值 = 不达标
- 写"基期对比"必须带具体日期
- 任何"建议推广/调权"必须标注[需A/B验证]
- 不要使用"因为…所以…"因果句式
- 整体 ≤ 350 字"""


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
                    channel_stats: pd.DataFrame, bu_stats: pd.DataFrame,
                    historical_channel: pd.DataFrame = None,
                    historical_bu: pd.DataFrame = None,
                    current_period: tuple = None,
                    historical_period: tuple = None,
                    quantile_baseline: pd.DataFrame = None,
                    top_per_channel_df: pd.DataFrame = None,
                    anomalies_df: pd.DataFrame = None) -> str:
    """调用 AI 进行总结分析（2026-08-03 升级版：透传新参数）"""
    if not api_key:
        return "请先填写 API Key"

    prompt = build_summary_prompt(
        channel_stats, bu_stats,
        historical_channel, historical_bu,
        current_period, historical_period,
        quantile_baseline, top_per_channel_df, anomalies_df,
    )

    return call_llm_text(api_key, provider, model, prompt)
