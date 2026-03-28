# Quant Alpha (A股 + H股 指数增强荐股系统)

生产级、可追踪、可扩展的 A/H 股票推荐系统（Phase 1 可运行版）。

## 功能（Phase 1）
- 统一数据适配层（Eastmoney/Tencent/Yahoo/Stooq）+ 降级机制
- Parquet 落盘 + DuckDB 查询
- 股票池过滤（A/H 分市场）
- 标签构建（future_ret_5d / future_excess_ret_5d / future_up_5d / future_big_up_5d）
- 基础特征工程（动量、波动、量价、截面）
- LightGBM Ranker 主流程
- Walk-forward 回测（基础版 + purge）
- Top10 推荐输出与历史持久化
- Streamlit 多页面 GUI 骨架

## 安装
```bash
cd quant_alpha
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 运行
### 1) 更新数据
```bash
python scripts/main_update_data.py
```

### 2) 训练 + 预测
```bash
python scripts/main_predict.py
```

### 3) 回测
```bash
python scripts/main_backtest.py
```

### 4) 启动 GUI
```bash
streamlit run app.py
```

## 测试
```bash
pytest -q
```

## 风险说明（外部数据源）
- Eastmoney/Tencent 接口在不同网络环境下可能不稳定或限流。
- 本系统内置降级：主源失败时自动切换 Yahoo/Stooq，并允许以示例 universe 继续跑通。
- 对多源同日同票价格差异做异常记录，超过阈值可剔除。

## 目录
见项目根目录树（与需求文档一致）。
