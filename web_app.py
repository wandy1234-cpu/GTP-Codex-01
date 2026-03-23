import html
import json
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

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
          <option value="csv">csv（本地文件）</option>
        </select>
      </div>
      <div>
        <label>TopN</label>
        <input id="topn" value="10" />
      </div>
    </div>

    <label>CSV 路径（仅 csv 模式）</label>
    <input id="csv" value="C:\\Users\\Admin\\Desktop\\GTP-Codex-01" />

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

    <button onclick="run()">运行策略</button>
  </div>

  <div class="card">
    <h3>输出</h3>
    <pre id="out">点击“运行策略”开始...</pre>
  </div>

<script>
async function run() {
  const payload = {
    mode: document.getElementById('mode').value,
    topn: document.getElementById('topn').value,
    csv: document.getElementById('csv').value,
    use_institution_factor: document.getElementById('use_institution_factor').value,
    use_market_sentiment: document.getElementById('use_market_sentiment').value,
    use_global_macro: document.getElementById('use_global_macro').value,
    benchmark: document.getElementById('benchmark').value,
    providers: document.getElementById('providers').value,
    max_weight: document.getElementById('max_weight').value,
    risk_aversion: document.getElementById('risk_aversion').value,
    cost_penalty: document.getElementById('cost_penalty').value,
    db_path: document.getElementById('db_path').value,
    db_only: document.getElementById('db_only').value,
    request_timeout: document.getElementById('request_timeout').value,
    request_retries: document.getElementById('request_retries').value,
    etf_live_limit: document.getElementById('etf_live_limit').value,
    cn_etf_limit: document.getElementById('cn_etf_limit').value,
  };

  document.getElementById('out').textContent = '运行中...';
  const res = await fetch('/run', { method: 'POST', body: JSON.stringify(payload) });
  const data = await res.json();
  document.getElementById('out').textContent = data.output || data.error || '无输出';
}
</script>
</body>
</html>
"""


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
        cost_penalty = str(payload.get("cost_penalty", "0.10"))
        db_path = str(payload.get("db_path", "alpha_realtime.db"))
        db_only = str(payload.get("db_only", "0"))
        request_timeout = str(payload.get("request_timeout", "8"))
        request_retries = str(payload.get("request_retries", "1"))
        etf_live_limit = str(payload.get("etf_live_limit", "120"))
        cn_etf_limit = str(payload.get("cn_etf_limit", "200"))
        csv_path = str(payload.get("csv", "")).strip()
        use_institution_factor = str(payload.get("use_institution_factor", "1"))
        use_market_sentiment = str(payload.get("use_market_sentiment", "1"))
        use_global_macro = str(payload.get("use_global_macro", "1"))

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
        elif mode == "csv":
            if not csv_path:
                self._send_json({"error": "csv 模式必须填写 csv 路径"}, 400)
                return
            cmd.extend(["--input-csv", csv_path])
        else:
            self._send_json({"error": f"未知模式: {html.escape(mode)}"}, 400)
            return

        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=STRATEGY_TIMEOUT_SECONDS)
            output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
            self._send_json({"output": output, "returncode": p.returncode})
        except subprocess.TimeoutExpired:
            self._send_json(
                {"error": f"运行超时（{STRATEGY_TIMEOUT_SECONDS}秒）: 请缩小股票池、降低重试次数，或改用 DB Only。"},
                500,
            )


def main():
    url = f"http://{HOST}:{PORT}"
    print(f"Web UI running on {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
