"""
config.py - 麦当劳内容排行榜：全局配置与常量
"""

# ═══════════════════════════════════════════════════════════════
# CTR/CVR 分段函数阈值配置
#   - Q3 阈值 = 75th percentile，来自全量数据统计
#   - 校准：使 Q3 得分 = 100
#   - 公式: G < C → score = 100 × (G/C)^EXP; G >= C → score = 100
# ═══════════════════════════════════════════════════════════════

# CTR 阈值配置 (单位: 百分比%，如 0.28 = 0.28% CTR)
# 2026-07-17 校准（APP Push 用"稳定 P75"，仅看触达≥5000 的样本，排除小样本噪声）
CTR_THRESHOLDS = {
    "APP Push": 0.23,   # 稳定 P75 (触达≥5000)，原 0.28% 偏高
    "企微1v1": 1.12,    # P50 而非 P75
    "微信小程序订阅消息": 4.09,
    "短信": 0.44,
}

# CVR 阈值配置 (单位: %，下单转化 = 点击后下单 ÷ 点击 × 100)
# APP Push 用稳定 P75 (触达≥5000)
CVR_THRESHOLDS = {
    "APP Push": 21.35,  # 稳定 P75 (触达≥5000)
    "企微1v1": 9.09,    # P50 而非 P75
    "微信小程序订阅消息": 26.81,
    "短信": 20.00,
}

# 未知渠道 fallback Q3 (2026 全量 P75)
CTR_UNKNOWN_THRESHOLD = 2.45   # 2.45%
CVR_UNKNOWN_THRESHOLD = 20.31   # 20.31%

EXP = 1.5  # 幂次：值/Q3 < 1 时用此指数（标准 1.5，sub-Q3 内容更严，逼近 Q3 时快速上涨）

# ─── 品牌色 ─────────────────────────────────────────────────────
MCD_RED = "#DA291C"   # 麦当劳品牌红
MCD_GOLD = "#FFC000"
MCD_GREEN = "#00A04A"
MCD_BG = "#FAFAFA"

# ─── 配色主题 ──────────────────────────────────────────────────
# 每个主题额外包含 score_high / score_med / score_low 三档分数色
THEMES = {
    "经典红金": {
        "bg": "#FAFAFA", "sidebar_bg": "#FFFFFF", "card_bg": "#FFFFFF",
        "text": "#1a1a1a", "text_sub": "#666", "text_muted": "#999",
        "border": "#E8E8E8", "accent": "#DA291C", "gold": "#FFC000",
        "score_high": "#00A04A", "score_med": "#FFC000", "score_low": "#DA291C",
    },
    "暖羊皮纸": {
        "bg": "#f5f4ed", "sidebar_bg": "#faf9f5", "card_bg": "#faf9f5",
        "text": "#141413", "text_sub": "#504e49", "text_muted": "#6b6a64",
        "border": "#e8e6dc", "accent": "#DA291C", "gold": "#C79200",
        "score_high": "#5C8A4F", "score_med": "#C79200", "score_low": "#B82015",
    },
    "赤陶暖橙": {
        "bg": "#F6EFE6", "sidebar_bg": "#FFFAF5", "card_bg": "#FFFFFF",
        "text": "#1A1918", "text_sub": "#6B6560", "text_muted": "#8B867E",
        "border": "#E5DDD4", "accent": "#D97757", "gold": "#C79200",
        "score_high": "#5C8A4F", "score_med": "#C79200", "score_low": "#B85447",
    },
    "冷调蓝灰": {
        "bg": "#0E1620", "sidebar_bg": "#131C28", "card_bg": "#17222E",
        "text": "#E8EEF5", "text_sub": "#A0B0C0", "text_muted": "#7A8A9B",
        "border": "#2A3A4A", "accent": "#5A8CB8", "gold": "#5A8CB8",
        "score_high": "#6FB58A", "score_med": "#C8D8E8", "score_low": "#B07080",
    },
    "森绿": {
        "bg": "#F5F0EB", "sidebar_bg": "#FAF7F3", "card_bg": "#FFFFFF",
        "text": "#2D3436", "text_sub": "#6D685F", "text_muted": "#9A958D",
        "border": "#D8D4CE", "accent": "#6B8F71", "gold": "#6B8F71",
        "score_high": "#5C8A4F", "score_med": "#8FA68E", "score_low": "#B85447",
    },
    "暗色": {
        "bg": "#1a1a1a", "sidebar_bg": "#222222", "card_bg": "#2a2a2a",
        "text": "#e8e6dc", "text_sub": "#b5b3aa", "text_muted": "#8a8880",
        "border": "#3a3a3a", "accent": "#DA291C", "gold": "#C79200",
        "score_high": "#6FB58A", "score_med": "#C79200", "score_low": "#E66B5C",
    },
    "极简黑白": {
        "bg": "#FFFFFF", "sidebar_bg": "#FAFAFA", "card_bg": "#FFFFFF",
        "text": "#000000", "text_sub": "#555555", "text_muted": "#888888",
        "border": "#E0E0E0", "accent": "#000000", "gold": "#000000",
        "score_high": "#000000", "score_med": "#888888", "score_low": "#BBBBBB",
    },
}

# ─── 列名常量 ──────────────────────────────────────────────────
# 注：data_cleaning._map_columns 把 "预算owner"/"owner"/"bu" 等统一 rename 成 "owner"
# 所以这里必须用 "owner"，否则 app.py 的侧栏/BU tab/AI 总结都查不到列
OWNER_COL = "owner"

# ─── API 配置 ──────────────────────────────────────────────────
API_PROVIDERS = {
    "火山方舟": {
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "models": ["minimax-m3", "deepseek-v4-flash", "GLM-5.2"],
        # 占位/虚拟 api_key — 真实值请走 .streamlit/secrets.toml 或环境变量
        "api_key": "k-897605b4-831b-494a-9e2e-d477d6b17158-fb2d1",
    },
    "百度千帆": {
        "base_url": "https://qianfan.baidubce.com/v2/coding",
        "models": ["qianfan-code-latest"],
        # 占位/虚拟 api_key — 真实值请走 .streamlit/secrets.toml 或环境变量
        "api_key": "ce-v3/ALTAKSP-QmNPHghHzqzyoxZMVnzVo/c6b429d64ddc09c0c24d2c61a79ab30d1f1f5a55",
    },
    "麦当劳AI网关": {
        "base_url": "https://ai-gateway-test.mcdchina.net/v1",
        "models": ["gemini-3-flash-preview", "gemini-3-pro-image-preview", "deepseek-v3", "claude-sonnet-4.6", "claude-haiku-4.5"],
        "api_key": "",
    },
    "SiliconFlow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["deepseek-ai/DeepSeek-V3-0324", "Qwen/Qwen2.5-72B-Instruct"],
        "api_key": "",
    },
    "OpenAI": {
        "base_url": None,
        "models": ["gpt-4o-mini", "gpt-4o"],
        "api_key": "",
    },
}

# ─── 默认权重 ──────────────────────────────────────────────────
DEFAULT_W_REACH = 0.25
DEFAULT_W_CTR = 0.55
DEFAULT_W_GC = 0.20

PAGE_SIZE = 10
