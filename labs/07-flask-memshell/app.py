#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""07-flask-memshell —— 不出网 SSTI：Jinja2 → Flask 内存马。

======================================================================
题目定位
======================================================================
本靶场模拟一个真实的「小型笔记服务」，把 SSTI 放进**业务逻辑**里，
而不是给你一个裸的模板输入框。攻击链有四个台阶：

  1. ``/profile``   用户名被拼进模板（有过滤）——确认 SSTI 存在，
                    并学会 ``{% print(...) %}`` 这类绕过 ``{{ }}`` 的手法。
  2. ``/admin``     Host 头被拼进模板（**无过滤**，但**不回显**）——
                    长 payload 的投递点，无回显（结果只进内存审计日志）。
  3. 写文件回显    无回显 + 不出网，先把命令结果写到 ``/app/echo/``，
                    再从 ``/echo/`` 取回（HTTP 侧信道）。
  4. 内存马         最终目标：把一条**新的路由**或一个
                    ``before_request`` 钩子注入运行中的 Flask 进程，
                    得到可反复调用的内存 webshell —— 全程不需要出网。

======================================================================
为什么内存马是「不出网」场景的正解
======================================================================
传统打法在内网/靶机里是反弹 shell：目标主动连回你的 VPS。
一旦容器切断出网（本靶场 entrypoint 里用 iptables 丢掉了新建的对外连接
与 DNS），反弹 shell、DNSLog 外带、外连下载全部失效。

内存马走的是**反向思路**：不要求目标出网，而是让目标把能力挂到
**已经存在的入站 HTTP 通道**上。对 Flask 来说就是两件事之一：

  * 往 ``app.url_map`` 加一条 Rule、并在 ``app.view_functions`` 里登记视图
    → 「路由型内存马」；
  * 往 ``app.before_request_funcs[None]`` 追加一个函数
    → 「Filter 型内存马」，对所有路径生效。

注意 Flask 的 ``setupmethod`` 保护：应用处理过第一个请求之后，
``add_url_rule`` / ``before_request`` 这些公开 API 会直接抛
``AssertionError``。所以真正的内存马必须**绕过公开 API**，
直接改底层数据结构 —— 这正是它作为「内存马」的要点，
也解释了为什么亲手打一遍比看十篇文章有用。

======================================================================
出题人备注（请勿删）
======================================================================
* 必须以 ``python app.py`` 启动，模块名才是 ``__main__``；
  这样 ``sys.modules['__main__'].__dict__['app']`` 这条链才成立。
  另一条更通用的链是 ``flask.globals.current_app``，不挑启动方式。
* ``/flag`` 由 entrypoint 从环境变量写入，不进镜像层。
* ``/report`` 的 admin bot 只允许访问本机地址，避免变成对外 SSRF。
* ``/profile`` 的过滤力度是**刻意标定**过的，见下方 ``_PROFILE_BAD``
  注释；不要随手加规则，否则这一关会变得无解。
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from urllib.parse import urlparse

import jwt
import requests
from flask import Flask, redirect, render_template_string, request, send_from_directory, url_for

from ssti_core import LabMeta, WafSpec
from ssti_core.labapp import mount_console, register_lab_api
from ssti_core.labmeta import THEMES
from ssti_core.level import Level, make
from ssti_core.levels import engine_titles

# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ssti-flask-memshell-secret")
app.config["FLAG_PATH"] = os.environ.get("FLAG_PATH", "/flag")

#: 命令输出回显目录（HTTP 可访问）。entrypoint 会把它建出来并放开写权限。
ECHO_DIR = os.environ.get("SSTI_ECHO_DIR", "/app/echo")
os.makedirs(ECHO_DIR, exist_ok=True)

#: 内存审计日志（只存元信息，**不存渲染内容** —— 否则就成了回显）
AUDIT_LOG: list[dict[str, object]] = []

USERS: dict[str, dict[str, str]] = {"admin": {"password": os.urandom(8).hex(), "role": "admin"}}

