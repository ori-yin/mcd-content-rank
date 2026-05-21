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

  /* ─── Streamlit 顶部导航条 ─── */
  .st-emotion-cache-1kyxreq {{
    background: {MCD_GOLD} !important;
  }}

  /* ─── 侧边栏：金色主题 ─── */
  [data-testid="stSidebar"] {{
    background: {MCD_GOLD} !important;
    border-right: 3px solid rgba(0,0,0,0.08);

  }}

  /* ─── 文件上传区：统一左右两侧边框 ─── */
  [data-testid="stSidebar"] [data-testid="stRadio"] > div {{
    border: 1px solid rgba(0,0,0,0.15) !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
    background: rgba(255,255,255,0.6) !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploader"] > div > div {{
    border: 1px solid rgba(0,0,0,0.15) !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
    background: rgba(255,255,255,0.6) !important;
  }}

  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p {{
    color: #000000 !important;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
  }}

  /* ─── 侧边栏：弱化数据类型和上传文件标签 ─── */
  [data-testid="stSidebar"] [data-testid="stRadio"] label,
  [data-testid="stSidebar"] [data-testid="stFileUploader"] label {{
    color: #999 !important;
    font-weight: 300 !important;
    font-size: 10px !important;
    letter-spacing: 0.02em;
  }}

  /* ─── 侧边栏：其他标签保持正常 ─── */
  [data-testid="stSidebar"] .stRadio label,
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stTextInput label,
  [data-testid="stSidebar"] .stDateInput label,
  [data-testid="stSidebar"] .stSlider label {{
    color: #000000 !important;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 4px;
  }}

  [data-testid="stSidebar"] hr {{
    border-color: rgba(0,0,0,0.15) !important;
    margin: 12px 0;
  }}

  [data-testid="stSidebar"] .stSlider > div {{
    padding: 4px 0;
  }}

  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {{
    background: rgba(255,255,255,0.5) !important;
    border-radius: 6px !important;

  }}

  [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [aria-valuenow] {{
    background: {MCD_RED} !important;
    border-radius: 6px !important;

  }}

  [data-testid="stSidebar"] .stSelectbox > div > div,
  [data-testid="stSidebar"] .stTextInput > div > div,
  [data-testid="stSidebar"] .stDateInput > div > div {{
    background: rgba(255,255,255,0.6) !important;
    border: 1px solid rgba(0,0,0,0.12) !important;
    border-radius: 10px !important;
    color: #000000 !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="select"] span {{
    color: #000000 !important;
  }}

  [data-testid="stSidebar"] [data-baseweb="input"] {{
    color: #000000 !important;
  }}

  [data-testid="stSidebar"] .stDownloadButton > button {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-weight: 700;
    border: none !important;
    border-radius: 10px !important;
  }}

  /* ─── 页面布局 ─── */
  .block-container {{
    padding-top: 1.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
    background: {MCD_BG};
  }}

  /* ─── 顶部指标卡（弱化：小字+中灰）─── */
  div[data-testid="stMetricValue"] {{
    font-size: 14px !important;
    font-weight: 300 !important;
    color: #999 !important;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    letter-spacing: 0;
  }}
  div[data-testid="stMetricLabel"] {{
    font-size: 10px !important;
    color: #BBB !important;
    font-weight: 300;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }}
  div[data-testid="stMetricDelta"] {{
    display: none;
  }}

  /* ─── Tab 栏 ─── */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 2px solid #EFEFEF;
  }}
  .stTabs [data-baseweb="tab"] {{
    color: #888 !important;
    font-weight: 600;
    font-size: 14px;
    padding: 8px 16px;
    border-radius: 8px 8px 0 0;
    border-bottom: 3px solid transparent;
    transition: all 0.15s ease;
  }}
  .stTabs [data-baseweb="tab"]:hover {{
    color: {MCD_RED} !important;
  }}
  .stTabs [aria-selected="true"] {{
    color: {MCD_RED} !important;
    border-bottom: 3px solid {MCD_RED} !important;
    font-weight: 700;
  }}

  /* ─── 主标题卡片 ─── */
  .mcd-header {{
    background: {MCD_RED};
    border-radius: 16px;
    padding: 28px 36px;
    color: #FFFFFF;
    margin-bottom: 24px;
    border-left: 6px solid {MCD_GOLD};
  }}
  .mcd-header h1 {{
    font-size: 22px;
    font-weight: 900;
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
    color: #FFFFFF;
  }}
  .mcd-header p {{
    font-size: 13px;
    opacity: 1;
    margin: 0;
    font-weight: 500;
    color: #FFFFFF;
  }}

  /* ─── 排名徽章 ─── */
  .rank-badge {{
    display: inline-block;
    width: 30px; height: 30px;
    border-radius: 50%;
    text-align: center; line-height: 30px;
    font-weight: 900; font-size: 13px;
    margin-right: 8px;
    border: 2px solid transparent;
  }}
  .rank-1 {{
    background: {MCD_GOLD};
    color: {MCD_RED};
    border-color: rgba(255,255,255,0.5);
    box-shadow: 0 2px 8px rgba(255,188,13,0.5);
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

  /* ─── 内容卡片 ─── */
  .content-card {{
    background: #FFFFFF;
    border: 1px solid #EFEFEF;
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
  }}
  .content-card:hover {{
    box-shadow: 0 4px 20px rgba(228,0,4, 0.12);
    transform: translateY(-1px);
  }}
  .card-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 6px;
    line-height: 1.5;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }}
  .card-content {{
    font-size: 13px;
    color: #666;
    line-height: 1.7;
    margin-bottom: 12px;
  }}
  .card-meta {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 12px;
    color: #888;
  }}
  .card-meta span {{
    background: #F8F8F8;
    padding: 4px 10px;
    border-radius: 20px;
    font-weight: 500;
    border: 1px solid #EFEFEF;
  }}
  .card-score {{
    font-size: 26px;
    font-weight: 900;
    color: {MCD_RED};
    text-align: right;
    line-height: 1;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }}
  .card-score-label {{
    font-size: 10px;
    color: #CCC;
    text-align: right;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  /* ─── 章节标题 ─── */
  .section-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin: 28px 0 14px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid {MCD_RED};
    letter-spacing: -0.01em;
  }}

  /* ─── 数据表格 ─── */
  .stDataFrame thead th {{
    background: {MCD_RED} !important;
    color: #FFFFFF !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em;
    border: none !important;
    padding: 10px 12px !important;
  }}
  .stDataFrame tbody tr:hover {{ background: rgba(228,0,4, 0.04) !important; }}
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

</style>
"""
