"""ssti_core —— 多靶场 SSTI 靶场公共库。

被每个靶场容器以 ``COPY shared/ssti_core`` 的方式打包进镜像。
不要在 ``import`` 时产生副作用（不要读文件、不要建连接）。

**Flask 是可选依赖**：``ssti_core.waf`` / ``level`` / ``render`` / ``flagutil``
只依赖标准库，可以脱离 Flask 单独使用（单元测试、离线生成 payload、静态分析都用得上）。
需要 Web 应用工厂时再访问 ``create_lab_app`` / ``register_lab_api``，
它们通过模块级 ``__getattr__`` 惰性导入 ``ssti_core.labapp``（那里才 import flask）。
"""

from ssti_core.config import Config
from ssti_core.flagutil import flag_found_in, resolve_flag, write_flag_file
from ssti_core.labmeta import LabMeta, Theme
from ssti_core.level import Level, find_level, group_engines, make
from ssti_core.render import RenderResult, plain_text_output, truncate
from ssti_core.waf import NO_WAF, WafSpec

__all__ = [
    # 配置与 flag
    "Config",
    "resolve_flag",
    "write_flag_file",
    "flag_found_in",
    # 元信息
    "LabMeta",
    "Theme",
    # 关卡模型
    "Level",
    "find_level",
    "group_engines",
    "make",
    # 渲染结果
    "RenderResult",
    "plain_text_output",
    "truncate",
    # WAF
    "WafSpec",
    "NO_WAF",
    # Flask 应用工厂（惰性）
    "create_lab_app",
    "register_lab_api",
    "mount_console",
    "lab_info_payload",
]

#: 需要 Flask 的符号 -> 它们在 ssti_core.labapp 里
_LAZY_FROM_LABAPP = frozenset(
    {"create_lab_app", "register_lab_api", "mount_console", "lab_info_payload"}
)


def __getattr__(name: str):
    """PEP 562：惰性导入 Flask 相关符号，避免 ``import ssti_core`` 就要求装 Flask。"""
    if name in _LAZY_FROM_LABAPP:
        from ssti_core import labapp

        return getattr(labapp, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
