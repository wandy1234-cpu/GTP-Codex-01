import argparse
import datetime as dt
import json
import math
from collections import defaultdict
from typing import Dict, List, Tuple, Set

import quant_alpha_system as q

GROUPS = {
    "liquidity_price_volume": {"ret_1d", "ret_5d", "vol_ratio", "price_pos_20d", "amihud_20d", "vol_20d"},
    "quality_profitability_proxy": {"ret_60d", "downside_vol_20d", "drawdown_20d"},
    "industry_momentum": {"ret_20d", "rel_ret_5d", "ma_gap_10_30", "bm_trend_5d"},
    "broker_revision": {"ib_top5_score"},
    "sentiment_macro": {"mkt_breadth_5d", "oil_ret_5d", "vix_ret_5d"},
}


def rankdata(vals: List[float]) -> List[float]:
    idx = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    r = 1
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and vals[idx[j + 1]] == vals[idx[i]]:
            j += 1
        avg_rank = 0.5 * (r + r + (j - i))
        for k in range(i, j + 1):
            out[idx[k]] = avg_rank
        r += j - i + 1
        i = j + 1
    return out


def spearman(x: List[float], y: List[float]) -> float:
    if len(x) < 3 or len(y) != len(x):
        return 0.0
    rx = rankdata(x)
    ry = rankdata(y)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return cov / (sx * sy)


def build_future_excess_map(data: Dict[str, List[q.Row]], benchmark: str, horizon: int) -> Dict[Tuple[dt.date, str], float]:
    bm = data.get(benchmark, [])
    bm_close = {r.date: r.close for r in bm}
    out = {}
    for tk, rows in data.items():
        if tk == benchmark:
            continue
        for i in range(0, len(rows) - horizon):
            d0 = rows[i].date
            d1 = rows[i + horizon].date
            if rows[i].close <= 0:
                continue
            r = rows[i + horizon].close / rows[i].close - 1.0
            if d0 in bm_close and d1 in bm_close and bm_close[d0] > 0:
                bm_r = bm_close[d1] / bm_close[d0] - 1.0
                out[(d0, tk)] = r - bm_r
            else:
                out[(d0, tk)] = r
    return out


