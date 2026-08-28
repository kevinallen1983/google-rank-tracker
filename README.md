# Google 排名每日监控工具

按知乎文章《如何使网站关键词排名靠前？》的方法实现：用 **SerpBase 的 SERP API** 查询谷歌自然搜索结果，自动找到你的域名排在第几名，落库到本地 SQLite，再用 Windows 任务计划程序每天定时跑一遍，看板上查看最新排名与历史趋势。

> 文章原方法用 `gl=cn`（中文谷歌），本工具默认改为 `gl=us / hl=en`，契合你做欧美 B2B 的场景。国家/语言可在看板里随时切换。

> **开源（MIT 许可证）**：欢迎 Issue 与 PR。本说明同时适用于从源码运行与参与开发。

## 密钥与隐私（务必先看）

- 你的 **SerpBase / Serper API Key**、域名、关键词都只存在本地 `config.json`，该文件已被 `.gitignore` 忽略，**不会**进入 git 仓库。
- 仓库仅提供 `config.example.json`（不含任何密钥）。首次运行前把它复制为 `config.json` 并填入你自己的 Key：
  ```bash
  # Windows
  copy config.example.json config.json
  # macOS / Linux
  cp config.example.json config.json
  ```
- `rank.db`（你的排名数据）同样被忽略，不会上传。
- **切勿**把含真实 Key 的 `config.json` 提交到 git 或粘贴到公开场合。

### 桌面版 exe 的数据存在哪里？

桌面版（`GoogleRankTracker.exe` / `GoogleRankTrackerDesktop.exe`）不会把配置写在 exe 旁边，而是写到当前 Windows 用户的数据目录：

```text
%APPDATA%\GoogleRankTracker\
├── config.json
├── rank.db
└── check.log
```

这样做的好处：
- 分发 exe 给别人时，不会把你的 API Key 和排名数据一起带过去；
- 同一台电脑上多个 Windows 用户各自有独立配置；
- 移动或重命名 exe 不会丢失自己的配置。

## 从源码运行（开发者 / 贡献者）

```bash
git clone <你的仓库地址>
cd google-rank-tracker
python -m venv venv
venv\Scripts\pip install -r requirements.txt      # Windows
# macOS / Linux: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
copy config.example.json config.json              # 然后填入你的 API Key 与域名
python app.py                                      # 看板：http://127.0.0.1:5000
```

打包成 exe 分发给无 Python 环境的用户，见「九、打包成 exe 分发版」。

---

## 一、它能做什么

- 管理你想盯的关键词（如 `custom inflatable tent`、`wholesale inflatable tube man`）
- 每天定时自动查询这些词在**指定国家谷歌**搜索里的排名（你的域名出现在第几名）
- 数据存本地 `rank.db`，随时可查、可导出、可与你的内容更新记录对照
- 看板展示：最新排名、较上次的升降、落地页 URL、30 天趋势折线图
- 成本极低：SerpBase 标准包 $10 = 2 万次查询，你这量级一年用不完一个包（注册还送 100 次免费额度）

---

## 二、第一次使用（3 步）

### 第 1 步：装 Python
本机需有 **Python 3.10+**，安装时务必勾选 **"Add Python to PATH"**。
下载：https://www.python.org/downloads/windows/

### 第 2 步：配置 API Key 与域名
1. 把仓库里的 `config.example.json` 复制为 `config.json`（首次运行 `start.bat` 也会自动生成一份空模板）：
   ```bash
   copy config.example.json config.json
   ```
2. 选择服务商并填入对应 Key（看板「基础配置」里也能改）：
   - **SerpBase**：打开 https://serpbase.dev 注册（送 100 次免费搜索），登录后复制 API Key，填进 `providers.serpbase.api_key`
   - **Serper.dev**：打开 https://serper.dev 注册获取 Key，填进 `providers.serper.api_key`
3. 在 `config.json` 里填好 `domain`（你的域名，不带 `www.`），并把 `provider` 设成你要用的服务商（`serper` 或 `serpbase`）

> 想换别的 SERP API 也可以：在 `config.json` 的 `providers` 增加一项并设好 `endpoint`（返回需含 `organic[]` 的 `rank`/`link` 字段），再改 `serp_client.py` 的解析逻辑即可。

### 第 3 步：启动看板
双击 **`start.bat`**（首次会自动建虚拟环境并安装依赖，稍等一两分钟）。
浏览器自动打开 http://127.0.0.1:5000

