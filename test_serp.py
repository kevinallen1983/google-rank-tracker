"""诊断脚本：测试所有已配置的 SERP provider。

用标准库 urllib，不依赖 requests，避免环境问题。
输出会重定向到 result.txt，请把 result.txt 发给排查方。
"""
import json
import os
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "config.json"), "r", encoding="utf-8") as f:
    cfg = json.load(f)

q = "inflatable beach tent"
hl = cfg.get("serp", {}).get("hl", "en")
gl = cfg.get("serp", {}).get("gl", "us")
device = cfg.get("serp", {}).get("device", "default")
domain = cfg.get("domain", "kcce-event.com")

def normalize_domain(d):
    d = d.lower().strip()
    if d.startswith("http://") or d.startswith("https://"):
        d = d.split("/", 2)[2]
    if d.startswith("www."):
        d = d[4:]
    return d.rstrip("/")

target = normalize_domain(domain)


def test_provider(name, prov_cfg):
    print("\n" + "=" * 60)
    print("Provider: %s" % name)
    print("Endpoint: %s" % (prov_cfg.get("endpoint") or "(not set)"))
    api_key = (prov_cfg.get("api_key") or "").strip()
    if not api_key:
        print("Result: API key is empty, skip")
        return
    print("API key prefix: %s..." % api_key[:8])

    endpoint = prov_cfg.get("endpoint", "")

    is_serper = "serper" in name.lower() or "serper" in endpoint.lower()
    is_serpbase = "serpbase" in name.lower() or "serpbase" in endpoint.lower()

    if is_serper:
        payload = {
            "q": q,
            "hl": hl,
            "gl": gl,
            "num": 100,
        }
        if device and device != "default":
            payload["device"] = device
        headers = {"Content-Type": "application/json", "X-API-KEY": api_key}
    elif is_serpbase:
        # SerpBase 实测不支持 num / device 参数，传 num 会返回 1000 invalid request。
        # 只能按 page 翻页，page=1 返回约 9 条，page>=2 每页约 10 条。
        payload = {"q": q, "hl": hl, "gl": gl}
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            # SerpBase 的 Cloudflare 会拦截无 User-Agent 的请求
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
    else:
        payload = {"q": q, "hl": hl, "gl": gl, "num": 100}
        headers = {"Content-Type": "application/json"}

    # 解析 organic
    def parse_organic(d):
        if "organic" in d:
            return d.get("organic") or []
        if "results" in d:
            return d.get("results") or []
        return []

    organic = []
    seen = set()

    if is_serpbase:
        # SerpBase：按 page 翻页
        page = 1
        while len(organic) < 100 and page <= 10:
            page_payload = dict(payload)
            page_payload["page"] = page
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(page_payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.loads(r.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                print("Result: HTTP Error %s: %s" % (e.code, e.reason))
                print("Response body: %s" % body[:800])
                return
            except Exception as e:
                print("Result: Request failed: %s" % e)
                return

            page_organic = parse_organic(data)
            new_items = [it for it in page_organic if it.get("link") and it.get("link") not in seen]
            if not new_items:
                break
            organic.extend(new_items)
            seen.update(it.get("link") for it in new_items)
            page += 1
    else:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print("Result: HTTP Error %s: %s" % (e.code, e.reason))
            print("Response body: %s" % body[:800])
            return
        except Exception as e:
            print("Result: Request failed: %s" % e)
            return

        organic = parse_organic(data)

        # Serper：如果第一次请求结果不足 100 条，尝试 page 翻页补足
        if is_serper and 0 < len(organic) < 100:
            page = 2
            seen = {it.get("link") for it in organic}
            while len(organic) < 100 and page <= 10:
                payload["num"] = 10
                payload["page"] = page
                req2 = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req2, timeout=60) as r2:
                        data2 = json.loads(r2.read().decode("utf-8", errors="replace"))
                except Exception as e:
                    print("   Page %d fetch failed: %s" % (page, e))
                    break
                page_organic = parse_organic(data2)
                if not page_organic:
                    break
                new_items = [it for it in page_organic if it.get("link") and it.get("link") not in seen]
                if not new_items:
                    break
                organic.extend(new_items)
                seen.update(it.get("link") for it in new_items)
                page += 1

    print("Status: %s" % data.get("status", "unknown"))
    print("Organic count (after pagination): %d" % len(organic))

    hit = False
    for i, it in enumerate(organic):
        link = (it.get("link") or it.get("url") or "").lower()
        title = it.get("title") or ""
        pos = i + 1
        if target in link:
            print("   >>> HIT %s at position %d: %s" % (target, pos, link))
            hit = True
        elif i < 20:
            print("   %2d. %s" % (pos, link or title))

    if not hit:
        print("   Domain %s NOT found in top %d results" % (target, len(organic)))


print("Config provider: %s" % cfg.get("provider", "(not set)"))
print("Fallback providers: %s" % cfg.get("fallback_providers", []))
print("Target domain: %s" % target)
print("Keyword: %s" % q)
print("hl=%s gl=%s device=%s" % (hl, gl, device))

providers = cfg.get("providers", {})
for name, prov_cfg in providers.items():
    test_provider(name, prov_cfg)

print("\n" + "=" * 60)
print("Diagnosis finished.")
