"""桌面窗口版入口：Flask 后台线程 + PyWebView 原生窗口（不打开系统浏览器）。

浏览器版（app.py / GoogleRankTracker.exe）保留不动；本文件是额外的「纯软件窗口」入口。
双击后看到的是一个原生软件窗口，里面就是现有的网页看板，不再弹出浏览器。

打包命令：
    pyinstaller --noconsole --onefile --name GoogleRankTrackerDesktop \
        --add-data "templates;templates" --hidden-import webview desktop_app.py

说明：
- 后端 Flask 在后台线程跑在 127.0.0.1:5001（与浏览器版 5000 区分，可共存）。
- 若目标机未安装 Microsoft Edge WebView2 运行时，自动回退为打开系统浏览器并提示。
"""
import ctypes
import os
import socket
import sys
import threading
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rank_db
from app import app as flask_app, load_config
from paths import app_dir, resource_dir

DESKTOP_PORT = 5001


def _log(msg):
    try:
        with open(os.path.join(app_dir(), "desktop.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass


def _wait_port(host, port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def start_flask():
    """在后台线程启动 Flask 看板（桌面窗口版专用端口）。"""
    rank_db.init_db()
    rank_db.seed_keywords(load_config().get("keywords", []))
    flask_app.run(host="127.0.0.1", port=DESKTOP_PORT, debug=False, use_reloader=False)


def _set_window_icon(icon_path, title="Google 排名监控"):
    """通过 Win32 API 给已创建的桌面窗口设置图标（PyWebView 不暴露该参数时兜底）。"""
    try:
        user32 = ctypes.windll.user32
        WM_SETICON = 0x80
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x10

        hicon = user32.LoadImageW(0, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
        if not hicon:
            _log(f"LoadImageW 图标失败: {icon_path}")
            return False

        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return False

        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        return True
    except Exception as e:
        _log(f"设置窗口图标异常: {repr(e)}")
        return False


def _wait_and_set_icon(icon_path, timeout=15):
    """在新线程中等待窗口出现并设置图标。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _set_window_icon(icon_path):
            _log("窗口图标已设置")
            return
        time.sleep(0.3)
    _log("窗口图标设置超时")


def main():
    # 默认：启动 Flask 后台线程 + 原生窗口
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    if not _wait_port("127.0.0.1", DESKTOP_PORT):
        _log("Flask 端口未就绪，回退浏览器")
        webbrowser.open(f"http://127.0.0.1:{DESKTOP_PORT}/")
        input("服务启动失败，已尝试打开浏览器。按回车退出。")
        return

    url = f"http://127.0.0.1:{DESKTOP_PORT}/"
    try:
        import webview

        _log("启动 PyWebView 原生窗口")
        icon_path = os.path.join(resource_dir("assets"), "icon.ico")
        if os.path.isfile(icon_path):
            threading.Thread(
                target=_wait_and_set_icon, args=(icon_path,), daemon=True
            ).start()
        else:
            _log(f"未找到窗口图标: {icon_path}")

        webview.create_window(
            "Google 排名监控",
            url,
            width=1120,
            height=840,
            resizable=True,
            text_select=True,
        )
        webview.start()
    except Exception as e:  # noqa
        _log("PyWebView 启动失败：" + repr(e))
        # WebView2 运行时缺失时的兜底方案
        webbrowser.open(url)
        input(
            "未能加载桌面窗口（很可能未安装 Microsoft Edge WebView2 运行时）。\n"
            "已改用系统浏览器打开。请到 https://go.microsoft.com/fwlink/p/?LinkId=2124703 安装 WebView2 后重试。\n"
            "按回车退出。"
        )


if __name__ == "__main__":
    main()
