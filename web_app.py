import csv
import html
import json
import os
import subprocess
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 8000
STRATEGY_TIMEOUT_SECONDS = 240

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>A/H Alpha Web 控制台（Pro v10）</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; max-width: 980px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
    label { display: block; margin-top: 10px; font-weight: 600; }
    input, select { width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box; }
    button { margin-top: 12px; padding: 10px 16px; cursor: pointer; }
    pre { background: #111; color: #e6e6e6; padding: 12px; border-radius: 8px; overflow-x: auto; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  </style>
</head>
<body>
  <h1>A/H Alpha Web 控制台（Pro v10）</h1>
  <div class="card">
    <div class="row">
      <div>
        <label>运行模式</label>
        <select id="mode">
          <option value="live">live（在线）</option>
          <option value="demo">demo（离线）</option>
          <option value="etf">etf（大陆ETF轮动）</option>
        </select>
      </div>
      <div>
        <label>TopN</label>
        <input id="topn" value="10" />
      </div>
    </div>

    <div class="row">
      <div>
        <label>考虑外资投行因子</label>
        <select id="use_institution_factor">
          <option value="1">是（默认）</option>
          <option value="0">否</option>
        </select>
      </div>
      <div>
        <label>考虑市场情绪因子</label>
        <select id="use_market_sentiment">
          <option value="1">是（默认）</option>
          <option value="0">否</option>
        </select>
      </div>
    </div>

    <div class="row">
      <div>
        <label>考虑全球宏观因子</label>
        <select id="use_global_macro">
          <option value="1">是（默认）</option>
          <option value="0">否</option>
        </select>
      </div>
      <div></div>
    </div>

    <div class="row">
      <div>
        <label>Benchmark</label>
        <input id="benchmark" value="000300.SS" />
      </div>
      <div>
        <label>Providers（live 模式）</label>
        <input id="providers" value="eastmoney,tencent,yahoo,stooq" />
      </div>
    </div>

    <div class="row">
      <div>
        <label>请求超时(秒)</label>
        <input id="request_timeout" value="8" />
      </div>
      <div>
        <label>重试次数</label>
        <input id="request_retries" value="1" />
      </div>
    </div>

    <div class="row">
      <div>
        <label>ETF在线池上限</label>
        <input id="etf_live_limit" value="120" />
      </div>
      <div>
        <label>ETF抓取上限</label>
        <input id="cn_etf_limit" value="200" />
      </div>
    </div>

    <div class="row">
      <div>
        <label>Max Weight</label>
        <input id="max_weight" value="0.20" />
      </div>
      <div>
        <label>Risk Aversion</label>
        <input id="risk_aversion" value="0.20" />
      </div>
    </div>

    <div class="row">
      <div>
        <label>BARRA 风控</label>
        <select id="barra_risk_control">
          <option value="1">开启（默认）</option>
          <option value="0">关闭</option>
        </select>
      </div>
      <div>
        <label>BARRA 风险惩罚系数</label>
        <input id="barra_risk_aversion" value="0.20" />
      </div>
    </div>

    <label>Cost Penalty</label>
    <input id="cost_penalty" value="0.10" />

    <div class="row">
      <div>
        <label>DB Path</label>
        <input id="db_path" value="alpha_realtime.db" />
      </div>
      <div>
        <label>DB Only</label>
        <select id="db_only">
          <option value="0">否（允许联网刷新，默认）</option>
          <option value="1">是（仅本地实时库）</option>
        </select>
      </div>
    </div>
  </div>

  <div class="card">
    <h3>回测与稳定性</h3>
    <div class="row">
      <div>
        <label>Walk-forward 回测</label>
        <select id="walk_forward">
          <option value="1">开启（推荐）</option>
          <option value="0">关闭</option>
        </select>
      </div>
      <div>
        <label>WF 训练天数</label>
        <input id="wf_train_days" value="756" />
      </div>
    </div>
    <div class="row">
      <div>
        <label>WF 测试天数</label>
        <input id="wf_test_days" value="21" />
      </div>
      <div>
        <label>WF 步长天数</label>
        <input id="wf_step_days" value="21" />
      </div>
    </div>
    <button id="run_btn" onclick="run()">运行策略</button>
  </div>

  <div class="card">
    <h3>Walk-forward 图表</h3>
    <div id="wf_hint">运行后若开启 walk-forward，将展示日胜率、累计胜率、月度胜率。</div>
    <button id="wf_export_btn" onclick="exportWalkForwardSnapshot()" disabled>一键导出 Walk-forward 图表截图（PNG）</button>
    <canvas id="wf_daily_chart" width="920" height="220"></canvas>
    <canvas id="wf_monthly_chart" width="920" height="220" style="margin-top:10px;"></canvas>
    <div id="wf_export_status" style="margin-top:8px; color:#2f6f44;"></div>
    <div id="wf_export_preview"></div>
  </div>

  <div class="card">
    <h3>输出</h3>
    <pre id="out">点击“运行策略”开始...</pre>
  </div>

<script>
async function run() {
  const runBtn = document.getElementById('run_btn');
  const payload = {
    mode: document.getElementById('mode').value,
    topn: document.getElementById('topn').value,
    use_institution_factor: document.getElementById('use_institution_factor').value,
    use_market_sentiment: document.getElementById('use_market_sentiment').value,
    use_global_macro: document.getElementById('use_global_macro').value,
    benchmark: document.getElementById('benchmark').value,
    providers: document.getElementById('providers').value,
    max_weight: document.getElementById('max_weight').value,
    risk_aversion: document.getElementById('risk_aversion').value,
    barra_risk_control: document.getElementById('barra_risk_control').value,
    barra_risk_aversion: document.getElementById('barra_risk_aversion').value,
    cost_penalty: document.getElementById('cost_penalty').value,
    db_path: document.getElementById('db_path').value,
    db_only: document.getElementById('db_only').value,
    request_timeout: document.getElementById('request_timeout').value,
    request_retries: document.getElementById('request_retries').value,
    etf_live_limit: document.getElementById('etf_live_limit').value,
    cn_etf_limit: document.getElementById('cn_etf_limit').value,
    walk_forward: document.getElementById('walk_forward').value,
    wf_train_days: document.getElementById('wf_train_days').value,
    wf_test_days: document.getElementById('wf_test_days').value,
    wf_step_days: document.getElementById('wf_step_days').value,
  };

  runBtn.disabled = true;
  runBtn.textContent = '运行中...';
  document.getElementById('out').textContent = '运行中（请稍候，策略可能需要几十秒）...';
  document.getElementById('wf_export_status').textContent = '';
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 260000);
    const res = await fetch('/run', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal: ctl.signal,
      headers: { 'Content-Type': 'application/json' },
    });
    clearTimeout(timer);
    const data = await res.json();
    if (!res.ok) {
      document.getElementById('out').textContent = data.error || `请求失败: HTTP ${res.status}`;
      renderWalkForward(null);
      return;
    }
    document.getElementById('out').textContent = data.output || data.error || '无输出';
    renderWalkForward(data.wf_report || null);
  } catch (e) {
    document.getElementById('out').textContent = `请求异常：${e?.message || e}`;
    renderWalkForward(null);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = '运行策略';
  }
}

