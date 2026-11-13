#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06-blind-ssti —— 无回显 SSTI：盲注与侧信道（4 关）。

攻击链与教学目标（四关都在这个文件里定义，因为 L3/L4 需要额外的 `/echo/` 路由）：

  1. ``echo_mode="bool"``   —— flag 作为模板变量 `secret` 注入上下文（**教学装置**）。
     只回显 `correct` / `wrong`，练习「把拿到数据变成控制成功与否」。
  2. ``echo_mode="none"``   —— 连成败都不告诉你，响应体恒定。唯一信道是**耗时**。
  3. ``echo_mode="file"``   —— 上下文里**没有** `secret`，flag 只在 `/flag`。
     把命令输出写进 HTTP 可访问的 ``ECHO_DIR`` 再从 `/echo/<path>` 取回。
  4. ``no_egress=True``     —— L3 的机制 + 「不出网」。本关是**通往内存马的桥梁**：
     一旦回显目录也不可写，能用的只剩「把能力留在入站 HTTP 通道上」，
     也就是 `07-flask-memshell` 里的内存马。

``ECHO_DIR`` 的写权限由本文件负责：entrypoint 只写 /flag，不会建回显目录，
所以导入时 `os.makedirs` + `os.chmod(0o777)`，否则容器里的应用用户写不进去。
"""

from __future__ import annotations

import os
import sys
import tempfile

from flask import send_from_directory

import ssti_core.labapp as labapp
from ssti_core import LabMeta, create_lab_app, flagutil
from ssti_core.labmeta import THEMES
from ssti_core.level import Level, make

# ---------------------------------------------------------------------------
# flag 与回显目录
# ---------------------------------------------------------------------------
#: entrypoint 已经把 flag 写进 /flag；读不到（本地直接 python app.py）就退回环境变量。
FLAG = flagutil.read_flag_file() or flagutil.resolve_flag()


def _prepare_echo_dir(path: str) -> str:
    """创建回显目录并放开写权限。

    entrypoint 只写 /flag，**不会**建这个目录；容器里应用以 root 启动，
    所以这里 makedirs + chmod 0777 之后进程一定能写进去。
    非容器环境（本地跑、CI 里只做 import 自检）可能没有 /app 的写权限，
    此时退回临时目录，保证「import 不该炸」。
    """
    try:
        os.makedirs(path, exist_ok=True)
        os.chmod(path, 0o777)
        return path
    except OSError as exc:  # pragma: no cover - 只在非容器/无权限环境命中
        fallback = os.path.join(tempfile.gettempdir(), "ssti-blind-echo")
        os.makedirs(fallback, exist_ok=True)
        print(f"⚠️ 无法准备回显目录 {path}（{exc}），改用 {fallback}", file=sys.stderr)
        return fallback


#: 命令输出回显目录（HTTP 可访问）。
ECHO_DIR = _prepare_echo_dir(os.environ.get("SSTI_ECHO_DIR", "/app/echo"))


# ---------------------------------------------------------------------------
# 关卡（lab-local：L3/L4 依赖本文件注册的 /echo/ 路由）
# ---------------------------------------------------------------------------
@make
def L01() -> Level:
    return Level(
        level_id="0",
        engine="jinja",
        title="L1 - 布尔盲注",
        summary="只回显 correct / wrong · flag 在模板变量 secret 里",
        description=(
            "渲染结果被替换成 `correct`（无异常）/ `wrong`（抛异常），你看不到任何求值结果。"
            "**教学装置**：flag 被直接注入模板上下文，变量名就叫 `secret`——"
            "真实盲注场景里你并不知道数据在哪，得先用 SSTI 探测出它的位置（读哪个文件、"
            "取哪个对象），再把「我拿到它了吗」转换成「渲染成功/失败」这个布尔信号。"
            "本关把第一步替你做了，只留第二步：**逐字符爆破**。\n"
            "手法：把猜测写进 `{% if %}`，猜中时主动制造一个异常（例如 `{{ 1/0 }}`），"
            "于是「`wrong`」= 猜中，「`correct`」= 猜错。"
        ),
        echo_mode="bool",
        options={"context": {"secret": FLAG}},
        hint=(
            "`{% if secret[0] == 'f' %}` 里塞一个必然抛异常的分支，猜中就变成 `wrong`。"
            "想快一点就别线性枚举：`secret[i] < 'm'` 这类比较可以二分，每字符约 7 次请求。"
        ),
    )


@make
def L02() -> Level:
    return Level(
        level_id="1",
        engine="jinja",
        title="L2 - 时间盲注",
        summary="echo_mode=none · 成功失败在响应体里完全一样，只剩耗时",
        description=(
            "上下文里同样有 `secret`，但这一关把回显彻底关掉：无论渲染成功还是抛异常，"
            "响应体永远是同一个常量 `received`（`echo_mode=\"none\"`）。"
            "唯一的信道是**服务端花了多久**。\n"
            "做法：条件成立时跑一段很慢的循环。\n"
            "**实测注意点**（别把噪声当成信号）：\n"
            "1. 先取基线：同一个 payload 去掉条件跑几次，记下中位数；\n"
            "2. 看**相对差**而不是绝对秒数——容器负载、冷启动、网络抖动都会影响绝对值；\n"
            "3. 循环体不能为空：空循环体的 `range(20000000)` 只要约 0.24 s，"
            "带 `{{ '' }}` 的 `range(50000000)` 约 1.44 s（README 有实测表）；\n"
            "4. 每个判定多打几次取中位数，再决定「慢」还是「快」。"
        ),
        echo_mode="none",
        echo_text="received",
        options={"context": {"secret": FLAG}},
        hint=(
            "`{% if <条件> %}{% for i in range(50000000) %}{{ '' }}{% endfor %}{% endif %}`："
            "条件为真时请求明显变慢（本镜像实测约 1.4 s，基线约 0.01 s）。"
            "记得先测基线、多测几次取中位数。"
        ),
    )


@make
def L03() -> Level:
    return Level(
        level_id="2",
        engine="jinja",
        title="L3 - 写文件回显",
        summary="无回显 · flag 只在 /flag · 把命令输出写进 /app/echo 再从 /echo/ 取回",
        description=(
            "本关的上下文里**没有** `secret`，flag 只以文件形式存在于 `/flag`；"
            "渲染结果同样不回显（`echo_mode=\"file\"`）。"
            "所以你需要一个**副作用信道**：容器把 `ECHO_DIR`（默认 `/app/echo`）"
            "以 `GET /echo/<path>` 暴露成 HTTP 目录，用 SSTI 执行命令并把输出重定向进去，"
            "再用 HTTP 取回来。\n"
            "本关用的是普通 Flask `render_template_string`（没有沙箱），"
            "`lipsum.__globals__` 与 `cycler.__init__.__globals__` 两条链都能直达 `os`。"
        ),
        echo_mode="file",
        hint=(
            "把命令输出重定向到 `/app/echo/<名字>`，再 `GET /echo/<名字>`；"
            "入口用 `lipsum.__globals__` 或 `cycler.__init__.__globals__` 拿到 `os`。"
        ),
    )


@make
def L04() -> Level:
    return Level(
        level_id="3",
        engine="jinja",
        title="L4 - 不出网 + 无回显：为什么答案是内存马",
        summary="no_egress=True · 反弹 shell / DNSLog 全部失效",
        description=(
            "L3 的机制 + `no_egress=True`：容器**已切断出网**（反弹 shell、DNSLog、"
            "外连下载全部不可用），响应体也不回显。\n"
            "**本关是通往内存马的桥梁**：如果连回显目录也不可写（把 `/app/echo` 挂成只读），"
            "那就既不能回显、又不能落文件、又不能外连——剩下的唯一答案是把能力留在"
            "**已经存在的入站 HTTP 通道**上：往运行中的 Flask 进程里注入一条路由，"
            "或一个 `before_request` 钩子（内存马）。注意 Flask 的 `setupmethod` 保护："
            "应用处理过第一个请求后，`add_url_rule` / `before_request` 会直接抛 "
            "`AssertionError`，必须绕过公开 API 改底层数据结构。\n"
            "本容器里回显目录是**可写**的（否则这一关在本靶场内无法完成），"
            "所以本关的完成方式与 L3 相同；真正的「只读目录 + 不出网」场景请去 "
            "`07-flask-memshell` 动手做内存马。"
        ),
        echo_mode="file",
        no_egress=True,
        hint=(
            "先用 L3 的做法确认文件回显仍然可用；然后把「如果目录只读」想一遍——"
            "能反复调用、不落文件的路只有内存马，见 07-flask-memshell。"
        ),
    )


LEVELS = [L01, L02, L03, L04]

META = LabMeta(
    id="blind-ssti",
    title="无回显 SSTI",
    subtitle="4 关：布尔盲注 / 时间盲注 / 写文件回显 / 不出网",
    engine="jinja",
    engine_title="Jinja2",
    theme=THEMES["matrix"],
    description=(
        "同一个 Jinja2 注入点，四种「看不见回显」的程度：只回显 correct/wrong、"
        "连成败都不回显（只能测时间）、完全没有回显（只能写文件再从 HTTP 取回）、"
        "以及再叠加不出网。L1/L2 的 flag 作为教学装置直接注入模板变量 `secret`，"
        "让你专注练「把数据变成布尔/时间信号」；L3/L4 的 flag 只在 `/flag`，"
        "必须真的写出副作用才能拿到。L4 是通向内存马（07-flask-memshell）的桥梁。"
    ),
    hint=(
        "先确认注入点在：`{{7*7}}` 能渲染，但练习模式只回显 correct/wrong 或常量。 "
        "盲关请开上帝模式看 `raw_output` 与异常类型，确认 payload 本身写对了再去做盲判。"
    ),
    # 本靶场自身没有切断出网（SSTI_NO_EGRESS=0）；只有 L4 关卡带 no_egress 标记，
    # 说明「这一关的题目语义是不出网」。真正的网络隔离在 07-flask-memshell。
    no_egress=False,
    doc_url="/docs/README.md",
)


def _extra_routes(flask_app) -> None:
    """文件回显信道：`GET /echo/<path>` 把 ECHO_DIR 暴露成可读目录。"""

    @flask_app.get("/echo/<path:path>")
    def echo(path: str):
        return send_from_directory(ECHO_DIR, path)


app = create_lab_app(
    META,
    LEVELS,
    engine_titles={"jinja": "Jinja2"},
    docs_folder="docs",
    extra_routes=_extra_routes,
)

if __name__ == "__main__":
    labapp.run(app)
