# -*- coding: utf-8 -*-
"""
行情查询 HTTP 服务(零依赖版)
================================
作用:把 A 股行情查询包装成 HTTP 接口,供阿里云百炼自定义插件调用。

** 重点:本版本只用 Python 标准库,不需要 pip install 任何东西。**
   数据直接来自新浪/腾讯的公开行情接口,免费、无需 token、无需积分。

保留两个接口(和之前一致,百炼插件/OpenAPI 不用改):
    POST /quote/realtime   实时行情
    POST /quote/daily      日线历史

FC 部署:
    - 代码只放这一个文件到 /code
    - 启动命令(Startup Command)就一句:
          python /code/tushare_quote_service.py
    - 监听端口(Port):9000
    - 不需要 requirements.txt,不需要 Layer,不需要环境变量。

本地自测:
    python tushare_quote_service.py
    然后 POST http://127.0.0.1:9000/quote/realtime  body: {"ts_codes":["600519","000001"]}
"""

import os
import re
import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 监听端口:优先读环境变量,默认 9000(和 FC 的 Port 配置保持一致)
PORT = int(os.getenv("FC_SERVER_PORT") or os.getenv("PORT") or 9000)

# 通用请求头,避免被行情源拒绝
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _http_get(url, referer=None, encoding="utf-8"):
    """标准库发起 GET 请求,返回文本。"""
    headers = {"User-Agent": _UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
    return raw.decode(encoding, errors="ignore")


def _to_sina_symbol(code):
    """
    把各种写法的股票代码统一成新浪格式:
      600519.SH / 600519 -> sh600519
      000001.SZ / 000001 -> sz000001
      430047.BJ          -> bj430047
    """
    code = str(code).strip().upper()
    if "." in code:
        num, _, ex = code.partition(".")
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(ex, "")
        if prefix:
            return prefix + num
        code = num  # 后缀不认识,退回按首位猜
    # 纯数字,按首位猜交易所
    if code.startswith("6"):
        return "sh" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sz" + code


# ---------- 接口 1:实时行情(新浪源) ----------
def get_realtime(ts_codes):
    """
    输入:["600519","000001"] 这类代码列表
    输出:每只股票的最新价、涨跌、开高低收、成交量等
    """
    symbols = [_to_sina_symbol(c) for c in ts_codes]
    if not symbols:
        return []
    url = "https://hq.sinajs.cn/list=" + ",".join(symbols)
    text = _http_get(url, referer="https://finance.sina.com.cn", encoding="gbk")

    results = []
    # 每行形如: var hq_str_sh600519="贵州茅台,1688.00,...";
    for line in text.split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = re.search(r'hq_str_(\w+)="([^"]*)"', line)
        if not m:
            continue
        sym, payload = m.group(1), m.group(2)
        f = payload.split(",")
        if len(f) < 32:
            results.append({"symbol": sym, "message": "无数据或代码错误"})
            continue
        results.append({
            "symbol": sym,
            "name": f[0],
            "open": f[1],
            "pre_close": f[2],
            "price": f[3],       # 当前价
            "high": f[4],
            "low": f[5],
            "volume": f[8],      # 成交量(股)
            "amount": f[9],      # 成交额(元)
            "date": f[30],
            "time": f[31],
        })
    return results


# ---------- 接口 2:日线历史(新浪源) ----------
def get_daily(ts_code, start_date, end_date):
    """
    输入:ts_code=600519.SH, start_date=20240101, end_date=20241231
    输出:该区间内的日K线(开高低收、成交量)
    数据来自新浪,免费无需 token。
    """
    symbol = _to_sina_symbol(ts_code)
    # datalen 取够大,拉近 3 年再按日期过滤(约 750 个交易日)
    url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           "CN_MarketData.getKLineData?symbol={}&scale=240&ma=no&datalen=1023").format(symbol)
    text = _http_get(url, referer="https://finance.sina.com.cn", encoding="utf-8")
    text = text.strip()
    if not text or text == "null":
        return []
    try:
        rows = json.loads(text)
    except Exception:
        # 少数情况下 key 没加引号,做一次兜底修复
        fixed = re.sub(r'(\w+):', r'"\1":', text)
        rows = json.loads(fixed)

    s = str(start_date).replace("-", "")
    e = str(end_date).replace("-", "")
    out = []
    for r in rows:
        day = str(r.get("day", "")).replace("-", "")
        if not day:
            continue
        if s and day < s:
            continue
        if e and day > e:
            continue
        out.append({
            "trade_date": r.get("day"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "close": r.get("close"),
            "volume": r.get("volume"),
        })
    return out


# ---------- HTTP 路由 ----------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 关掉默认访问日志,保持 FC 日志干净

    def do_GET(self):
        # 健康检查 / 浏览器直接访问
        if self.path.rstrip("/") in ("", "/health"):
            self._send(200, {"status": "ok", "service": "quote", "port": PORT})
        else:
            self._send(405, {"detail": "请用 POST 调用该接口"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception as ex:
            self._send(400, {"detail": "请求体不是合法 JSON: %s" % ex})
            return

        path = self.path.split("?")[0].rstrip("/")
        try:
            if path == "/quote/realtime":
                codes = data.get("ts_codes") or []
                if isinstance(codes, str):
                    codes = [codes]
                self._send(200, {"data": get_realtime(codes)})
            elif path == "/quote/daily":
                self._send(200, {"data": get_daily(
                    data.get("ts_code", ""),
                    data.get("start_date", ""),
                    data.get("end_date", ""),
                )})
            else:
                self._send(404, {"detail": "未知路径,可用: /quote/realtime, /quote/daily"})
        except Exception as ex:
            self._send(500, {"detail": str(ex)})


if __name__ == "__main__":
    print("行情服务启动,监听 0.0.0.0:%d" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
