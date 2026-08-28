"""SQLite 存储层：关键词表 + 每日排名表。

设计要点：
- keywords 表是关键词的"唯一来源"（看板与无头脚本都读它）。
- ranks 表用 (keyword, day) 做主键，天然一天一条、自动去重。
- position 为 None 表示当天该词未进入所查页数的前 N 名。
"""
import datetime
import os
import re
import sqlite3

from paths import app_dir

DB_PATH = os.path.join(app_dir(), "rank.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ranks (
            keyword TEXT NOT NULL,
            day TEXT NOT NULL,
            position INTEGER,
            url TEXT,
            checked_at TEXT,
            is_demo INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (keyword, day)
        )
        """
    )
    # 老库兼容：补上 is_demo 列（演示数据标记，避免与真实检查数据混淆）
    cols = [c[1] for c in conn.execute("PRAGMA table_info(ranks)").fetchall()]
    if "is_demo" not in cols:
        conn.execute("ALTER TABLE ranks ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


def seed_keywords(keyword_list):
    """首次运行时，用配置文件里的关键词初始化（已存在则跳过）。"""
    conn = get_conn()
    for kw in keyword_list:
        conn.execute(
            "INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (kw.strip(),)
        )
    conn.commit()
    conn.close()


def add_keyword(keyword):
    keyword = (keyword or "").strip()
    if not keyword:
        return False
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (keyword,)
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


def remove_keyword(keyword):
    conn = get_conn()
    conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
    conn.execute("DELETE FROM ranks WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()


def list_keywords():
    conn = get_conn()
    rows = conn.execute(
        "SELECT keyword FROM keywords ORDER BY id"
    ).fetchall()
    conn.close()
    return [r["keyword"] for r in rows]


def normalize_day(day):
    """把各种日期字符串统一转为 ISO YYYY-MM-DD。兼容 2026/8/26、2026.08.26、Aug 26 2026 等。"""
    if not day:
        import datetime
        return datetime.date.today().isoformat()
    s = str(day).strip()
    # 已经是 ISO 格式
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # 尝试用常见分隔符解析
    for sep in ("/", ".", "-"):
        parts = [p.strip() for p in s.split(sep) if p.strip()]
        if len(parts) == 3:
            try:
                nums = [int(p) for p in parts]
            except ValueError:
                continue
            # 2026/8/26 或 2026-08-26
            if nums[0] > 1900:
                y, m, d = nums[0], nums[1], nums[2]
            # 8/26/2026 美式
            elif nums[2] > 1900:
                m, d, y = nums[0], nums[1], nums[2]
            else:
                continue
            import datetime
            return datetime.date(y, m, d).isoformat()
    # 尝试用 dateutil / datetime 解析英文日期
    try:
        import datetime
        dt = datetime.datetime.strptime(s, "%b %d %Y")
        return dt.date().isoformat()
    except ValueError:
        pass
    try:
        import datetime
        dt = datetime.datetime.strptime(s, "%B %d %Y")
        return dt.date().isoformat()
    except ValueError:
        pass
    return s  # 解析不了原样返回，由上层决定


def normalize_checked_at(checked_at):
    """把检查时间统一转为 YYYY-MM-DD HH:MM:SS。"""
    if not checked_at:
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = str(checked_at).strip()
    # 已经是标准格式
    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", s):
        return s
    # 尝试 2026/8/26 9:00
    try:
        import datetime
        dt = datetime.datetime.strptime(s, "%Y/%m/%d %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    try:
        import datetime
        dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    return s


def upsert_rank(keyword, day, position, url, checked_at, is_demo=0):
    conn = get_conn()
    day = normalize_day(day)
    checked_at = normalize_checked_at(checked_at) if checked_at else checked_at
    conn.execute(
        """
        INSERT INTO ranks (keyword, day, position, url, checked_at, is_demo)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(keyword, day) DO UPDATE SET
            position = excluded.position,
            url = excluded.url,
            checked_at = excluded.checked_at,
            is_demo = excluded.is_demo
        """,
        (keyword, day, position, url, checked_at, is_demo),
    )
    conn.commit()
    conn.close()


def get_latest(keyword):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM ranks WHERE keyword = ? ORDER BY day DESC LIMIT 1",
        (keyword,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_row(keyword, day):
    """返回指定 (关键词, 日期) 的单条记录，用于判断该天是否已有真实数据。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM ranks WHERE keyword = ? AND day = ?",
        (keyword, day),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_previous(keyword, before_day):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM ranks WHERE keyword = ? AND day < ? ORDER BY day DESC LIMIT 1",
        (keyword, before_day),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_history(keyword, days=None):
    """返回某关键词的历史排名。同一天多条记录时取 checked_at 最新的一条。

    days：可选，限制为「今天往前 N 天」（含今天）。None 或 <=0 表示不限制。
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT day, position, url, checked_at
        FROM ranks
        WHERE keyword = ?
        ORDER BY day ASC, checked_at DESC
        """,
        (keyword,),
    ).fetchall()
    conn.close()
    # 按天去重：同一天只保留 checked_at 最新的一条
    seen = {}
    for r in rows:
        day = r["day"]
        if day not in seen:
            seen[day] = dict(r)
    days_list = sorted(seen.keys())
    # 按时间范围过滤横轴天数
    if days and int(days) > 0:
        import datetime
        cutoff = (datetime.date.today() - datetime.timedelta(days=int(days) - 1)).isoformat()
        days_list = [d for d in days_list if d >= cutoff]
    return [seen[day] for day in days_list]


def delete_demo_rows():
    """删除全部演示数据（is_demo=1），返回删除条数。真实检查记录保留。"""
    conn = get_conn()
    cur = conn.execute("DELETE FROM ranks WHERE is_demo = 1")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_overview():
    """返回每个关键词的最新排名、与上一次相比的变化、最近检查时间。"""
    out = []
    for kw in list_keywords():
        latest = get_latest(kw)
        if not latest:
            out.append(
                {
                    "keyword": kw,
                    "position": None,
                    "prev_position": None,
                    "change": None,
                    "url": None,
                    "day": None,
                    "checked_at": None,
                    "is_demo": 0,
                }
            )
            continue
        prev = get_previous(kw, latest["day"])
        prev_pos = prev["position"] if prev else None
        change = None
        if latest["position"] is not None and prev_pos is not None:
            change = prev_pos - latest["position"]  # 正数=上升(名次变小)
        elif latest["position"] is not None and prev_pos is None:
            change = None  # 新上榜
        out.append(
            {
                "keyword": kw,
                "position": latest["position"],
                "prev_position": prev_pos,
                "change": change,
                "url": latest["url"],
                "day": latest["day"],
                "checked_at": latest["checked_at"],
                "is_demo": latest.get("is_demo", 0) or 0,
            }
        )
    return out
