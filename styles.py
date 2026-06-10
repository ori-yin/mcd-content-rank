"""
styles.py - 麦当劳内容排行榜：CSS 样式
"""

from config import MCD_RED, MCD_GOLD, MCD_GREEN, MCD_BG


def get_css() -> str:
    return f"""
<style>
  /* ─── 全局字体 ─── */
    html, body, .stApp {{
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif !important;
    background: {MCD_BG};
    color: #1a1a1a;
  }}

  /* ─── 侧边栏：白底，品牌色仅用于交互态 ─── */
  [data-testid="stSidebar"] {{
    background: #FFFFFF !important;
    border-right: 1px solid #E8E8E8;
    border-top: 3px solid {MCD_GOLD};
  }}

  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p {{
    color: #1a1a1a !important;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
  }}

  /* ─── 侧边栏：标签层级 ─── */
  [data-testid="stSidebar"] .stRadio label,
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stTextInput label,
  [data-testid="stSidebar"] .stDateInput label,
  [data-testid="stSidebar"] .stSlider label {{
    color: #666 !important;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.02em;
    margin-bottom: 4px;
  }}

  [data-testid="stSidebar"] hr {{
    border-color: #EFEFEF !important;
    margin: 16px 0;
  }}

  [data-testid="stSidebar"] .stSlider > div {{
    padding: 4px 0;
  }}

  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{
    background: #E8E8E8 !important;
    border-radius: 4px !important;
  }}

  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [aria-valuenow] {{
    background: {MCD_RED} !important;
    border-radius: 4px !important;
  }}

  [data-testid="stSidebar"] .stSelectbox > div > div,
  [data-testid="stSidebar"] .stTextInput > div > div,
  [data-testid="stSidebar"] .stDateInput > div > div {{
    background: #FFFFFF !important;
    border: 1px solid #E0E0E0 !important;
    border-radius: 6px !important;
    color: #1a1a1a !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="select"] span {{
    color: #1a1a1a !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="input"] {{
    color: #1a1a1a !important;
  }}

  [data-testid="stSidebar"] .stDownloadButton > button {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-weight: 600;
    border: none !important;
    border-radius: 6px !important;
  }}

  /* ─── 页面布局 ─── */
  .block-container {{
    padding-top: 2rem;
    padding-left: 2.5rem;
    padding-right: 2.5rem;
    background: {MCD_BG};
  }}

  /* ─── 顶部指标卡 ─── */
  div[data-testid="stMetricValue"] {{
    font-size: 18px !important;
    font-weight: 500 !important;
    color: #504e49 !important;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    letter-spacing: -0.02em;
  }}
  div[data-testid="stMetricLabel"] {{
    font-size: 12px !important;
    color: #999 !important;
    font-weight: 500;
    letter-spacing: 0.02em;
  }}
  div[data-testid="stMetricDelta"] {{
    display: none;
  }}

  /* ─── Tab 栏 ─── */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 0;
    border-bottom: 1px solid #E8E8E8;
  }}
  .stTabs [data-baseweb="tab"] {{
    color: #999 !important;
    font-weight: 500;
    font-size: 14px;
    padding: 10px 20px;
    border-radius: 0;
    border-bottom: 2px solid transparent;
    transition: color 0.15s ease;
  }}
  .stTabs [data-baseweb="tab"]:hover {{
    color: #333 !important;
  }}
  .stTabs [aria-selected="true"] {{
    color: #1a1a1a !important;
    border-bottom: 2px solid {MCD_RED} !important;
    font-weight: 600;
  }}

  /* ─── Header：品牌色在标题，不用色块 ─── */
  .mcd-header {{
    padding: 0 0 16px 0;
    margin-bottom: 24px;
    border-bottom: 1px solid #E8E8E8;
  }}
  .mcd-header h1 {{
    font-size: 20px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.01em;
    color: {MCD_RED};
  }}

  /* ─── 排名徽章 ─── */
  .rank-badge {{
    display: inline-block;
    width: 28px; height: 28px;
    border-radius: 8px;
    text-align: center; line-height: 28px;
    font-weight: 700; font-size: 12px;
    margin-right: 10px;
    border: none;
  }}
  .rank-1 {{
    background: {MCD_GOLD};
    color: #000;
    border-color: transparent;
  }}
  .rank-2 {{
    background: #E8E8E8;
    color: #666;
    border-color: rgba(0,0,0,0.08);
  }}
  .rank-3 {{
    background: #FFC000;
    color: #000;
    border-color: rgba(0,0,0,0.1);
  }}
  .rank-other {{
    background: #F2F2F2;
    color: #AAA;
    border-color: transparent;
  }}

  /* ─── 内容卡片：精致阴影 ─── */
  .content-card {{
    background: #FFFFFF;
    border: 1px solid rgba(0,0,0,0.06);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: all 0.15s ease;
  }}
  .content-card:hover {{
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    border-color: rgba(0,0,0,0.1);
  }}
  .card-title {{
    font-size: 14px;
    font-weight: 600;
    color: #1a1a1a;
    margin-bottom: 6px;
    line-height: 1.6;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }}
  .card-content {{
    font-size: 13px;
    color: #888;
    line-height: 1.7;
    margin-bottom: 14px;
  }}
  .card-meta {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 12px;
    color: #888;
  }}
  .card-meta span {{
    background: #F8F7F5;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: 500;
    border: none;
  }}
  .card-score {{
    font-size: 28px;
    font-weight: 700;
    color: {MCD_RED};
    text-align: right;
    line-height: 1;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    letter-spacing: -0.02em;
  }}
  .card-score-label {{
    font-size: 11px;
    color: #BBB;
    text-align: right;
    font-weight: 400;
    letter-spacing: 0.02em;
    margin-top: 4px;
  }}

  /* ─── 章节标题 ─── */
  .section-title {{
    font-size: 14px;
    font-weight: 600;
    color: #1a1a1a;
    margin: 28px 0 14px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #E8E8E8;
    letter-spacing: -0.01em;
  }}

  /* ─── 数据表格 ─── */
  .stDataFrame thead th {{
    background: #F8F8F8 !important;
    color: #666 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
    border-bottom: 2px solid #E8E8E8 !important;
    padding: 10px 12px !important;
  }}
  .stDataFrame tbody tr:hover {{ background: #FAFAFA !important; }}
  .stDataFrame tbody td {{
    font-size: 13px !important;
    color: #333 !important;
    padding: 9px 12px !important;
    border-color: #F0F0F0 !important;
  }}

  /* ─── 清洗状态提示 ─── */
  .clean-status {{
    background: #FFF8F0;
    border: 1px solid {MCD_GOLD};
    border-left: 4px solid {MCD_GOLD};
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 20px;
    font-size: 13px;
    color: #000000;
    font-weight: 500;
  }}

  /* ─── 副文本 / 说明文字 ─── */
  .stCaption {{
    font-size: 12px !important;
    color: #AAA !important;
  }}

  /* ─── 数字高亮 ─── */
  .stAlert {{
    border-radius: 10px;
  }}

  /* ─── 综合评分 Info Tooltip ─── */
  .score-info-wrap {{
    display: inline-block;
    position: relative;
    vertical-align: middle;
    margin-left: 5px;
    cursor: help;
    line-height: 1;
  }}
  .score-info-wrap .info-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #E0E0E0;
    color: #999;
    font-size: 9px;
    font-weight: 900;
    font-style: normal;
    line-height: 1;
    user-select: none;
    transition: background 0.15s, color 0.15s;
  }}
  .score-info-wrap:hover .info-icon {{
    background: {MCD_RED};
    color: #FFF;
  }}
  .score-tooltip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: calc(100% + 8px);
    right: calc(100% + 10px);
    background: rgba(30, 30, 30, 0.95);
    color: #FFFFFF;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12px;
    white-space: pre-line;
    line-height: 1.6;
    min-width: 220px;
    max-width: 300px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    z-index: 9999;
    pointer-events: none;
    transition: opacity 0.15s ease;
  }}
  .score-tooltip::after {{
    content: '';
    position: absolute;
    top: 100%;
    right: auto;
    left: 100%;
    border: 5px solid transparent;
    border-left-color: rgba(30, 30, 30, 0.95);
  }}
  .score-info-wrap:hover .score-tooltip {{
    visibility: visible;
    opacity: 1;
  }}

  /* ─── AI 分析卡片 ─── */
  .ai-card {{
    background: #FFFFFF;
    border: 1px solid rgba(0,0,0,0.06);
    border-left: 3px solid {MCD_GOLD};
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .ai-card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }}
  .ai-card-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
  }}
  .ai-badge {{
    display: inline-block;
    background: {MCD_RED};
    color: #FFF;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    letter-spacing: 0.05em;
  }}
  .ai-tag {{
    display: inline-block;
    background: #F8F7F5;
    color: #666;
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 6px;
    margin-right: 6px;
    margin-bottom: 4px;
    border: none;
    font-weight: 500;
  }}
  .ai-tag-label {{
    color: #999;
    font-size: 11px;
    margin-right: 3px;
  }}
  .ai-highlight {{
    color: {MCD_GREEN};
    font-weight: 600;
  }}
  .ai-weakness {{
    color: {MCD_RED};
    font-weight: 600;
  }}
  .ai-suggestion {{
    background: #FFF8F0;
    border: 1px solid #FFE0B2;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: #333;
    margin-top: 8px;
  }}

  /* ─── 卡片 AI 标签按钮 ─── */
  .ai-tag-btn {{
    background: #FFF0F0;
    color: {MCD_RED};
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid #FFDADA;
    cursor: default;
    transition: all 0.15s ease;
  }}
  .ai-tag-btn:hover {{
    background: {MCD_RED};
    color: #FFFFFF;
    border-color: {MCD_RED};
  }}

  /* ─── AI 解读 hover tooltip ─── */
  .ai-has-tip {{
    position: relative;
    cursor: help;
  }}
  .ai-tip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: calc(100% + 10px);
    left: 50%;
    transform: translateX(-50%);
    background: rgba(30, 30, 30, 0.95);
    color: #FFFFFF;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 12px;
    font-weight: 400;
    line-height: 1.8;
    white-space: normal;
    min-width: 260px;
    max-width: 360px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    z-index: 9999;
    pointer-events: none;
    transition: opacity 0.15s ease;
  }}
  .ai-tip::after {{
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: rgba(30, 30, 30, 0.95);
  }}
  .ai-has-tip:hover .ai-tip {{
    visibility: visible;
    opacity: 1;
  }}
  .ai-has-tip:hover {{
    background: {MCD_RED};
    color: #FFFFFF;
    border-color: {MCD_RED};
  }}

  /* ─── 隐藏 API Key 密码小眼睛 ─── */
  [data-testid="stTextInputVisibilityToggle"] {{
    display: none !important;
  }}

  /* ─── 按钮加载动画 ─── */
  @keyframes mcd-pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.5; }}
  }}
  .stButton > button[data-testid="stBaseButton-primary"]:disabled {{
    animation: mcd-pulse 1.2s ease-in-out infinite;
    background: {MCD_RED} !important;
    color: #FFF !important;
  }}

</style>
"""