USERNAME_MAX = 4096

#: ``/profile`` 的过滤：模板定界符 ``{{`` ``}}``、引号、方括号。
#: 点号与圆括号放行，所以 ``{%print(7*7)%}`` 仍可求值 —— 这是本关的教学点。
#:
#: ⚠️ 不要再往上加规则。Jinja2 里「裸标识符当字符串」只对**函数调用的位置参数**
#:    生效（``foo(bar)`` → ``foo('bar')`` 成立，``foo[bar]`` / ``foo|attr(bar)``
#:    不成立）。一旦把引号、方括号、点号同时堵死，这一关就真的无解了。
_PROFILE_BAD = re.compile(r"[\"'\[\]]|\{\{|\}\}")


# ---------------------------------------------------------------------------
# 会话（JWT 放在 cookie 里，保持「服务无状态」的观感）
# ---------------------------------------------------------------------------
def _issue_cookie(resp, username: str, role: str = "user"):
    token = jwt.encode(
        {"u": username, "role": role, "iat": int(time.time())}, app.config["SECRET_KEY"]
    )
    if isinstance(token, bytes):  # PyJWT 1.x
        token = token.decode()
    resp.set_cookie("session", token, httponly=True, samesite="Lax")


def _current_user() -> str | None:
    raw = request.cookies.get("session")
    if not raw:
        return None
    try:
        data = jwt.decode(raw, app.config["SECRET_KEY"], algorithms=["HS256"])
    except Exception:
        return None
    return data.get("u")


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
_CSS = """
:root{--accent:#00e5ff;--bg:#05070d;--panel:#0b1020;--line:#1d2740;--fg:#dbe7ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:15px/1.65 system-ui,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:840px;margin:48px auto;padding:0 22px}
h1{border-bottom:2px solid var(--accent);padding-bottom:8px;margin-bottom:6px;
   font-size:24px;letter-spacing:.4px}
h1 span{color:var(--accent)}
.box{border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0;background:var(--panel)}
code{background:rgba(255,255,255,.08);padding:1px 5px;border-radius:4px;
     font:13px ui-monospace,Consolas,monospace}
input{padding:9px;margin:5px 0;width:100%;box-sizing:border-box;background:#05080f;
      color:var(--fg);border:1px solid var(--line);border-radius:8px}
button{padding:9px 18px;margin-top:8px;cursor:pointer;background:var(--accent);
       color:#03121a;border:0;border-radius:8px;font-weight:700}
a{color:var(--accent)}
.err{color:#ff8fa3}
.ok{color:#39ff88}
.muted{opacity:.7;font-size:13px}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        f"<div class='wrap'><h1>abking's <span>notes</span></h1>{body}"
        "<p class='muted'>统一控制台：<a href='/console/'>/console/</a> · "
        "健康检查：<a href='/healthz'>/healthz</a></p>"
        "</div></body></html>"
    )


def _home(err: str = "") -> str:
    user = _current_user()
    errbox = f"<p class='err'>{err}</p>" if err else ""
    if user:
        return _page(
            "home",
            f"<div class='box'><b>已登录：</b><code>{user}</code>"
            f"<p><a href='/profile'>个人中心</a> · <a href='/admin'>审计记录</a> · "
            f"<a href='/logout'>退出</a></p>{errbox}</div>",
        )
    return _page(
        "home",
        "<div class='box'>"
        "<p>一个很小的笔记服务。注册一个名字，它就记住你。</p>"
        f"{errbox}"
        "<form method='post' action='/register'>"
        "<label>username</label>"
        "<input name='username' placeholder='abking' autocomplete='off'>"
        "<button>注册</button></form>"
        "<form method='post' action='/login'>"
        "<label>已注册？直接登录</label>"
        "<input name='username' placeholder='abking' autocomplete='off'>"
        "<button>登录</button></form>"
        "</div>"
        "<div class='box'><b>目标</b>"
        "<ul><li>flag 在容器的 <code>/flag</code>。</li>"
        "<li>容器<b>已切断出网</b>：反弹 shell、DNSLog、外连下载都不可用。</li>"
        "<li>请通过已有的入站 HTTP 通道把能力留在内存里。</li></ul></div>",
    )


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return _home()


@app.post("/register")
def register():
    username = request.form.get("username", "")
    if not username:
        return _home("username 不能为空")
    if len(username) > USERNAME_MAX:
        return _home(f"username 过长（<= {USERNAME_MAX}）")
    if _PROFILE_BAD.search(username):
        return _home("username 含非法字符")
    USERS.setdefault(username, {"password": uuid.uuid4().hex, "role": "user"})
    resp = redirect(url_for("profile"))
    _issue_cookie(resp, username)
    return resp


@app.post("/login")
def login():
    username = request.form.get("username", "")
    if username not in USERS:
        return _home("没有这个用户")
    role = "admin" if username == "admin" else "user"
    resp = redirect(url_for("profile"))
    _issue_cookie(resp, username, role)
    return resp


@app.get("/logout")
def logout():
    resp = redirect(url_for("index"))
    resp.set_cookie("session", "", expires=0)
    return resp


@app.get("/profile")
def profile():
    """漏洞点 1：username 被**未转义**拼进模板，但有过滤。

    这一关的作用是让选手确认 SSTI 存在。``{{7*7}}`` 会被过滤拦掉，
    但 ``{%print(7*7)%}`` 能过 —— 由此知道 ``{% %}`` 这一面是开放的。
    """
    user = _current_user()
    if not user:
        return redirect(url_for("index"))
    tpl = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<title>profile</title><style>" + _CSS + "</style></head><body>"
        "<div class='wrap'><h1>Welcome, " + user + "</h1>"
        "<div class='box'><p>你的个人中心由注册时保存的 username 渲染而来。</p>"
        "<p><a href='/'>首页</a> · <a href='/admin'>审计记录</a> · "
        "<a href='/logout'>退出</a></p></div></div></body></html>"
    )
    return render_template_string(tpl)


@app.get("/admin")
def admin():
    """漏洞点 2：Host 头被**无过滤**拼进模板，但结果**不回显**。

    审计记录页会把来源 Host 渲染进一张内部审计模板；渲染结果只写进
    进程内存的审计日志（连长度都不对外暴露），HTTP 响应永远是同一张静态页。
    于是：payload 从这里投递（Host 头够长、无过滤），
    但你必须自己想办法把结果带出来 —— 这正是「无回显 + 不出网」的起点。

    实战提示：Host 头里**不能有空格**，payload 内部的空白请用 TAB
    （Python 与 shell 都把 TAB 当空白）。
    """
    host = request.headers.get("Host") or request.environ.get("HTTP_HOST") or ""
    audit_template = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>source record</title></head><body>"
        "<h3>source record</h3><p>origin: " + host + "</p></body></html>"
    )
    try:
        render_template_string(audit_template)
    except Exception:  # noqa: BLE001 —— 审计失败不应影响响应
        pass
    # ⚠️ 只记录时间戳，连「渲染是否成功」都不记录。
    # 一旦把 ok/长度 暴露到页面上，就等于给了攻击者一个布尔盲注信道，
    # 本靶场「必须做内存马」的设计前提也就不成立了。
    AUDIT_LOG.append({"ts": time.time()})
    return _page(
        "source record",
        "<div class='box'><b>审计记录已保存</b>"
        "<p>来源已写入审计日志。本页不展示渲染结果，也不反馈渲染成败。</p>"
        "<p class='muted'>无回显意味着：你只能通过**副作用**判断 payload 是否执行——"
        "这正是不出网场景下内存马存在的理由。</p>"
        f"<pre class='muted'>{_render_audit_meta()}</pre></div>",
    )


def _render_audit_meta() -> str:
    return "\n".join(
        f"{time.strftime('%H:%M:%S', time.localtime(e['ts']))}  recorded"
        for e in AUDIT_LOG[-5:]
    )


@app.route("/report", methods=["GET", "POST"])
def report():
    """交给 admin bot 访问（只允许本机，避免变成对外 SSRF）。"""
    url = request.form.get("url") or request.args.get("url")
    if not url:
        return _page(
            "report",
            "<div class='box'><p>提交一个本机 URL，admin bot 会去访问它。</p>"
            "<form method='post' action='/report'>"
            "<input name='url' value='http://127.0.0.1:5000/admin'>"
            "<button>提交</button></form></div>",
        )
    host = urlparse(url).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        return _page("report", "<div class='box'><p class='err'>admin 只访问本机地址。</p></div>")
    threading.Thread(target=_visit_as_admin, args=(url,), daemon=True).start()
    return _page("report", f"<div class='box'><p>admin 将访问：<code>{url}</code></p></div>")


def _visit_as_admin(url: str) -> None:
    try:
        requests.get(url, timeout=5, headers={"X-Bot": "admin"})
    except Exception:  # noqa: BLE001
        pass


@app.get("/echo/<path:path>")
def echo(path: str):
    """命令输出回显目录。

    这是一个**有意的侧信道**：不出网时，「把结果写到 Web 可访问目录再取回」
    是最朴素也最有效的带外方式。理解它之后，内存马的价值才更清楚：
    写文件是「一次性、有痕迹」的，内存马是「可反复调用、不留文件」的。
    """
    return send_from_directory(ECHO_DIR, path)


# ---------------------------------------------------------------------------
# 关卡：把攻击链的四个台阶做成可渲染的 walkthrough
# ---------------------------------------------------------------------------
@make
def STEP0() -> Level:
    return Level(
        level_id="0",
        engine="jinja",
        title="步骤 0 · 本地调试台（有回显）",
        summary="先把 payload 调通，再走真实投递",
        description=(
            "控制台里的渲染接口使用**与 `/admin` 完全相同的无过滤渲染上下文**，"
            "但会把结果回显给你。作用是把「构造 payload」和「盲投递」两件事分开："
            "在这里把 payload 调到能用，再去 Host 头里盲投。"
            "可用的上下文：`config` / `request` / `session` / `url_for` / "
            "`get_flashed_messages` / `lipsum` / `cycler` / `joiner` / `namespace`。"
        ),
        hint="先试 `{{7*7}}`，再试 `{{ cycler.__init__.__globals__.os.popen('id').read() }}`。",
    )


@make
def STEP1() -> Level:
    return Level(
        level_id="1",
        engine="jinja",
        title="步骤 1 · /profile 用户名注入（有过滤）",
        summary="过滤 {{ }} 引号 方括号 · 但 {% %} 开放",
        description=(
            "`/profile` 把 username 未转义拼进模板，过滤 `{{` `}}` `'` `\"` `[` `]`。"
            "注意被拦的是**模板定界符**而不是表达式本身：`{%print(7*7)%}` 可以求值并回显。"
            "本关故意**不**堵引号以外的所有字符——一旦把引号、方括号、点号同时堵死，"
            "Jinja2 下这一关就无法完成（详见 app.py 里 `_PROFILE_BAD` 的注释）。"
        ),
        waf=WafSpec(
            regexes=(r"[\"'\[\]]", r"\{\{", r"\}\}"),
            ignore_case=False,
            note="命中 `{{`、`}}`、`'`、`\"`、`[`、`]` 即返回 WAF。",
        ),
        hint="`{%print(...)%}` 替代 `{{...}}`；用 `request.args` 之类通道带入字符串。",
    )


@make
def STEP2() -> Level:
    return Level(
        level_id="2",
        engine="jinja",
        title="步骤 2 · /admin Host 头注入（无过滤 · 无回显）",
        summary="真实投递点：结果进内存审计日志，不回显",
        description=(
            "`/admin` 把 Host 头无过滤拼进审计模板，但渲染结果**不返回给客户端**——"
            "只记录「是否渲染成功」和时间戳。所以这里是真正的**无回显**注入点。"
            "投递要点：Host 头里不能有空格，payload 内部的空白请用 TAB。"
        ),
        echo_mode="none",
        hint="无回显时，唯一的信息是副作用：写文件、注册路由、改变进程状态。",
    )


@make
def STEP3() -> Level:
    return Level(
        level_id="3",
        engine="jinja",
        title="步骤 3 · 写文件回显（HTTP 侧信道）",
        summary="把命令输出写进 /app/echo/，再从 /echo/ 取回",
        description=(
            "容器已切断出网，所以不能反弹、不能 DNSLog。最朴素的办法是"
            "把命令输出写进 Web 可访问的 `/app/echo/`，再用 GET `/echo/<名字>` 取回。"
            "这一关先掌握它，作为后面内存马的对照：写文件是一次性的、有痕迹的。"
        ),
        echo_mode="none",
        no_egress=True,
        hint="`__import__('os').popen('cat /flag > /app/echo/f.txt')`，然后取 `/echo/f.txt`。",
    )


@make
def STEP4() -> Level:
    return Level(
        level_id="4",
        engine="jinja",
        title="步骤 4 · 内存马（不出网最终目标）",
        summary="绕过 flask setupmethod 保护，把 webshell 挂进运行中的进程",
        description=(
            "最终目标：不落任何文件，把一条新路由（或一个 `before_request` 钩子）"
            "注入正在运行的 Flask 进程，得到可反复调用的内存 webshell。"
            "关键坑：Flask 的 `add_url_rule` / `before_request` 带 `setupmethod` 保护，"
            "应用处理过第一个请求后会直接抛 `AssertionError`——"
            "必须绕过公开 API，直接改 `app.url_map` + `app.view_functions`，"
            "或直接往 `app.before_request_funcs[None]` 追加函数。"
        ),
        echo_mode="none",
        no_egress=True,
        hint=(
            "`cycler.__init__.__globals__.__builtins__` 能拿到 `eval` 与 `__import__`。"
            "用 `eval(\"lambda: ...\")` 造出视图函数，再直接改底层数据结构。"
        ),
    )


LEVELS = [STEP0, STEP1, STEP2, STEP3, STEP4]

META = LabMeta(
    id="flask-memshell",
    title="不出网 SSTI · Flask 内存马",
    subtitle="无回显 + 无出网 · 四台阶攻击链",
    engine="jinja",
    engine_title="Jinja2",
    theme=THEMES["crimson"],
    description=(
        "模拟一个小型笔记服务：`/profile` 的用户名被未转义拼进模板（有过滤），"
        "`/admin` 的 Host 头被无过滤拼进模板（但结果不回显）。"
        "容器**已切断出网**，所以反弹 shell / DNSLog 全部不可用；"
        "你要先用写文件侧信道建立回显，最终把 webshell 注入运行中的 Flask 进程，"
        "得到可反复调用的内存马。"
    ),
    no_egress=True,
    hint=(
        "四步走：① `/profile` 用 `{%print(7*7)%}` 确认 SSTI；"
        "② Host 头盲投（空白用 TAB）；③ 写 `/app/echo/` 再取回；"
        "④ 绕过 `setupmethod` 做内存马。"
    ),
    doc_url="/docs/README.md",
)

# ---------------------------------------------------------------------------
# 挂载公共 API 与统一控制台
# ---------------------------------------------------------------------------
# 场景型靶场**不**用 create_lab_app()：那个工厂会抢占 `/` 与 `/<path:path>`，
# 与本文件的业务路由（index/profile/admin/...）重复注册端点名而报错。
# 正确做法是自己持有 Flask 应用，只挂接口与控制台：
#     /          -> 业务页面（本文件上面定义）
#     /console/  -> 统一赛博朋克控制台（复用 frontend 构建产物）
#     /api/*     -> 契约接口
register_lab_api(app, META, LEVELS, engine_titles=engine_titles(), docs_folder="docs")
mount_console(app, "public", "/console")

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "5000")), debug=False)
