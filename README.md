# 麦当劳内容排行榜

麦当劳 Push 内容效果排行榜可视化工具，基于 Streamlit + Plotly 构建。

**在线访问**：https://ori-yin-mcd-content-rank.streamlit.app

**GitHub**：https://github.com/ori-yin/mcd-content-rank

## 功能特性

- **综合评分模型**：触达量(35%) + CTR(15%) + 订单Sales(40%) + 单均价(10%)，支持权重自定义调节
- **三种视图**：卡片排行榜 / 数据表格 / 可视化图表
- **筛选功能**：按计划类型、渠道筛选，支持关键词搜索
- **交互图表**：Top 10 柱状图、触达 vs 订单Sales 散点图（气泡大小=CTR）
- **麦当劳品牌风格**：红金配色，苹果风 UI

## 快速开始（本地运行）

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 部署到 Streamlit Cloud

1. 访问 [streamlit.io/sharing](https://streamlit.io/sharing)
2. 点击 **New app** → 选择 `ori-yin/mcd-content-rank` → 分支选 `main` → 主文件填 `app.py`
3. 点击 **Deploy**

> Streamlit Cloud 会自动从 GitHub 读取 requirements.txt 并安装依赖

## 数据格式

上传 CSV 文件，列名对应关系：

| CSV 列名 | 说明 |
|----------|------|
| 标题 | 内容标题 |
| 内容 | 内容正文 |
| 触达成功 | 触达人数 |
| 点击人次 | 点击次数 |
| 订单GC | 订单数量 |
| 订单Sales | 订单金额 |
| 计划类型 | 常规Plan / AARRPlan |
| 渠道 | APP Push / 企微1v1 |
| 发送日期 | 发送日期 |

## 综合评分算法

**Min-Max 归一化加权模型：**

```
综合评分 = 触达量_norm × 35% + CTR_norm × 15% + 订单Sales_norm × 40% + 单均价_norm × 10%
```

- 各维度分别归一化到 0-100 分
- 权重可在 App 侧边栏实时调整
