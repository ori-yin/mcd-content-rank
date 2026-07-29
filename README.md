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

最小列（必填，缺一报错）：

发送日期 | 计划类型 | 渠道 | 触达成功 | 点击人次 | 点击后下单人次 | 订单GC | 订单Sales | 标题 | 内容 | 预算owner

新数据源（2026-07 起）追加 2 列，**强烈建议带上**：

Plan ID | Unit ID | Message ID

> - `Plan ID` → 投放计划 ID（卡片底部展示）
> - `Unit ID` → 同一文案的「千人千面」分组（推送文案相同，点击后落地页菜单不同）
> - `Message ID` → 文案本身的唯一 ID（与「内容」字段一一对应，18 位数字）
>
> 没有 `Message ID` 时自动退化为按 `Plan ID × 标题` 聚合（兼容旧数据 cnn0727 及更早）。

## 卡片聚合粒度

**一张卡片 = 一个 Plan × 一条文案（Message）**

- 同一天同 Plan 下 N 个 Unit 的同一文案 → 合成 **1 张卡**，卡片底部标 `N Unit`
- 同一天同 Plan 下不同文案 → 各占 **1 张卡**（不合并，保留文案差异）
- 跨天投放 → 仍是不同卡片，**by day 一张不少**（日期窗口由侧边栏控制）

**为什么要合并 Unit：** 同一条文案按 Unit 拆分后投放（如 7/06 东北市场短信拆 7 个 Unit），不合并会出现：① 一条文案按 Unit 数重复占榜；② Unit 之间的 CTR 差异来自人群/落地页不是文案，会被误读成文案优劣。

## 数据源变更历史

- **2026-07-27 起** — SQL 输出新增 `Unit ID`、`Message ID` 两列（共 17 列）。Message ID 与「消息内容」一一对应，可作为文案唯一键
- **2026-07-27 之前** — 15 列格式，无 Unit/Message 概念，1 Plan = 1 文案。仍兼容

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
