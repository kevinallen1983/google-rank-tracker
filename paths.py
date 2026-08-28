"""路径处理：区分「数据目录」与「资源目录」，兼容开发态与 PyInstaller 打包态。

- app_dir()   : 可写目录，exe 同级目录（config.json / rank.db / check.log 都放这里）
- resource_dir(): 只读资源目录（如 templates），打包后从 sys._MEIPASS 读取
"""
import os
import sys


def app_dir():
    """返回程序可写数据目录。

    - 开发态：源码所在目录（保持向后兼容）。
    - PyInstaller 打包态：Windows 用 %APPDATA%/GoogleRankTracker；其它系统 fallback 到用户主目录。
      不把 config.json / rank.db 放在 exe 同级目录，避免分发 exe 时泄露或读取他人配置。
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "GoogleRankTracker")
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d


def resource_dir(subdir=""):
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, subdir)
    return os.path.join(app_dir(), subdir)
