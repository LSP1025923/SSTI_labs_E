"""ssti_core —— 多靶场 SSTI 靶场公共库。

被每个靶场容器以 ``COPY shared/ssti_core`` 的方式打包进镜像。
不要在 ``import`` 时产生副作用（不要读文件、不要建连接）。
"""

from ssti_core.config import Config
from ssti_core.flagutil import resolve_flag, write_flag_file, flag_found_in
from ssti_core.labmeta import LabMeta, Theme
from ssti_core.render import RenderResult, plain_text_output
from ssti_core.waf import WafSpec
from ssti_core.level import Level
from ssti_core.labapp import create_lab_app, lab_info_payload

__all__ = [
    "Config",
    "resolve_flag",
    "write_flag_file",
    "flag_found_in",
    "LabMeta",
    "Theme",
    "RenderResult",
    "plain_text_output",
    "WafSpec",
    "Level",
    "create_lab_app",
    "lab_info_payload",
]
