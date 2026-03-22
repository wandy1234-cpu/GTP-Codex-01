# A/H 股票上涨概率系统（Pro v9：实时数据库 + 专业报告格式）

本次升级目标：
- **优先实时**：支持东财实时行情刷新（中国大陆源）+ Yahoo 备用
- **兜底最新**：若实时不可得，自动使用最新日线数据
- **多数据源**：支持 `eastmoney,tencent,yahoo,stooq` 级联抓取，提高 A/H 数据可用性
- **更偏 Alpha**：标签升级为“相对基准超额收益 > 0”（缺基准时回退绝对收益）
- **新增组合建议**：输出 alpha 导向的建议权重（带单票权重上限）
- **新增风控/换手感知**：组合打分加入风险惩罚与成本惩罚，并支持读取上期权重估算换手
- **新增实时数据库**：使用 SQLite 缓存历史与实时行情，支持断网回退继续运行
- **专业输出格式**：终端报告增加系统名、策略介绍、运行时间、数据来源、模型区块
- 仍保持纯 Python（无第三方库）

## 1) 默认运行（实时优先）

```bash
python quant_alpha_system.py
```

默认：
- `--providers eastmoney,tencent,yahoo,stooq`（先东财，再腾讯，再 Yahoo，再 Stooq）
- `--end` 自动取当天日期
- `--benchmark 000300.SS`（默认沪深300，作为超额收益标签基准）
- `--max-weight 0.35`（单票建议权重上限）
- `--risk-aversion 0.15`（风险惩罚系数）
- `--cost-penalty 0.10`（成本/换手惩罚系数）
- `--prev-weights prev.csv`（上一期权重，估算换手）
- `--save-weights out.csv`（保存本期建议权重）
- `--db-path alpha_realtime.db`（实时数据库路径）
- `--db-only`（仅使用本地数据库运行，不访问网络）
- 会尝试实时 quote 刷新；失败则回退到最新日线

## 2) 指定数据窗口与股票池

```bash
python quant_alpha_system.py \
  --tickers "600519.SS,000858.SZ,0700.HK,9988.HK" \
  --start 2020-01-01 \
  --end 2026-03-21 \
  --providers eastmoney,tencent,yahoo,stooq \
  --benchmark 000300.SS \
  --max-weight 0.30 \
  --risk-aversion 0.20 \
  --cost-penalty 0.10 \
  --prev-weights prev_portfolio.csv \
  --save-weights new_portfolio.csv \
  --horizon 5 \
  --topn 10
```

## 3) 关闭实时刷新（只用最新日线）

```bash
python quant_alpha_system.py --no-realtime
```

## 4) 使用你自己的 CSV

CSV 列：`date,ticker,close,high,low,volume`

```bash
python quant_alpha_system.py --input-csv your_ah_data.csv --horizon 5 --topn 10
```

## 5) 离线演示模式

```bash
python quant_alpha_system.py --demo
```

## 5.1) Windows 一键脚本

仓库已提供 `run_alpha_windows.bat`，支持三种模式：

```bat
run_alpha_windows.bat demo
run_alpha_windows.bat live
run_alpha_windows.bat csv your_ah_data.csv
```

说明：
- 自动把权重输出到 `outputs\portfolio_时间戳.csv`
- 自动维护 `outputs\latest_portfolio.csv` 作为下一次的 `--prev-weights`
- `live` 模式默认用大陆优先数据源：`eastmoney,tencent,yahoo,stooq`

## 5.2) 网页版控制台（推荐）

项目提供了 `web_app.py`，可在浏览器中配置参数并运行策略。

启动：

```bash
python web_app.py
```

打开：

```
http://127.0.0.1:8000
```

页面支持：
- `demo` / `live` / `csv` 三种模式
- TopN、benchmark、providers、max-weight、risk-aversion、cost-penalty 参数可视化配置
- DB Path、DB Only 可视化配置（实时数据库模式）
- 在线展示 `quant_alpha_system.py` 的完整输出

## 6) 这次算法/工程升级点

- 新增 Eastmoney（东财）实时 quote 接口（实时价格 + 时间戳）
- 新增 Eastmoney 历史日线接口（大陆源，支持 A/H）
- 新增 Tencent（腾讯）历史日线与实时 quote 备用接口（大陆源）
- 新增 Stooq 历史日线兜底源
- 提供 `--providers` 自定义抓取优先级
- 新增 `--benchmark`，标签改为超额收益方向（指数增强更实用）
- 新增 `--max-weight` 与组合权重输出（从“选股”升级到“组合建议”）
- 新增 `--risk-aversion` / `--cost-penalty` / `--prev-weights` / `--save-weights`
- 保留时间切分 + Logistic SGD + F1 阈值搜索 + TopN 概率排序

## 7) 偏 Alpha 下一步建议

- 标签改“超额收益 > 0”
- 行业/风格中性化
- 交易成本 + 冲击成本
- walk-forward 稳定性检验
- 组合优化层：`max(alpha - 风险惩罚 - 成本惩罚)`
