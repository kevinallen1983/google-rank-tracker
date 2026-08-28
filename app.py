"""Flask 看板：关键词管理 + 配置 + 手动检查 + 排名趋势。

启动：python app.py  （start.bat 会自动建 venv 并打开浏览器）
访问：http://127.0.0.1:5000
"""
import argparse
import csv
import datetime
import io
import json
import os
import sys
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, render_template, request, send_from_directory, Response, make_response

import rank_db
from paths import app_dir, resource_dir
from serp_client import check_rank as serp_check_rank

BASE_DIR = app_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__, template_folder=resource_dir("templates"))


@app.after_request
def add_cache_control_headers(response):
    """防止浏览器缓存HTML和JS，确保更新后能加载最新代码。"""
    if response.content_type and 'html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


DEFAULT_CONFIG = {
    "domain": "",
    "provider": "serper",
    "fallback_providers": [],
    "providers": {
        "serper": {
            "endpoint": "https://google.serper.dev/search",
            "api_key": ""
        },
        "serpbase": {
            "endpoint": "https://api.serpbase.dev/google/search",
            "api_key": ""
        }
    },
    "keywords": ["custom inflatable tent", "inflatable advertising tent"],
    "serp": {
        "hl": "en",
        "gl": "us",
        "device": "default",
        "max_pages": 5,
    },
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _sync_keywords_in_config(keywords):
    """将当前数据库里的关键词列表写回 config.json，保持两边一致。"""
    cfg = load_config()
    cfg["keywords"] = list(keywords)
    save_config(cfg)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/assets/<path:filename>")
def assets_files(filename):
    return send_from_directory(resource_dir("assets"), filename)


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = load_config()
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def post_config():
    data = request.get_json(force=True)
    cfg = load_config()
    cfg["domain"] = data.get("domain", cfg.get("domain", ""))
    cfg["provider"] = data.get("provider", cfg.get("provider", "serper"))

    # 兼容旧版单 api_key；优先写入当前 provider 的 api_key
    provider = cfg.get("provider", "serper")
    providers = cfg.setdefault("providers", DEFAULT_CONFIG["providers"].copy())
    if provider not in providers:
        providers[provider] = {"endpoint": "", "api_key": ""}
    # 仅在提交非空 api_key 时才更新；空字符串不覆盖已有 key，避免误清空
    api_key = data.get("api_key", "").strip() if isinstance(data.get("api_key", ""), str) else str(data.get("api_key", "")).strip()
    if api_key:
        providers[provider]["api_key"] = api_key
        cfg["api_key"] = api_key  # 保留顶层兼容
    if "endpoint" in data:
        providers[provider]["endpoint"] = data["endpoint"]

    serp = cfg.setdefault("serp", {})
    serp["hl"] = data.get("hl", serp.get("hl", "en"))
    serp["gl"] = data.get("gl", serp.get("gl", "us"))
    serp["device"] = data.get("device", serp.get("device", "default"))
    serp["max_pages"] = int(data.get("max_pages", serp.get("max_pages", 5)))
    save_config(cfg)
    return jsonify({"ok": True, "config": cfg})


@app.route("/api/keywords", methods=["GET"])
def get_keywords():
    return jsonify(rank_db.list_keywords())


@app.route("/api/keywords", methods=["POST"])
def add_keyword():
    data = request.get_json(force=True)
    kw = (data.get("keyword") or "").strip()
    if not kw:
        return jsonify({"ok": False, "msg": "关键词为空"}), 400
    added = rank_db.add_keyword(kw)
    _sync_keywords_in_config(rank_db.list_keywords())
    return jsonify({"ok": True, "added": added, "keyword": kw})


@app.route("/api/keywords", methods=["DELETE"])
def del_keyword():
    data = request.get_json(force=True)
    kw = (data.get("keyword") or "").strip()
    rank_db.remove_keyword(kw)
    _sync_keywords_in_config(rank_db.list_keywords())
    return jsonify({"ok": True, "keyword": kw})


@app.route("/api/keywords/batch", methods=["POST"])
def add_keywords_batch():
    """批量添加关键词：接收 {keywords:[...]}，自动去重、跳过空行与已存在词。"""
    data = request.get_json(force=True)
    kws = data.get("keywords", [])
    if isinstance(kws, str):
        kws = [kws]
    added = 0
    seen = set()
    for raw in kws:
        kw = (raw or "").strip()
        if not kw or kw in seen:
            continue
        seen.add(kw)
        if rank_db.add_keyword(kw):
            added += 1
    _sync_keywords_in_config(rank_db.list_keywords())
    return jsonify({"ok": True, "added": added, "received": len(seen)})


@app.route("/api/check", methods=["POST"])
def api_check():
    cfg = load_config()
    domain = cfg.get("domain", "")
    serp = cfg.get("serp", {})

    # 检查当前 provider 是否配置了 api_key
    provider = cfg.get("provider", "serper")
    providers = cfg.get("providers", {})
    prov_cfg = providers.get(provider, {})
    api_key = prov_cfg.get("api_key") or cfg.get("api_key", "")
    if not api_key:
        return jsonify({"ok": False, "msg": f"请先在配置中填写 {provider} API Key"}), 400
    if not domain:
        return jsonify({"ok": False, "msg": "请先在配置中填写你的域名"}), 400

    data = request.get_json(silent=True) or {}
    keyword_filter = data.get("keyword")

    rank_db.init_db()
    rank_db.seed_keywords(cfg.get("keywords", []))
    keywords = rank_db.list_keywords()
    if keyword_filter:
        keywords = [k for k in keywords if k == keyword_filter]

    today = datetime.date.today().isoformat()
    checked_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results = []
    max_pages = int(serp.get("max_pages", 5))
    for kw in keywords:
        try:
            res = serp_check_rank(
                keyword=kw,
                domain=domain,
                provider=provider,
                max_results=max_pages * 10,
                max_pages=max_pages,
            )
            pos = res.get("rank")
            url = res.get("found_url")
            error = res.get("error")
            rank_db.upsert_rank(kw, today, pos, url, checked_at, is_demo=0)
            results.append({
                "keyword": kw,
                "position": pos,
                "url": url,
                "provider": res.get("provider"),
                "total_checked": res.get("total_checked"),
                "ok": error is None,
                "error": error,
            })
        except Exception as e:
            results.append({"keyword": kw, "position": None, "url": None,
                           "ok": False, "error": str(e)})
        time.sleep(1.0)
    return jsonify({"ok": True, "results": results, "checked_at": checked_at})


@app.route("/api/overview", methods=["GET"])
def api_overview():
    rank_db.init_db()
    return jsonify(rank_db.get_overview())


@app.route("/api/export", methods=["GET"])
def api_export():
    """导出最新排名概览为 CSV（UTF-8 BOM，Excel 可直接打开，中文不乱码）。"""
    rank_db.init_db()
    rows = rank_db.get_overview()

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "关键词", "最新排名", "排名变化", "上一次排名",
        "落地页URL", "数据来源", "最近检查日期", "最近检查时间",
    ])
    for r in rows:
        pos = r.get("position")
        prev = r.get("prev_position")
        change = r.get("change")
        is_demo = r.get("is_demo", 0) or 0

        pos_text = "未上榜" if pos is None else pos
        prev_text = "" if prev is None else prev

        if pos is None:
            change_text = "未上榜"
        elif change is None:
            change_text = "新上榜"
        elif change > 0:
            change_text = f"上升 {change} 位"
        elif change < 0:
            change_text = f"下降 {abs(change)} 位"
        else:
            change_text = "持平"

        writer.writerow([
            r.get("keyword", ""),
            pos_text,
            change_text,
            prev_text,
            r.get("url") or "",
            "演示" if is_demo else "真实",
            r.get("day") or "",
            r.get("checked_at") or "",
        ])

    csv_bytes = buf.getvalue().encode("utf-8-sig")  # utf-8-sig 自动写入 BOM
    today = datetime.date.today().isoformat()
    filename = f"ranking-overview-{today}.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/api/import", methods=["POST"])
