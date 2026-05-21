"""
config.py - 麦当劳内容排行榜：全局配置与常量
"""

# ═══════════════════════════════════════════════════════════════
# CTR/GC 分段函数阈值配置
#   - Q3 阈值 = 75th percentile，来自全量数据统计
#   - 校准：使 Q3 得分 = 100
#   - 公式: G < C → score = 100 × (G/C)^EXP; G >= C → score = 100
# ═══════════════════════════════════════════════════════════════

# CTR 阈值配置 (单位: 百分比%，如 0.31 = 0.31% CTR)
CTR_THRESHOLDS = {
    "APP Push": 0.31,
    "企微1v1": 2.62,
    "微信小程序订阅消息": 4.01,
    "短信": 0.53,
}

# GC 阈值配置 (单位: 百分比，如 69.5 = 69.5%)
GC_THRESHOLDS = {
    "APP Push": 69.5,
    "企微1v1": 18.5,
    "微信小程序订阅消息": 41.0,
    "短信": 26.7,
}

# 未知渠道 fallback Q3 (来自全量 CTR/GC 统计)
CTR_UNKNOWN_THRESHOLD = 2.85   # 2.85%
GC_UNKNOWN_THRESHOLD = 34.8    # 34.8%

EXP = 1.5  # 幂次：E越大区分度越大（G/threshold^EXP，若 G/threshold=0.5→得分=100×0.5^1.5≈35）

# ─── 品牌色 ─────────────────────────────────────────────────────
MCD_RED = "#DA291C"   # 麦当劳品牌红
MCD_GOLD = "#FFC000"
MCD_GREEN = "#00A04A"
MCD_BG = "#FAFAFA"

# ─── 列名常量 ──────────────────────────────────────────────────
OWNER_COL = "预算owner"

# ─── API 配置 ──────────────────────────────────────────────────
API_PROVIDERS = {
    "百度千帆": {
        "base_url": "https://qianfan.baidubce.com/v2/coding",
        "models": ["qianfan-code-latest"],
    },
    "SiliconFlow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["deepseek-ai/DeepSeek-V3-0324", "Qwen/Qwen2.5-72B-Instruct"],
    },
    "OpenAI": {
        "base_url": None,
        "models": ["gpt-4o-mini", "gpt-4o"],
    },
}

PAGE_SIZE = 20
