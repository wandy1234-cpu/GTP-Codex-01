# A/H 股票上涨概率系统（Pro v10：多周期标签融合 + 指数增强）

本次升级目标：
- **优先实时**：支持东财实时行情刷新（中国大陆源）+ Yahoo 备用
- **兜底最新**：若实时不可得，自动使用最新日线数据
- **多数据源**：支持 `eastmoney,tencent,yahoo,stooq` 级联抓取，提高 A/H 数据可用性
- **更偏 Alpha**：标签升级为“相对基准超额收益 > 0”（缺基准时回退绝对收益）
- **新增组合建议**：输出 alpha 导向的建议权重（带单票权重上限）
- **新增风控/换手感知**：组合打分加入风险惩罚与成本惩罚，并支持读取上期权重估算换手
- **新增实时数据库**：使用 SQLite 缓存历史与实时行情，支持断网回退继续运行
- **专业输出格式**：终端报告增加系统名、策略介绍、运行时间、数据来源、模型区块
- **可读性升级**：股票代码后自动显示股票名称（如 `000858.SZ(五粮液)`）
- **名称来源升级**：优先从东财/腾讯实时接口获取股票中文名，并写入 SQLite 缓存
- **TopN 修正**：请求多少条就返回多少条（不足时用占位行提示）
- **多周期标签融合**：支持 `5/10/20`（可自定义），更贴合指数增强的多周期alpha框架
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
- `--no-db-only`（允许联网拉取/刷新数据，**默认开启**）
- `--cn-etf-rotation`（启用大陆 ETF 轮动模式：自动拉取沪深 ETF 池）
- `--cn-etf-limit 800`（大陆 ETF 池拉取上限）
- `--horizons 5,10,20`（多标签周期）
- `--horizon-weights 0.2,0.3,0.5`（多标签融合权重）
- `--auto-tune-horizon-weights`（根据 holdout 回测胜率自动反推多周期融合权重）
- `--min-samples 500`（每个 horizon 最低样本门槛；ETF 模式默认自动放宽到 180）
- `--report-csv one_year_report.csv`（导出近1年每日胜率报告）
- 会尝试实时 quote 刷新；失败则回退到最新日线
- 为避免 `--db-only` 与联网模式因“陈旧实时价”产生偏差，程序仅使用不早于 `--end` 当天 00:00(UTC) 的 quote，过旧 quote 自动忽略并回退日线收盘价
- 联网模式会在多数据源中优先选“最新日期”的日线数据，并过滤掉明显过旧（默认落后超过 7 天）的数据源结果

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

如果你想强制只用数据库（断网/稳态复现），加：

```bash
python quant_alpha_system.py --db-only
```

## 3.1) 根据回测结果反向优化模型（自动调融合权重）

```bash
python quant_alpha_system.py --horizons 5,10,20 --auto-tune-horizon-weights
```

说明：
- 对每个 horizon，在 holdout 测试集上统计 top20% 组合胜率；
- 用 `max(胜率-0.5, 0.0001) * log(1+样本数)` 计算分数并归一化为权重；
- 适合作为“先验自动调参”，建议再做样本外窗口复核。

## 3.2) 大陆 ETF 轮动推荐（新增）

```bash
python quant_alpha_system.py \
  --cn-etf-rotation \
  --providers eastmoney,tencent,yahoo,stooq \
  --benchmark 510300.SS \
  --topn 20 \
  --auto-tune-horizon-weights
```

说明：
- 自动从 Eastmoney 拉取沪深 ETF 列表（失败时回退到内置 ETF 池）；
- 默认 benchmark 若仍为 `000300.SS`，会自动切到 `510300.SS`；
- 输出逻辑不变：TopN + 建议组合权重 + 风险/成本惩罚。

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
run_alpha_windows.bat etf
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

> 现在执行 `python web_app.py` 会自动尝试打开默认浏览器。

页面支持：
- `demo` / `live` / `csv` 三种模式
- TopN、benchmark、providers、max-weight、risk-aversion、cost-penalty 参数可视化配置
- DB Path、DB Only 可视化配置（实时数据库模式）
- `请求超时(秒)` / `重试次数` 可视化配置（解决 live 模式超时问题）
- CSV 路径默认预填：`C:\Users\Admin\Desktop\GTP-Codex-01`
- 在线展示 `quant_alpha_system.py` 的完整输出

## 6) 这次算法/工程升级点

- 新增 Eastmoney（东财）实时 quote 接口（实时价格 + 时间戳）
- 新增 Eastmoney 历史日线接口（大陆源，支持 A/H）
- 新增 Tencent（腾讯）历史日线与实时 quote 备用接口（大陆源）
- 新增 Stooq 历史日线兜底源
- 提供 `--providers` 自定义抓取优先级
- 新增 `--request-timeout` / `--request-retries` / `--full-provider-scan`，默认启用低延迟拉取（拿到新鲜数据即停止继续扫描 provider）
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

## 8) 这个模型适不适合 ETF？

可以，但更适合 **ETF轮动/ETF增强**，不建议把它当作单只ETF择时的万能模型。实务建议：
- `--tickers` 直接给 ETF 池（宽基/行业/主题）；
- `--benchmark` 用宽基或你策略对应基准；
- 优先中周期权重（如 `10/20`），降低超短周期噪声；
- 适当提高 `--cost-penalty`，防止ETF高换手吞噬超额；
- 结合成交额/规模约束，避免冷门ETF滑点。