def api_import():
    """从 CSV 文件导入排名数据（UTF-8 BOM）。支持通过导出功能生成的 CSV。"""
    rank_db.init_db()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "msg": "请选择 CSV 文件"}), 400
    raw = f.read()
    # utf-8-sig 自动去掉 BOM，没有 BOM 也能正常读
    text = raw.decode("utf-8-sig", errors="replace")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return jsonify({"ok": False, "msg": "文件为空"}), 400
    reader = csv.reader(lines)
    header = [h.strip() for h in next(reader)]
    # 建立列索引映射（按表头名称匹配，兼容列顺序变化）
    col_map = {}
    for idx, h in enumerate(header):
        if h in ("关键词", "keyword"):
            col_map["keyword"] = idx
        elif h in ("最新排名", "position", "rank"):
            col_map["position"] = idx
        elif h in ("落地页URL", "url"):
            col_map["url"] = idx
        elif h in ("最近检查日期", "day"):
            col_map["day"] = idx
        elif h in ("最近检查时间", "checked_at", "checkedat"):
            col_map["checked_at"] = idx
    today = datetime.date.today().isoformat()
    inserted = 0
    skipped = 0
    for row in reader:
        kw = row[col_map["keyword"]].strip() if "keyword" in col_map and col_map["keyword"] < len(row) else ""
        if not kw:
            skipped += 1
            continue
        # 注册关键词（已存在则跳过）
        rank_db.add_keyword(kw)
        # 解析 position
        pos_raw = row[col_map["position"]].strip() if "position" in col_map and col_map["position"] < len(row) else ""
        pos = None
        if pos_raw and pos_raw not in ("未上榜", "未上榜（占位）", "", "—"):
            try:
                pos = int(pos_raw)
            except ValueError:
                # 兼容 "12.0" 这类带小数的排名文本（导出/第三方 CSV 常见）
                try:
                    pos = int(float(pos_raw))
                except ValueError:
                    pos = None
        url = (row[col_map["url"]].strip() if "url" in col_map and col_map["url"] < len(row) else "") or None
        day_raw = row[col_map["day"]].strip() if "day" in col_map and col_map["day"] < len(row) else ""
        # 标准化导入日期：兼容 2026/8/26、2026.08.26 等
        day = rank_db.normalize_day(day_raw) if day_raw else today
        checked_at_raw = (row[col_map["checked_at"]].strip() if "checked_at" in col_map and col_map["checked_at"] < len(row) else "") or None
        checked_at = rank_db.normalize_checked_at(checked_at_raw) if checked_at_raw else None
        rank_db.upsert_rank(kw, day, pos, url, checked_at, is_demo=0)
        inserted += 1
    return jsonify({"ok": True, "inserted": inserted, "skipped": skipped,
                    "msg": f"导入完成：新增 {inserted} 条，跳过 {skipped} 条（关键词为空）"})


