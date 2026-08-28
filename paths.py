"""路径处理：区分「数据目录」与「资源目录」，兼容开发态与 PyInstaller 打包态。

- app_dir()   : 可写目录，exe 同级目录（config.json / rank.db / check.log 都放这里）
- resource_dir(): 只读资源目录（如 templates），打包后从 sys._MEIPASS 读取
"""
import os
import sys


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir(subdir=""):
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, subdir)
    return os.path.join(app_dir(), subdir)