进去后：
1. 填「你的网站域名」（如 `kcce-event.com`，不用带 `www.`）
2. 选目标国家 `gl` 与语言 `hl`（默认美国/英语）
3. 在「监控关键词」里添加你要盯的词——**支持批量**：把多行关键词直接粘贴进文本框（每行一个，或用逗号/分号分隔），点「添加」一次加完
4. 点「立即检查全部」查所有词；**只想查某一个词时，点该词右侧的「检查」按钮，单独查它**
5. 没 Key 想先预览界面？点「生成演示数据」看效果

---

## 三、设置「每天定时检查」

1. **双击** `setup_schedule.bat` 即可（脚本会自动检测管理员权限，不够就弹 UAC 请求提权，无需手动右键）
2. 它会创建名为 `GoogleRankTrackerDaily` 的 Windows 任务，默认**每天 09:00** 自动跑 `run_check.bat`
3. 验证：任务计划程序 → 找到该任务，可手动「运行」一次测试；日志写在 `check.log`

> 改时间：编辑 `config.json` 的 `schedule.time`，或手动在任务计划程序里改触发器。
> 注意：电脑关机时任务不会跑；开机后若错过计划时间，可在任务属性勾选「如果错过计划开始时间，立即运行」。

### 取消定时（停止每天自动检查）

**方法一（推荐，双击即可）：** 双击 `remove_schedule.bat`，脚本会自动提权并删除 `GoogleRankTrackerDaily` 任务。

**方法二（图形界面）：** 任务计划程序 → 库 → 找到 `GoogleRankTrackerDaily` → 右键「删除」。

**方法三（命令行）：** 以管理员运行 cmd，执行：
```
schtasks /delete /tn "GoogleRankTrackerDaily" /f
```
> 取消后，存到 `rank.db` 里的历史数据不会丢，只是以后不再自动跑了。想恢复就再双击 `setup_schedule.bat`。

---

## 四、文件说明

| 文件 | 作用 |
|------|------|
| `start.bat` | 双击启动看板（自动建 venv + 装依赖 + 开浏览器） |
| `run_check.bat` | 无头检查脚本入口，供任务计划程序调用 |
| `setup_schedule.bat` | 注册 Windows 每日定时任务（双击自动提权） |
| `remove_schedule.bat` | 取消/删除定时任务（双击自动提权） |
| `setup_schedule.bat` | 注册 Windows 每日定时任务（需管理员） |
| `app.py` | Flask 看板后端（API + 页面） |
| `serp_client.py` | 调用 SerpBase API、解析域名排名 |
| `check_rank.py` | 每日检查核心逻辑（被 run_check.bat 调用） |
| `rank_db.py` | SQLite 存储（关键词表 + 每日排名表） |
| `config.json` | 域名 / API Key / 国家语言 / 检查深度 / 关键词（**已被 .gitignore 忽略，不入库**） |
| `rank.db` | 排名数据库（自动生成） |
| `check.log` | 每日检查的日志（自动生成） |
| `templates/index.html` | 看板前端页面 |

---

## 五、配置参数解释（config.json）

```json
{
  "domain": "your-domain.com",
  "provider": "serper",
  "providers": {
    "serper":   { "endpoint": "https://google.serper.dev/search",       "api_key": "" },
    "serpbase": { "endpoint": "https://api.serpbase.dev/google/search", "api_key": "" }
  },
  "serp": {
    "hl": "en",          // 界面语言：en / de / fr / es / pt-br ...
    "gl": "us",          // 目标国家：us / uk / ca / de / au ...
    "device": "default", // default / pc / mobile
    "max_pages": 5       // 翻页数：每页约10条，5=查前50名
  },
  "keywords": [ "custom inflatable tent", "..." ]
}
```

- `provider`：当前使用哪个服务商（`serper` 或 `serpbase`），只有对应 `providers.<name>.api_key` 会被读取。
- `schedule` 字段已废弃：定时任务由 Windows 任务计划程序（`setup_schedule.bat`）控制，不写在配置里。

- **检查深度 `max_pages`**：API 没有「一次返回 100 条」的参数，靠翻页实现。默认翻 5 页（约前 50 名）。想查前 100 名就设 10。翻得越深，单次消耗查询次数越多（仍极便宜）。
- 排名 `position` 为 `null` 表示当天该词**未进入**所查页数的前 N 名（不是第 0 名）。

---

## 六、查看与导出数据

- 看板「最新排名概览」表：关键词 / 最新排名 / 较上次升降 / 最近检查 / 落地页
- 「排名趋势」：选关键词看 30 天折线（纵轴第 1 名在顶部，越靠上越好）
- 直接查数据库（高级）：
  ```sql
  SELECT keyword, day, position FROM ranks WHERE keyword='custom inflatable tent' ORDER BY day;
  ```
  `rank.db` 是标准 SQLite 文件，可用 DB Browser for SQLite 打开导出 CSV。

---

## 七、常见问题

