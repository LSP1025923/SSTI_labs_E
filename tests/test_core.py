#!/usr/bin/env python3
"""ssti_core 单元自检 —— 不依赖 Docker，直接在 Python 里跑。

用法（仓库根目录）::

    PYTHONPATH=shared python tests/test_core.py

覆盖：关卡注册完整性、三引擎基础渲染、WAF 命中/绕过语义、盲关语义、
flag 读写与「输出中出现 flag」判定。
"""

from __future__ import annotations

import os
import sys

# --- Windows 控制台默认编码是 GBK，而本脚本会打印 ✅ / ⚠️ 这类字符 -----------
# 不处理的话，即使所有断言都通过，最后一行 print 也会抛 UnicodeEncodeError，
# 脚本以非 0 退出（在 CI 上看起来就是「失败」）。这里强制走 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # 老解释器 / 已被重定向的流
        pass

import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))

# flag 相关测试不碰真实 /flag
_TMP = Path(tempfile.mkdtemp(prefix="ssti-core-test-"))
os.environ.setdefault("FLAG_PATH", str(_TMP / "flag"))
os.environ["STATIC_FLAG"] = "flag{core_self_test}"

from flask import Flask  # noqa: E402

from ssti_core import flagutil  # noqa: E402
from ssti_core.level import find_level  # noqa: E402
from ssti_core.levels import engine_titles, levels_for, registry  # noqa: E402
from ssti_core.labmeta import LabMeta  # noqa: E402
from ssti_core.labapp import lab_info_payload  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(name)


def main() -> int:
    app = Flask(__name__)
    flagutil.write_flag_file()

    print("[1] 关卡注册")
    for engine in ("jinja", "mako", "tornado"):
        lv = levels_for(engine)
        check(f"{engine} 有 13 关", len(lv) == 13, f"实际 {len(lv)}")
        ids = [x.level_id for x in lv]
        check(f"{engine} 关卡 id 唯一且为 0..12", ids == [str(i) for i in range(13)], str(ids))
        check(f"{engine} 每关都有标题/描述", all(x.title and x.description for x in lv))
        check(f"{engine} 第 3 关是盲关", lv[2].blind is True)
    check("engine_titles 覆盖基础三引擎", {"jinja", "mako", "tornado"} <= set(engine_titles()))

    print("[1b] 沙箱关卡库（05-jinja-sandbox）")
    sbx = levels_for("jinja-sandbox")
    check("jinja-sandbox 有 4 关", len(sbx) == 4, f"实际 {len(sbx)}")
    check("jinja-sandbox 关卡 id 为 0..3", [x.level_id for x in sbx] == [str(i) for i in range(4)])
    check(
        "沙箱关卡都用 jinja_sandbox 渲染器",
        all(x.renderer_key == "jinja_sandbox" for x in sbx),
        str([x.renderer_key for x in sbx]),
    )
    check("沙箱关卡的展示分组仍是 jinja", all(x.engine == "jinja" for x in sbx))
    check(
        "沙箱关卡声明了沙箱类型（L2 为 immutable）",
        sbx[1].options.get("sandbox") == "immutable"
        and sbx[0].options.get("sandbox") in (None, "default"),
    )
    check(
        "L3 是关键字子串黑名单，L4 是字符黑名单",
        sbx[2].waf.kind == "substring" and sbx[3].waf.kind == "chars",
        f"{sbx[2].waf.kind} / {sbx[3].waf.kind}",
    )
    check("沙箱关卡都有标题/描述/hint", all(x.title and x.description and x.hint for x in sbx))
    check("注册表里能查到 jinja-sandbox", registry().get("jinja-sandbox") == 4, str(registry()))

    with app.test_request_context("/"):
        print("[2] 基础渲染（练习模式）")
        cases = [
            ("jinja", "{{7*7}}", "49"),
            ("jinja", "{{ config }}", None),
            ("mako", "${7*7}", "49"),
            ("tornado", "{{ 7*7 }}", "49"),
        ]
        for engine, tpl, expect in cases:
            level = levels_for(engine)[0]
            res = level.render(tpl)
            if expect is None:
                check(f"{engine} `{tpl}` 渲染无异常", res.error is None, str(res.error))
            else:
                check(f"{engine} `{tpl}` => {expect}", res.practice_output.strip() == expect,
                      repr(res.practice_output))

        print("[3] WAF 语义")
        j = levels_for("jinja")
        l2 = j[1]  # 拦截 {{
        r = l2.render("{{7*7}}")
        check("L2 命中 {{ 返回 WAF", r.practice_output == "WAF" and r.waf_blocked)
        r = l2.render("{% print(7*7) %}")
        check("L2 用 {% print %} 绕过成功", r.practice_output.strip() == "49", repr(r.practice_output))

        l4 = j[3]  # 禁方括号
        check("L4 命中 [ 返回 WAF", l4.render("{{ [1,2] }}").practice_output == "WAF")
        check("L4 不用方括号则通过", l4.render("{{ 7*7 }}").practice_output.strip() == "49")

        l10 = j[9]  # 前缀置空
        r10 = l10.render("{{7*7}}")
        check("L10 前缀被拼接进 template_after_waf",
              r10.template_after_waf.startswith("{% set config=None%}"), r10.template_after_waf)
        check("L10 config 被置空", "None" in l10.render("{{ config }}").practice_output)

        print("[4] 盲关语义")
        b = j[2]
        rb_ok = b.render("ok")
        check("盲关成功 => correct", rb_ok.practice_output == "correct", repr(rb_ok.practice_output))
        check("盲关保留真实输出在 raw_output", rb_ok.raw_output.strip() == "ok")
        rb_bad = b.render("{{ 1/0 }}")
        check("盲关异常 => wrong", rb_bad.practice_output == "wrong")
        check("盲关记录异常类型", rb_bad.exception_type is not None)

        print("[5] 未过滤关卡不应报异常")
        for engine in ("jinja", "mako", "tornado"):
            lv = levels_for(engine)[0]
            res = lv.render("hello")
            check(f"{engine} L1 `hello` 无异常", res.error is None, str(res.error))

        print("[6] flag 判定")
        flag = flagutil.read_flag_file()
        check("flag 文件已写入", flag == "flag{core_self_test}", repr(flag))
        check("输出含 flag 时可检出", flagutil.flag_found_in(f"x{flag}y"))
        check("输出不含 flag 时不可检出", not flagutil.flag_found_in("nothing"))

        print("[7] lab-info 契约")
        meta = LabMeta(id="jinja-chain", title="t", engine="jinja", engine_title="Jinja2")
        payload = lab_info_payload(meta, levels_for("jinja"))
        for key in ("id", "title", "engine", "no_egress", "flag_path", "theme", "levels", "engines"):
            check(f"lab-info 含 {key}", key in payload)
        check("lab-info.theme 含 accent", "accent" in payload["theme"])
        first = payload["levels"][0]
        for key in ("id", "title", "summary", "description", "blind", "no_egress", "waf", "hint"):
            check(f"level 含 {key}", key in first)
        check("L1 的 waf 为 null", first["waf"] is None)
        check("L2 的 waf 为 substring", payload["levels"][1]["waf"]["kind"] == "substring")

        print("[8] find_level 回落")
        check("未知 id 回落到第一关", find_level(levels_for("jinja"), "nope").level_id == "0")
        check("空 id 回落到第一关", find_level(levels_for("jinja"), None).level_id == "0")

    print()
    print(f"共 {CHECKS} 项，失败 {len(FAILURES)} 项")
    if FAILURES:
        print("失败项：" + ", ".join(FAILURES))
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
