"""SERP 查询客户端，支持多数据源（SerpBase / Serper.dev / ValueSERP 风格）。

使用策略：
1. config.json 中 `provider` 字段决定默认数据源（默认 serper）。
2. 每个 provider 可配置自己的 endpoint / api_key / 参数映射。
3. 如果默认 provider 失败，可尝试 fallback_providers 列表里的其他源。
4. 优先一次性抓取前 100 条（num=100），失败再降级为翻页。
"""
import json
import os
import time
import urllib.request
import urllib.error
from urllib.parse import urljoin


from paths import app_dir


def _load_config():
    # 必须用 app_dir() 而不是 __file__ 目录，否则 PyInstaller onefile 会读到
    # 临时解压目录 (_MEIPASS) 里的空配置，导致 API key 永远为空。
    path = os.path.join(app_dir(), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_domain(domain):
    d = (domain or "").lower().strip()
    if d.startswith("http://") or d.startswith("https://"):
        d = d.split("/", 2)[2]
    if d.startswith("www."):
        d = d[4:]
    return d.rstrip("/")


def _domain_in_link(domain, link):
    if not link:
        return False
    target = _normalize_domain(domain)
    link_norm = link.lower()
    # 支持 kcce-event.com 和 *.kcce-event.com 子域名
    if target in link_norm:
        return True
    # 也尝试匹配 www. 前缀
    if "www." + target in link_norm:
        return True
    return False


class SerpProvider:
    """通用 SERP provider 定义。"""

    name = "generic"

    def __init__(self, cfg):
        self.cfg = cfg
        self.provider_cfg = cfg.get("providers", {}).get(self.name, {})

    def api_key(self):
        # 优先读取 providers.<name>.api_key，兼容顶层 api_key
        key = self.provider_cfg.get("api_key")
        if not key:
            key = self.cfg.get("api_key")
        return (key or "").strip()

    def endpoint(self):
        return self.provider_cfg.get("endpoint") or self.default_endpoint()

    def default_endpoint(self):
        return ""

    def request(self, keyword, extra=None):
        """返回 (ok, result_dict_or_error_msg, raw_response_text)"""
        raise NotImplementedError

    def parse_organic(self, data):
        """从原始返回里解析出 [{'title', 'link', 'position'}, ...]"""
        raise NotImplementedError


class SerpBaseProvider(SerpProvider):
    name = "serpbase"

    def default_endpoint(self):
        return "https://api.serpbase.dev/google/search"

    def request(self, keyword, extra=None):
        extra = extra or {}
        endpoint = self.endpoint()
        api_key = self.api_key()
        if not api_key:
            return False, "API key not configured", ""

        # SerpBase 实测不支持 num 参数；传 num 会返回 1000 invalid request。
        # device 只接受 pc / mobile（不接受 desktop），默认不传入该字段。
        device = self.cfg.get("serp", {}).get("device", "default")
        if device == "desktop":
            device = "pc"

        payload = {
            "q": keyword,
            "hl": self.cfg.get("serp", {}).get("hl", "en"),
            "gl": self.cfg.get("serp", {}).get("gl", "us"),
        }
        if device and device != "default":
            payload["device"] = device
        if "page" in extra:
            payload["page"] = extra["page"]

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
                # SerpBase 的 Cloudflare 会拦截无 User-Agent 的请求，返回 403 error code: 1010
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                # SerpBase 有时 HTTP 200 但返回 status/error（如 1020 insufficient credits）。
                # 兼容两种成功标识：status=0（整数）或 status="ok"（字符串）。
                status = data.get("status")
                ok_status = status in (0, "ok", "OK", "success", "Success", None)
                if not ok_status:
                    err = data.get("error") or data.get("message") or "API error"
                    return False, f"API status {status}: {err}", raw
                return True, data, raw
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return False, f"HTTP Error {e.code}: {e.reason} (body: {body[:500]})", body
        except Exception as e:
            return False, f"Request failed: {e}", ""

    def parse_organic(self, data):
        organic = data.get("organic") or []
        out = []
        for it in organic:
            link = it.get("link") or it.get("url") or ""
            out.append({
                "title": it.get("title") or "",
                "link": link,
                # 这里只用做去重/显示，全局排名由 check_rank 重新按顺序编号
                "position": it.get("rank") or it.get("position") or 0,
            })
        return out


class SerperProvider(SerpProvider):
    name = "serper"

    def default_endpoint(self):
        return "https://google.serper.dev/search"

    def request(self, keyword, extra=None):
        extra = extra or {}
        endpoint = self.endpoint()
        api_key = self.api_key()
        if not api_key:
            return False, "API key not configured", ""

        payload = {
            "q": keyword,
            "hl": self.cfg.get("serp", {}).get("hl", "en"),
            "gl": self.cfg.get("serp", {}).get("gl", "us"),
            "num": extra.get("num", 100),
        }
        # Serper 的 device 可传 desktop/mobile，默认不传即可
        device = self.cfg.get("serp", {}).get("device", "default")
        if device and device != "default":
            payload["device"] = device
        if "page" in extra:
            payload["page"] = extra["page"]

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-KEY": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                return True, data, raw
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return False, f"HTTP Error {e.code}: {e.reason} (body: {body[:500]})", body
        except Exception as e:
            return False, f"Request failed: {e}", ""

    def parse_organic(self, data):
        organic = data.get("organic") or []
        out = []
        for it in organic:
            link = it.get("link") or ""
            out.append({
                "title": it.get("title") or "",
                "link": link,
                "position": it.get("position") or 0,
            })
        return out


PROVIDERS = {
    "serpbase": SerpBaseProvider,
    "serper": SerperProvider,
}


def _get_provider(cfg, name=None):
    name = (name or cfg.get("provider", "serper")).lower()
    cls = PROVIDERS.get(name, SerperProvider)
    return cls(cfg)


def check_rank(keyword, domain=None, provider=None, max_results=100, max_pages=None):
    """查询 keyword 在指定 domain 的排名。

    参数：
      max_results: 最多检查多少条结果（向后兼容）
      max_pages: 用户选择的"前 N 页"；优先用此值控制 Serper/SerpBase 的实际请求页数。
                 若未传，则按 max_results 折算（每页约 10 条）。

    返回 dict：
    {
        "provider": "serper",
        "keyword": "...",
        "domain": "...",
        "rank": 17,          # 未找到时为 None
        "found_url": "...",  # 命中链接
        "total_checked": 100,
        "raw_results": [...],# 前 N 条结果（用于调试）
        "error": None,       # 出错时填写
    }
    """
    # 用户前端选择"前 N 页"，后端应严格按 N 页控制 API 请求，避免多扣积分。
    if max_pages is None:
        max_pages = max(1, (max_results + 9) // 10)

    cfg = _load_config()
    domain = domain or cfg.get("domain", "")
    target = _normalize_domain(domain)

    provider_name = (provider or cfg.get("provider", "serper")).lower()
    providers_to_try = [provider_name]
    fallback = cfg.get("fallback_providers") or []
    for p in fallback:
        if p not in providers_to_try:
            providers_to_try.append(p)

    last_error = None
    for pname in providers_to_try:
        prov = _get_provider(cfg, pname)
        prov_api_key = prov.api_key()
        if not prov_api_key:
            last_error = f"[{pname}] API key not configured"
            continue

        # 辅助：在 organic 列表中查找目标域名，命中即停以节省积分。
        def _find_hit(organic_list):
            for idx, it in enumerate(organic_list, start=1):
                if _domain_in_link(target, it.get("link", "")):
                    return idx, it.get("link")
            return None, None

        # 辅助：构造返回结果
        def _build_result(organic_list):
            hit, hit_url = _find_hit(organic_list)
            raw_trimmed = [
                {"position": i + 1, "title": it.get("title", ""), "link": it.get("link", "")}
                for i, it in enumerate(organic_list[:max_results])
            ]
            return {
                "provider": pname,
                "keyword": keyword,
                "domain": target,
                "rank": hit,
                "found_url": hit_url,
                "total_checked": len(organic_list),
                "raw_results": raw_trimmed,
                "error": None,
            }

        organic = []

        if pname == "serpbase":
            # SerpBase 不支持 num 参数，只能按 page 翻页，每页约 9-10 条。
            # 免费 tier 限速 1 QPS，翻页太快会返回 1029 rate limit exceeded。
            page = 1
            seen_links = set()
            request_failed = False
            while len(organic) < max_results and page <= max_pages:
                if page > 1:
                    time.sleep(1.2)  # SerpBase free tier: 1 req/s
                ok, data, _ = prov.request(keyword, extra={"page": page})
                if not ok:
                    last_error = f"[{pname}] {data}"
                    request_failed = True
                    break
                page_organic = prov.parse_organic(data)
                if not page_organic:
                    break
                new_items = [it for it in page_organic if it.get("link") and it.get("link") not in seen_links]
                if not new_items:
                    break
                organic.extend(new_items)
                seen_links.update(it.get("link") for it in new_items)
                # 命中即停：已找到目标域名，不再浪费积分翻页
                if _find_hit(organic)[0]:
                    break
                page += 1
            if request_failed or not organic:
                if not last_error:
                    last_error = f"[{pname}] No organic results returned"
                continue
        else:
            # Serper：按 page 逐页抓取（每页 10 条），命中即停，避免浪费积分。
            # 一次性 num=50 的请求与后续 num=10/page 的翻页容易重叠且行为不可预测，
            # 因此采用固定 page size 的串行翻页。
            page = 1
            seen_links = set()
            request_failed = False
            while page <= max_pages:
                ok, data, _ = prov.request(keyword, extra={"num": 10, "page": page})
                if not ok:
                    last_error = f"[{pname}] {data}"
                    request_failed = True
                    break
                page_organic = prov.parse_organic(data)
                if not page_organic:
                    break
                new_items = [it for it in page_organic if it.get("link") and it.get("link") not in seen_links]
                if not new_items:
                    break
                organic.extend(new_items)
                seen_links.update(it.get("link") for it in new_items)
                # 命中即停：翻页过程中找到目标域名，立即停止
                if _find_hit(organic)[0]:
                    break
                page += 1
            if request_failed or not organic:
                if not last_error:
                    last_error = f"[{pname}] No organic results returned"
                continue

        return _build_result(organic)

    return {
        "provider": provider_name,
        "keyword": keyword,
        "domain": target,
        "rank": None,
        "found_url": None,
        "total_checked": 0,
        "raw_results": [],
        "error": last_error or "All providers failed",
    }


if __name__ == "__main__":
    # 简单自测
    r = check_rank("inflatable beach tent")
    print(json.dumps(r, ensure_ascii=False, indent=2))