**Q：检查报 401 / 无结果？** 检查 API Key 是否填对、SerpBase 账户是否有额度。
**Q：排名一直显示「未上榜」？** 可能真没排进前 N 名；可把 `max_pages` 调大，或确认 `domain`/`gl`/`hl` 设置正确（用美国 IP 查美国词才准）。
**Q：能监控多个网站吗？** 当前按单域名设计。多站点复制一份目录、改 `config.json` 的 `domain`、各自建定时任务即可。
**Q：任务计划程序没跑？** 多数情况是 `setup_schedule.bat` 没成功注册任务（权限不足或电脑当时关机）。直接双击 `setup_schedule.bat` 即可，它会自动请求管理员权限创建任务；也可在「管理员命令提示符」中手动运行脚本里给出的 `schtasks /create ...` 命令。检查 `check.log` 有无报错。

---

## 八、成本参考（基于文章数据）

十几个关键词、每天查一次、翻 5 页 ≈ 每月 2000 次请求：
- SerpBase 标准包 $10 = 2 万次（永不过期），折合月成本约 **$1**，一年用不完。
- 比任何按月订阅的排名工具都便宜，且数据完全归你所有。

---

## 九、打包成 exe 分发版（对方无需装 Python）

本工具可打包为单个 `GoogleRankTracker.exe`，对方电脑不装 Python、不装任何环境，双击即用。

**打包步骤（开发机）：**
1. 装依赖：`python -m venv venv && venv\Scripts\pip install -r requirements.txt pyinstaller`
2. 打包（推荐直接用仓库里的 `.spec`，已包含 `templates` / `assets` 与图标）：
   ```
   venv\Scripts\pyinstaller GoogleRankTracker.spec
   ```
   如需手动指定：
   ```
   venv\Scripts\pyinstaller --noconsole --onefile --name GoogleRankTracker --add-data "templates;templates" --add-data "assets;assets" --icon "assets/icon.ico" app.py
   ```
3. 产物：`dist/GoogleRankTracker.exe`（约 14MB 单文件）。

**分发与运行：**
- 只需把 `GoogleRankTracker.exe` 发给对方，放到任意文件夹双击即可。
- 首次运行自动在同目录生成空白 `config.json` 与 `rank.db`，并打开浏览器看板。
- 对方填**自己的** SerpBase Key + 域名 + 关键词即可，**不携带你的任何配置/密钥**。
- 支持 Windows 10/11 64 位。首次可能被 Windows SmartScreen 拦截，点「仍要运行」即可。

**注意：** 打包机需与目标机同架构（当前为 64 位 Windows）。目标机必须能联网（查谷歌排名要调 SERP API）。若改了源码后重新打包，先 `rm -rf build dist __pycache__` 清缓存再打包，避免用到旧字节码（不要把 `.spec` 删掉）。

---

## 十、桌面窗口版（GoogleRankTrackerDesktop.exe）

除浏览器版外，还提供**纯桌面窗口版**：双击直接弹出一个原生软件窗口（内嵌 WebView2 渲染现有看板），不再弹出系统浏览器。两个版本后端逻辑一致、数据（config.json / rank.db）共用，可同时存在。

**打包步骤（开发机）：**
```
venv\Scripts\pyinstaller --noconsole --onefile --name GoogleRankTrackerDesktop --add-data "templates;templates" --hidden-import webview --collect-submodules webview desktop_app.py
```
产物：`dist/GoogleRankTrackerDesktop.exe`（约 16MB）。

**两种版本对比：**
| 版本 | 文件 | 双击后 |
|------|------|--------|
| 浏览器版 | `GoogleRankTracker.exe` | 自动打开系统浏览器访问 http://127.0.0.1:5000 |
| 桌面窗口版 | `GoogleRankTrackerDesktop.exe` | 直接弹出原生软件窗口（不弹浏览器） |

**注意事项：**
- 桌面窗口版后端默认跑在 **5001** 端口，与浏览器版 5000 不冲突，可同时运行。
- 依赖 **Microsoft Edge WebView2 运行时**（Win10 20H2 及以后 / Win11 基本自带）。若目标机缺失，软件会自动回退为打开系统浏览器，并提示到 https://go.microsoft.com/fwlink/p/?LinkId=2124703 安装 WebView2 后重试。
- 定时任务、检查、配置、导出等用法与浏览器版完全一致；定时任务动作指向桌面版 exe 自身（`--check`）。

---

## 十一、许可证

本项目以 **MIT License** 开源，详见仓库根目录的 [LICENSE](LICENSE) 文件。

- 可自由使用、修改、再分发，包括商业用途；唯一要求是保留版权声明与许可证文本。
- 软件按「原样」提供，作者不对使用后果承担责任。