def evaluate(data, benchmark, horizon, topn, disabled_groups: Set[str], only_groups: Set[str] | None = None):
    mkt = q.build_market_sentiment_map(data, benchmark)
    macro = {}
    samples = q.build_samples(
        data,
        horizon=horizon,
        benchmark_ticker=benchmark,
        institutional_factor={},
        market_sentiment_map=mkt,
        global_macro_map=macro,
        use_liquidity_factor=True,
    )
    train, test = q.train_test_split(samples, split_ratio=0.8)
    x_train, y_train, x_test, y_test, _m, _s = q.standardize(train, test)
    w, b = q.train_logistic_sgd(x_train, y_train)

    use = [1.0] * len(q.FEATURE_NAMES)
    for i, f in enumerate(q.FEATURE_NAMES):
        gnames = [g for g, fs in GROUPS.items() if f in fs]
        if any(g in disabled_groups for g in gnames):
            use[i] = 0.0
        if only_groups is not None and gnames and all(g not in only_groups for g in gnames):
            use[i] = 0.0

    x_test_mask = q.apply_feature_scalers(x_test, use)
    probs = q.predict_prob(w, b, x_test_mask)
    fex = build_future_excess_map(data, benchmark, horizon)

    by_day = defaultdict(list)
    for s, p in zip(test, probs):
        ex = fex.get((s.date, s.ticker))
        if ex is None:
            continue
        by_day[s.date].append((s.ticker, p, ex))

    daily_ret = []
    daily_ic = []
    prev_set = set()
    turn_sum = 0.0
    a_contrib = 0.0
    h_contrib = 0.0
    a_n = h_n = 0
    phase = defaultdict(list)

    bm_rows = data.get(benchmark, [])
    bm_close = {r.date: r.close for r in bm_rows}
    bm_dates = sorted(bm_close.keys())
    for d in sorted(by_day.keys()):
        arr = sorted(by_day[d], key=lambda x: x[1], reverse=True)
        sel = arr[: min(topn, len(arr))]
        if not sel:
            continue
        ret = sum(x[2] for x in sel) / len(sel)
        daily_ret.append((d, ret))
        daily_ic.append(spearman([x[1] for x in arr], [x[2] for x in arr]))
        cur_set = {x[0] for x in sel}
        if prev_set:
            turn_sum += 1 - len(cur_set & prev_set) / max(1, len(cur_set | prev_set))
        prev_set = cur_set
        for tk, _p, ex in sel:
            if tk.endswith('.HK'):
                h_contrib += ex
                h_n += 1
            else:
                a_contrib += ex
                a_n += 1
        # simple phase by benchmark above MA60
        idx = next((i for i, bd in enumerate(bm_dates) if bd == d), -1)
        if idx >= 60:
            ma20 = sum(bm_close[bm_dates[j]] for j in range(idx - 19, idx + 1)) / 20
            ma60 = sum(bm_close[bm_dates[j]] for j in range(idx - 59, idx + 1)) / 60
            if bm_close[d] > ma20 and bm_close[d] > ma60:
                ph = 'risk_on'
            elif bm_close[d] < ma20 and bm_close[d] < ma60:
                ph = 'risk_off'
            else:
                ph = 'neutral'
            phase[ph].append(ret)

    rs = [r for _d, r in daily_ret]
    if not rs:
        return {}
    eq = [1.0]
    for r in rs:
        eq.append(eq[-1] * (1 + r))
    peak = eq[0]
    mdd = 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    mean = sum(rs) / len(rs)
    std = math.sqrt(sum((x - mean) ** 2 for x in rs) / max(1, len(rs) - 1))
    sharpe = (mean / std * math.sqrt(252)) if std > 1e-12 else 0.0
    ann = (eq[-1] ** (252 / max(1, len(rs))) - 1.0)
    calmar = ann / abs(mdd) if mdd < 0 else 0.0
    pos = [x for x in rs if x > 0]
    neg = [x for x in rs if x <= 0]
    payoff = (sum(pos) / len(pos)) / abs(sum(neg) / len(neg)) if pos and neg and abs(sum(neg)) > 1e-12 else 0.0

    return {
        'days': len(rs),
        'cum_excess_return': eq[-1] - 1.0,
        'annualized_excess_return': ann,
        'max_drawdown': mdd,
        'sharpe': sharpe,
        'calmar': calmar,
        'win_rate': len(pos) / len(rs),
        'payoff_ratio': payoff,
        'turnover': turn_sum / max(1, len(rs) - 1),
        'rankic': sum(daily_ic) / max(1, len(daily_ic)),
        'rankic_ir': (sum(daily_ic) / len(daily_ic)) / (math.sqrt(sum((x - (sum(daily_ic)/len(daily_ic)))**2 for x in daily_ic) / max(1, len(daily_ic)-1)) + 1e-12),
        'a_alpha': a_contrib / max(1, a_n),
        'h_alpha': h_contrib / max(1, h_n),
        'phase_alpha': {k: (sum(v) / len(v) if v else 0.0) for k, v in phase.items()},
    }


