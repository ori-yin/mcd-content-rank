# 麦当劳内容排行榜

Streamlit Web 应用：上传 CSV 数据后对内容按综合评分排名，展示卡片式排行榜。

## 功能

- 支持原始 CSV（含 JSON 列自动清洗）和已清洗 CSV
- 综合评分算法：触达分(25%) + CTR分(50%) + 下单转化率分(25%)，含置信度惩戒
- 日期范围 / 计划类型 / 渠道 / 预算Owner 多维筛选
- 卡片排行榜（分页，每页50条）+ 数据表格 + 算法说明
- 权重可调，排序可切换
- CSV 一键下载
- LLM AI 内容分析（支持百度千帆、麦当劳AI网关、SiliconFlow、OpenAI）

## 评分算法

- CTR/下单转化率 分段评分：以各渠道 Q3 为阈值，达到 Q3 = 100分，低于 Q3 按幂次(1.5)打分
- 触达分：幂次归一化 (触达/最大触达)^0.3 * 100
- 置信度惩戒：触达<100 x0.1 / <500 x0.3 / <1000 x0.5 / <5000 x0.8 / >=5000 x1.0

详见 [内容排行榜评分算法-文档.html](内容排行榜评分算法-文档.html)

## 列名要求（CSV）

发送日期 | 计划类型 | 渠道 | 触达成功 | 点击人次 | 点击后下单人次 | 订单GC | 订单Sales | 标题 | 内容 | 预算owner

## 快速开始（本地运行）

### 前置条件

- Python 3.11+（[下载地址](https://www.python.org/downloads/)）

### 一键启动（Windows）

双击 `setup_and_run.bat`，脚本会自动：
1. 创建虚拟环境（继承系统已有库，已装过的不会重复下载）
2. 检查并安装缺失依赖（使用国内镜像，无需翻墙）
3. 启动 Streamlit 应用，浏览器自动打开

### 手动启动

```bash
# 克隆仓库
git clone https://github.com/ori-yin/mcd-content-rank.git
cd mcd-content-rank

# 创建虚拟环境
python -m venv --system-site-packages venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 安装依赖
pip install -r requirements.txt

# 启动
streamlit run app.py
```

浏览器访问 http://localhost:8501

## 依赖

```
streamlit>=1.40.0
pandas>=2.0.0
numpy>=1.24.0
openai>=1.0.0
openpyxl>=3.1.0
```

## 在线部署

https://ori-yin-mcd-content-rank.streamlit.app

## 项目结构

```
├── app.py                      # Streamlit 主入口
├── config.py                   # 全局配置（阈值、API、主题）
├── data_cleaning.py            # CSV/XLSX 数据清洗
├── scoring.py                  # 评分算法
├── llm_service.py              # LLM AI 内容分析
├── styles.py                   # CSS 样式
├── requirements.txt            # Python 依赖
├── 内容排行榜评分算法-文档.html  # 评分算法可视化文档
└── setup_and_run.bat           # Windows 一键启动脚本
```