function drawLineChart(canvas, labels, seriesList, yMin, yMax) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);

  const pad = { l: 45, r: 10, t: 10, b: 28 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  ctx.strokeStyle = '#ddd';
  ctx.beginPath();
  ctx.rect(pad.l, pad.t, iw, ih);
  ctx.stroke();
  for (let k = 0; k <= 4; k++) {
    const yy = pad.t + (ih * k) / 4;
    ctx.strokeStyle = '#eee';
    ctx.beginPath();
    ctx.moveTo(pad.l, yy);
    ctx.lineTo(pad.l + iw, yy);
    ctx.stroke();
    const v = yMax - ((yMax - yMin) * k) / 4;
    ctx.fillStyle = '#666';
    ctx.font = '11px Arial';
    ctx.fillText((v * 100).toFixed(1) + '%', 4, yy + 4);
  }
  if (!labels.length) return;

  function xOf(i) {
    return pad.l + (iw * i) / Math.max(labels.length - 1, 1);
  }
  function yOf(v) {
    const t = (v - yMin) / Math.max(yMax - yMin, 1e-8);
    return pad.t + ih * (1 - t);
  }
  for (const s of seriesList) {
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    s.values.forEach((v, i) => {
      const x = xOf(i), y = yOf(v);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
  ctx.fillStyle = '#444';
  ctx.font = '11px Arial';
  ctx.fillText(labels[0], pad.l, H - 8);
  ctx.fillText(labels[labels.length - 1], pad.l + iw - 70, H - 8);
  let lx = pad.l + 12, ly = pad.t + 14;
  for (const s of seriesList) {
    ctx.fillStyle = s.color;
    ctx.fillRect(lx, ly - 8, 10, 10);
    ctx.fillStyle = '#333';
    ctx.fillText(s.name, lx + 14, ly);
    lx += 150;
  }
}

function drawBarChart(canvas, labels, values, yMin, yMax) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);
  const pad = { l: 45, r: 10, t: 10, b: 30 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  ctx.strokeStyle = '#ddd';
  ctx.beginPath();
  ctx.rect(pad.l, pad.t, iw, ih);
  ctx.stroke();
  if (!labels.length) return;
  const bw = iw / labels.length;
  for (let i = 0; i < labels.length; i++) {
    const v = values[i];
    const t = (v - yMin) / Math.max(yMax - yMin, 1e-8);
    const h = ih * Math.max(0, Math.min(1, t));
    const x = pad.l + i * bw + bw * 0.15;
    const y = pad.t + ih - h;
    ctx.fillStyle = '#4e79a7';
    ctx.fillRect(x, y, bw * 0.7, h);
  }
  const stride = Math.max(1, Math.floor(labels.length / 8));
  ctx.fillStyle = '#444';
  ctx.font = '11px Arial';
  for (let i = 0; i < labels.length; i += stride) {
    const x = pad.l + i * bw + 2;
    ctx.fillText(labels[i], x, H - 8);
  }
}

function renderWalkForward(report) {
  const hint = document.getElementById('wf_hint');
  const dailyCanvas = document.getElementById('wf_daily_chart');
  const monthlyCanvas = document.getElementById('wf_monthly_chart');
  if (!report || !report.daily || !report.daily.length) {
    hint.textContent = '无 walk-forward 结果（可能关闭了该选项或样本不足）。';
    const c1 = dailyCanvas.getContext('2d'); c1.clearRect(0, 0, dailyCanvas.width, dailyCanvas.height);
    const c2 = monthlyCanvas.getContext('2d'); c2.clearRect(0, 0, monthlyCanvas.width, monthlyCanvas.height);
    document.getElementById('wf_export_btn').disabled = true;
    return;
  }
  hint.textContent = `overall: ${(report.overall_win_rate * 100).toFixed(2)}% | n=${report.selected_count}（当前版本暂不提供“权重漂移”曲线）`;
  const labels = report.daily.map(r => r.date);
  const daily = report.daily.map(r => r.daily_win_rate);
  const cumu = report.daily.map(r => r.cumulative_win_rate);
  drawLineChart(
    dailyCanvas,
    labels,
    [{ name: '日胜率', values: daily, color: '#4e79a7' }, { name: '累计胜率', values: cumu, color: '#f28e2b' }],
    0,
    1
  );
  drawBarChart(
    monthlyCanvas,
    report.monthly.map(r => r.month),
    report.monthly.map(r => r.monthly_win_rate),
    0,
    1
  );
  document.getElementById('wf_export_btn').disabled = false;
}

function exportWalkForwardSnapshot() {
  const dailyCanvas = document.getElementById('wf_daily_chart');
  const monthlyCanvas = document.getElementById('wf_monthly_chart');
  const hint = document.getElementById('wf_hint').textContent || '';
  const out = document.getElementById('out').textContent || '';
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');

  const W = 980;
  const H = 620;
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle = '#111';
  ctx.font = 'bold 20px Arial';
  ctx.fillText('A/H Alpha Walk-forward Snapshot', 24, 34);

  ctx.fillStyle = '#444';
  ctx.font = '13px Arial';
  ctx.fillText(hint.slice(0, 120), 24, 58);

  ctx.drawImage(dailyCanvas, 24, 78, 920, 220);
  ctx.drawImage(monthlyCanvas, 24, 308, 920, 220);

  ctx.fillStyle = '#666';
  ctx.font = '12px Arial';
  const tail = out.split('\\n').slice(-3).join(' | ').slice(0, 140);
  ctx.fillText('output tail: ' + tail, 24, 562);
  ctx.fillText('generated: ' + new Date().toLocaleString(), 24, 584);

  const pngData = c.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = pngData;
  a.download = `wf_snapshot_${stamp}.png`;
  a.click();
  document.getElementById('wf_export_status').textContent = `已导出：${a.download}`;
  document.getElementById('wf_export_preview').innerHTML =
    `<div style="margin-top:8px;"><img src="${pngData}" alt="wf snapshot" style="max-width:460px;border:1px solid #ddd;border-radius:6px;" /></div>`;
}
</script>
</body>
</html>
"""


def parse_walk_forward_csv(path: str):
    daily = []
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    for row in rows[1:]:
        if not row:
            break
        if len(row) < 4:
            continue
        day, sel, wins, wr = row[0], int(row[1]), int(row[2]), float(row[3])
        daily.append({"date": day, "selected_count": sel, "wins": wins, "daily_win_rate": wr})

    if not daily:
        return None

    cum_wins = 0
    cum_sel = 0
    for rec in daily:
        cum_wins += rec["wins"]
        cum_sel += rec["selected_count"]
        rec["cumulative_win_rate"] = (cum_wins / cum_sel) if cum_sel else 0.0

    by_month = {}
    for rec in daily:
        month = rec["date"][:7]
        if month not in by_month:
            by_month[month] = {"sel": 0, "wins": 0}
        by_month[month]["sel"] += rec["selected_count"]
        by_month[month]["wins"] += rec["wins"]

    monthly = []
    for month in sorted(by_month.keys()):
        sel = by_month[month]["sel"]
        wins = by_month[month]["wins"]
        monthly.append({"month": month, "selected_count": sel, "wins": wins, "monthly_win_rate": (wins / sel) if sel else 0.0})

    return {
        "daily": daily,
        "monthly": monthly,
        "overall_win_rate": daily[-1]["cumulative_win_rate"],
        "selected_count": cum_sel,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            b = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        self.send_error(404, "Not Found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/run":
            self.send_error(404, "Not Found")
            return

        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, 400)
            return

        mode = str(payload.get("mode", "demo"))
        topn = str(payload.get("topn", "10"))
        benchmark = str(payload.get("benchmark", "000300.SS"))
        providers = str(payload.get("providers", "eastmoney,tencent,yahoo,stooq"))
        max_weight = str(payload.get("max_weight", "0.20"))
        risk_aversion = str(payload.get("risk_aversion", "0.20"))
        barra_risk_control = str(payload.get("barra_risk_control", "1"))
        barra_risk_aversion = str(payload.get("barra_risk_aversion", "0.20"))
        cost_penalty = str(payload.get("cost_penalty", "0.10"))
        db_path = str(payload.get("db_path", "alpha_realtime.db"))
        db_only = str(payload.get("db_only", "0"))
        request_timeout = str(payload.get("request_timeout", "8"))
        request_retries = str(payload.get("request_retries", "1"))
        etf_live_limit = str(payload.get("etf_live_limit", "120"))
        cn_etf_limit = str(payload.get("cn_etf_limit", "200"))
        use_institution_factor = str(payload.get("use_institution_factor", "1"))
        use_market_sentiment = str(payload.get("use_market_sentiment", "1"))
        use_global_macro = str(payload.get("use_global_macro", "1"))
        walk_forward = str(payload.get("walk_forward", "1"))
        wf_train_days = str(payload.get("wf_train_days", "756"))
        wf_test_days = str(payload.get("wf_test_days", "21"))
        wf_step_days = str(payload.get("wf_step_days", "21"))

        cmd = [
            "python",
            "quant_alpha_system.py",
            "--topn",
            topn,
            "--benchmark",
            benchmark,
            "--max-weight",
            max_weight,
            "--risk-aversion",
            risk_aversion,
            "--barra-risk-aversion",
            barra_risk_aversion,
            "--cost-penalty",
            cost_penalty,
            "--db-path",
            db_path,
            "--request-timeout",
            request_timeout,
            "--request-retries",
            request_retries,
        ]
        if use_institution_factor == "1":
            cmd.append("--use-institution-factor")
        else:
            cmd.append("--no-use-institution-factor")
        if use_market_sentiment == "1":
            cmd.append("--use-market-sentiment")
        else:
            cmd.append("--no-use-market-sentiment")
        if use_global_macro == "1":
            cmd.append("--use-global-macro")
        else:
            cmd.append("--no-use-global-macro")
        if barra_risk_control == "1":
            cmd.append("--barra-risk-control")
        else:
            cmd.append("--no-barra-risk-control")

        if mode == "demo":
            cmd.append("--demo")
        elif mode == "live":
            cmd.extend(["--providers", providers])
            if db_only == "1":
                cmd.append("--db-only")
            else:
                cmd.append("--no-db-only")
        elif mode == "etf":
            cmd.extend(
                [
                    "--providers",
                    providers,
                    "--cn-etf-rotation",
                    "--auto-tune-horizon-weights",
                    "--cn-etf-limit",
                    cn_etf_limit,
                    "--etf-live-limit",
                    etf_live_limit,
                ]
            )
            if db_only == "1":
                cmd.append("--db-only")
            else:
                cmd.append("--no-db-only")
        else:
            self._send_json({"error": f"未知模式: {html.escape(mode)}"}, 400)
            return

        wf_tmp_path = None
        if walk_forward == "1":
            wf_tmp = tempfile.NamedTemporaryFile(prefix="wf_", suffix=".csv", delete=False)
            wf_tmp.close()
            wf_tmp_path = wf_tmp.name
            cmd.extend(
                [
                    "--walk-forward",
                    "--wf-train-days",
                    wf_train_days,
                    "--wf-test-days",
                    wf_test_days,
                    "--wf-step-days",
                    wf_step_days,
                    "--walk-forward-csv",
                    wf_tmp_path,
                ]
            )

        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=STRATEGY_TIMEOUT_SECONDS)
            output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
            wf_report = None
            if wf_tmp_path and os.path.exists(wf_tmp_path) and os.path.getsize(wf_tmp_path) > 0:
                wf_report = parse_walk_forward_csv(wf_tmp_path)
            self._send_json({"output": output, "returncode": p.returncode, "wf_report": wf_report})
        except subprocess.TimeoutExpired:
            self._send_json(
                {"error": f"运行超时（{STRATEGY_TIMEOUT_SECONDS}秒）: 请缩小股票池、降低重试次数，或改用 DB Only。"},
                500,
            )
        finally:
            if wf_tmp_path and os.path.exists(wf_tmp_path):
                os.remove(wf_tmp_path)


def main():
    url = f"http://{HOST}:{PORT}"
    print(f"Web UI running on {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
