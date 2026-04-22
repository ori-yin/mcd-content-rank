# 麦当劳内容排行榜

Streamlit Web 应用：从 Push 发送数据中自动计算内容综合评分排行榜。

**功能：**
- 上传 CSV 自动识别列名
- 4维综合评分：触达量 35% + CTR 15% + 订单Sales 40% + 单均价 10%
- 日期范围 / 计划类型 / 渠道 / Owner 多维筛选
- 卡片排行榜 + 数据表格 + Plotly 可视化图表
- 筛选后 HTML 一键下载（麦当劳品牌设计）

**列名要求（CSV）：**
发送日期 | 计划类型 | 渠道 | 触达成功 | 点击人次 | 订单GC | 订单Sales | 标题 | 内容 | 预算owner

**部署：** https://ori-yin-mcd-content-rank.streamlit.app
