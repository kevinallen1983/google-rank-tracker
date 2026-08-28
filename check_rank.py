"""无头每日检查脚本：供 Windows 任务计划程序定时调用。

逻辑：
1. 读取 config.json（域名 / API key / 搜索参数 / 关键词）
2. 初始化数据库并以配置文件关键词做首次种子
3. 逐个关键词查询谷歌排名并写入 ranks 表（(keyword, day) 去重）
4. 全程记录日志到 check.log，单个关键词失败不影响其它关键词

用法：
    python check_rank.py            # 检查配置里全部关键词
    python check_rank.py --keyword "custom inflatable tent"   # 只查某一个
"""
import argparse
import datetime
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rank_db
from paths import app_dir
from serp_client import check_rank as serp_check_rank

BASE_DIR = app_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "check.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("rank-check")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run(keyword_filter=None):
    cfg = load_config()
    domain = cfg.get("domain", "")
    provider = cfg.get("provider", "serper")
    providers = cfg.get("providers", {})
    prov_cfg = providers.get(provider, {})
    api_key = prov_cfg.get("api_key") or cfg.get("api_key", "")
    serp = cfg.get("serp", {})
    max_results = int(serp.get("max_pages", 5)) * 10

    if not api_key:
        logger.error(f"未配置 {provider} 的 API Key，请在 config.json 中设置")
        return
    if not domain:
        logger.error("未配置 domain，请在 config.json 中设置")
        return

    rank_db.init_db()
    rank_db.seed_keywords(cfg.get("keywords", []))

    keywords = rank_db.list_keywords()
    if keyword_filter:
        keywords = [k for k in keywords if k == keyword_filter]
    if not keywords:
        logger.warning("没有可检查的关键词。")
        return

    today = datetime.date.today().isoformat()
    checked_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok, miss, err = 0, 0, 0

    for kw in keywords:
        try:
            res = serp_check_rank(
                keyword=kw,
                domain=domain,
                provider=provider,
                max_results=max_results,
            )
            pos = res.get("rank")
            url = res.get("found_url")
            error = res.get("error")
            if error:
                logger.error(f"[{kw}] 检查失败：{error}")
                err += 1
                continue
            rank_db.upsert_rank(kw, today, pos, url, checked_at)
            if pos is None:
                logger.info(f"[{kw}] 未进入前 {max_results} 名（已记录为未上榜）")
                miss += 1
            else:
                logger.info(f"[{kw}] 第 {pos} 名 -> {url} (via {res.get('provider')})")
                ok += 1
            time.sleep(1.0)  # 礼貌性间隔，避免触发限流
        except Exception as e:
            logger.error(f"[{kw}] 检查失败：{e}")
            err += 1

    logger.info(f"完成：上榜 {ok} / 未上榜 {miss} / 失败 {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google 排名每日检查")
    parser.add_argument("--keyword", help="只检查指定关键词", default=None)
    args = parser.parse_args()
    logger.info("=== 开始每日排名检查 ===")
    try:
        run(args.keyword)
    except Exception as e:
        logger.exception(f"整体运行异常：{e}")
    logger.info("=== 检查结束 ===\n")
