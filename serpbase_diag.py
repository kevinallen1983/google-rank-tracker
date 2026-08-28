"""SerpBase 专项诊断脚本。

测试多种请求组合，帮助定位 SerpBase 请求失败或查不到排名的根因：
1. 哪些参数会导致 1000 invalid request
2. 哪些参数组合能正常返回
3. 翻页是否生效
4. 目标域名是否出现在结果中

输出保存到 serpbase_diag_result.txt。
"""
import json
import os
import time
import urllib.request
import urllib.error
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "config.json"), "r", encoding="utf-8") as f:
    cfg = json.load(f)

q = "inflatable beach tent"
endpoint = cfg.get("providers", {}).get("serpbase", {}).get(
    "endpoint", "https://api.serpbase.dev/google/search"
)
real_key = (cfg.get("providers", {}).get("serpbase", {}).get("api_key") or "").strip()
target = cfg.get("domain", "kcce-event.com").lower().strip()
if target.startswith("http://") or target.startswith("https://"):
    target = target.split("/", 2)[2]
if target.startswith("www."):
    target = target[4:]


def mask_key(k):
    if len(k) <= 12:
        return k[:4] + "****" + k[-4:] if len(k) > 8 else "****"
    return k[:6] + "..." + k[-6:]


def do_request(label, payload, api_key=None):
    api_key = api_key if api_key is not None else real_key
    print("\n" + "=" * 70)
    print("TEST: %s" % label)
    print("API key:  %s" % (mask_key(api_key) if api_key else "(none / empty)"))
    print("Request body: %s" % json.dumps(payload, ensure_ascii=False))

    headers = {
        "Content-Type": "application/json",
        # SerpBase Cloudflare 会拦截无 User-Agent 的请求
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            status = data.get("status")
            err = data.get("error")
            organic = data.get("organic") or []
            print("HTTP status: %s %s" % (r.status, r.reason))
            print("API status: %s  error: %s" % (status, err))
            print("Organic count: %d" % len(organic))
            if organic:
                print("First result: %s" % organic[0].get("link", "N/A"))
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print("HTTP Error %s: %s" % (e.code, e.reason))
        print("Body: %s" % body[:500])
        return None
    except Exception as e:
        print("Request failed: %s" % e)
        return None


def search_with_pagination():
    """按 SerpBase 正确方式（page 翻页）搜索，检查目标域名是否出现。"""
    print("\n" + "=" * 70)
    print("PAGINATED SEARCH for domain: %s" % target)
    organic_all = []
    seen = set()
    page = 1
    while len(organic_all) < 100 and page <= 10:
        if page > 1:
            time.sleep(1.2)  # SerpBase free tier: 1 req/s
        payload = {"q": q, "hl": "en", "gl": "us", "page": page}
        data = do_request("page=%d" % page, payload)
        if data is None:
            break
        organic = data.get("organic") or []
        new_items = [it for it in organic if it.get("link") and it.get("link") not in seen]
        if not new_items:
            print("No new results on page %d, stopping." % page)
            break
        organic_all.extend(new_items)
        seen.update(it.get("link") for it in new_items)
        page += 1

    print("\nTotal unique results checked: %d" % len(organic_all))
    hits = []
    for idx, it in enumerate(organic_all, start=1):
        link = it.get("link", "").lower()
        if target in link:
            hits.append((idx, link))
    if hits:
        for pos, link in hits:
            print(">>> HIT %s at position %d: %s" % (target, pos, link))
    else:
        print(">>> Domain %s NOT found in top %d results" % (target, len(organic_all)))
    return organic_all


print("SerpBase Diagnostic Report")
print("Generated at: %s" % datetime.datetime.now().isoformat())
print("Real key (masked): %s" % mask_key(real_key))
print("Target endpoint: %s" % endpoint)
print("Target domain: %s" % target)

# 1. 最小请求（已知能成功）
do_request("Minimal: q+gl+hl", {"q": q, "hl": "en", "gl": "us"})

# 2. 加 num 参数（已知会导致 1000 invalid request）
do_request("With num=10", {"q": q, "hl": "en", "gl": "us", "num": 10})

# 3. 加 device=desktop（SerpBase 不支持，会返回 1000 invalid request）
do_request("With device=desktop", {"q": q, "hl": "en", "gl": "us", "device": "desktop"})

# 4. 加 device=pc（SerpBase 桌面端正确参数）
do_request("With device=pc", {"q": q, "hl": "en", "gl": "us", "device": "pc"})

# 5. 用错 key（应返回 1001 unauthorized）
do_request("Wrong key", {"q": q, "hl": "en", "gl": "us"}, api_key="sk-fake000000000000000000000000000000000000")

# 6. 分页搜索目标域名
search_with_pagination()

print("\n" + "=" * 70)
print("Diagnosis finished.")
print("\nInterpretation guide:")
print("- 'Minimal: q+gl+hl' should return HTTP 200 / status 0 with organic results.")
print("- 'With num=10' returning status:1000 'invalid request' means SerpBase does NOT")
print("  support the num parameter in this endpoint.")
print("- 'With device=desktop' returning status:1000 means SerpBase uses 'pc' instead")
print("  of 'desktop' for desktop device type.")
print("- 'Wrong key' returning status:1001 'unauthorized' means SerpBase auth works.")
print("- If paginated search shows 0 hits for your domain, SerpBase simply returned")
print("  a different Google result set than Serper.dev; this is a data-source difference,")
print("  not a bug in this tool.")