def md_table(rows: List[List[str]]) -> str:
    if not rows:
        return ''
    out = ['| ' + ' | '.join(rows[0]) + ' |', '| ' + ' | '.join(['---'] * len(rows[0])) + ' |']
    for r in rows[1:]:
        out.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--benchmark', default='000300.SS')
    ap.add_argument('--horizon', type=int, default=5)
    ap.add_argument('--topn', type=int, default=10)
    ap.add_argument('--output-md', default='audit_report.md')
    args = ap.parse_args()

    data = q.generate_demo_data(seed=42)
    baseline = evaluate(data, args.benchmark, args.horizon, args.topn, disabled_groups=set())

    ablation = {}
    standalone = {}
    for g in GROUPS:
        ablation[g] = evaluate(data, args.benchmark, args.horizon, args.topn, disabled_groups={g})
        standalone[g] = evaluate(data, args.benchmark, args.horizon, args.topn, disabled_groups=set(), only_groups={g})

    lines = []
    lines.append('# Quant System Structure Audit Report')
    lines.append('')
    lines.append('## 1) Pipeline Diagram')
    lines.append('')
    lines.append('```text')
    lines.append('Data (A/H bars + benchmark + optional broker/mkt/macro)')
    lines.append('  -> Feature Engineering (multi-group factors)')
    lines.append('  -> Label: future excess return sign (horizon-based)')
    lines.append('  -> Logistic SGD (binary classification)')
    lines.append('  -> Multi-horizon fusion')
    lines.append('  -> Regime overlay (risk_on/neutral/risk_off)')
    lines.append('  -> Constrained pools (formal / backup / watch)')
    lines.append('  -> Portfolio + risk/cost/BARRA + exit plan')
    lines.append('  -> Reports (CLI + JSON/MD/CSV)')
    lines.append('```')
    lines.append('')
    lines.append('## 2) Audit Answers')
    lines.append('- 标签定义：`horizon` 日未来超额收益是否 > 0（二分类标签）。')
    lines.append('- 模型类型：二分类模型（Logistic SGD），并按概率做排序。')
    lines.append('- Top10 逻辑：先概率排序，再经市场状态与组合约束生成正式池。')
    lines.append('- 外资/情绪/宏观注入方式：作为特征进入模型（并可在上层作为 regime/置信度参考）。')
    lines.append('- 行业/市值中性化：当前无严格回归中性化（行业仅用于组合约束；市值代理尚弱）。')
    lines.append('- 回测假设：当前核心回测侧重超额收益方向与组合收益统计；交易成本/滑点/涨跌停实盘约束仍需进一步细化。')
    lines.append('')
    lines.append('## 3) Key Metrics (baseline)')
    rows = [["metric", "value"]] + [[k, f"{v:.6f}" if isinstance(v, float) else json.dumps(v, ensure_ascii=False)] for k, v in baseline.items()]
    lines.append(md_table(rows))
    lines.append('')
    lines.append('## 4) Factor Inventory')
    inv = [["group", "factors"]]
    for g, fs in GROUPS.items():
        inv.append([g, ', '.join(sorted(fs))])
    lines.append(md_table(inv))
    lines.append('')
    lines.append('## 5) Ablation (remove one group)')
    rows = [["group", "cum_excess", "ann_excess", "max_dd", "sharpe", "turnover", "rankic"]]
    for g, m in ablation.items():
        if not m:
            rows.append([g, 'NA', 'NA', 'NA', 'NA', 'NA', 'NA'])
            continue
        rows.append([
            g,
            f"{m['cum_excess_return']:.4f}",
            f"{m['annualized_excess_return']:.4f}",
            f"{m['max_drawdown']:.4f}",
            f"{m['sharpe']:.4f}",
            f"{m['turnover']:.4f}",
            f"{m['rankic']:.4f}",
        ])
    lines.append(md_table(rows))
    lines.append('')
    lines.append('## 6) Standalone Group Power')
    rows = [["group", "cum_excess", "ann_excess", "max_dd", "sharpe", "turnover", "rankic"]]
    for g, m in standalone.items():
        if not m:
            rows.append([g, 'NA', 'NA', 'NA', 'NA', 'NA', 'NA'])
            continue
        rows.append([
            g,
            f"{m['cum_excess_return']:.4f}",
            f"{m['annualized_excess_return']:.4f}",
            f"{m['max_drawdown']:.4f}",
            f"{m['sharpe']:.4f}",
            f"{m['turnover']:.4f}",
            f"{m['rankic']:.4f}",
        ])
    lines.append(md_table(rows))
    lines.append('')
    lines.append('## 7) Most Likely Issues')
    lines.append('- 目标函数仍容易被“命中率”牵引，成本后信息比率优化不足。')
    lines.append('- 市值/行业严格中性化缺失，风格漂移风险仍在。')
    lines.append('- 成本、滑点、不可交易（停牌/涨跌停）的实盘约束尚需全量并入回测成交层。')
    lines.append('- 外资/情绪/宏观三组的角色边界（核心 alpha vs 过滤器）还需通过年度稳定性进一步约束。')
    lines.append('')
    lines.append('## 8) Highest ROI Improvements')
    lines.append('1. 先用“年化超额 + IR - 换手惩罚”做主排序指标。')
    lines.append('2. 将外资/情绪/宏观从直接排序因子迁移为 regime/filter/confidence 层。')
    lines.append('3. 在组合层补齐小市值上限与低流动性硬过滤。')
    lines.append('4. 回测成交层纳入成本/滑点/不可交易约束，按年份与市场状态分解表现。')

    with open(args.output_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'Saved audit report: {args.output_md}')


if __name__ == '__main__':
    main()