@app.route("/api/history", methods=["GET"])
def api_history():
    kw = request.args.get("keyword", "")
    days_raw = request.args.get("days", "")
    days = None
    if days_raw:
        try:
            days = int(days_raw)
        except ValueError:
            days = None
    return jsonify(rank_db.get_history(kw, days))


@app.route("/api/demo", methods=["POST"])
def api_demo():
    """填充 30 天模拟数据，方便无 API Key 先预览看板效果。"""
    rank_db.init_db()
    rank_db.seed_keywords(load_config().get("keywords", []))
    keywords = rank_db.list_keywords() or ["custom inflatable tent",
                                           "inflatable advertising tent"]
    today = datetime.date.today()
    import random
    random.seed(42)
    for kw in keywords:
        base = random.randint(3, 25)
        for i in range(30, -1, -1):
            d = (today - datetime.timedelta(days=i)).isoformat()
            # 不覆盖当天已有的真实检查数据；演示数据仅填补空缺日期
            existing = rank_db.get_row(kw, d)
            if existing and (existing.get("is_demo") or 0) == 0:
                continue
            pos = max(1, base + random.randint(-4, 4) - int((30 - i) / 6))
            url = f"https://{load_config().get('domain','yourdomain.com')}/product/{kw.replace(' ', '-')}"
            rank_db.upsert_rank(kw, d, pos, url,
                                f"{d} 09:00:00", is_demo=1)
    return jsonify({"ok": True, "msg": "已生成 30 天演示数据（仅用于预览，URL 为占位示例，不会覆盖真实检查数据）"})


@app.route("/api/clear-demo", methods=["POST"])
def api_clear_demo():
    """只删除演示数据（is_demo=1），保留真实检查记录。"""
    rank_db.init_db()
    deleted = rank_db.delete_demo_rows()
    return jsonify({"ok": True, "deleted": deleted,
                    "msg": f"已清空演示数据 {deleted} 条，真实排名数据不受影响。"})


def _pick_port(preferred):
    """优先用 preferred；若被占用则依次尝试 +1/+2/+3，返回可用的端口。

    避免「旧进程仍占用 5000，导致新 exe 无法绑定 / 浏览器命中旧服务而显示旧页面」。
    """
    import socket
    for p in [preferred, preferred + 1, preferred + 2, preferred + 3]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            continue
    return preferred  # 都不可用则硬试首选端口，让 Flask 报错更明确


def main():
    parser = argparse.ArgumentParser(description="Google 排名监控")
    parser.add_argument("--no-browser", action="store_true",
                        help="启动看板但不自动打开浏览器")
    parser.add_argument("--port", type=int, default=5000,
                        help="看板端口（默认 5000）")
    args = parser.parse_args()

    # 默认：启动 Web 看板
    rank_db.init_db()
    rank_db.seed_keywords(load_config().get("keywords", []))
    port = _pick_port(args.port)
    if port != args.port:
        print(f"端口 {args.port} 已被占用，改用 {port}")
    if not args.no_browser:
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:
            pass
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
