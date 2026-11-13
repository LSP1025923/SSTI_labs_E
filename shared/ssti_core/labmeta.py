"""靶场元信息：前端靠它初始化整个控制台。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ssti_core.config import Config


@dataclass
class Theme:
    """前端主题。每个靶场一个色调，玩家在多个容器间切换时不会串台。"""

    name: str = "cyber"
    accent: str = "#00e5ff"
    accent2: str = "#ff2bd6"
    glow: str = "rgba(0,229,255,0.55)"

    def to_json(self) -> dict[str, str]:
        return {
            "name": self.name,
            "accent": self.accent,
            "accent2": self.accent2,
            "glow": self.glow,
        }


#: 预置配色，供各靶场引用
THEMES: dict[str, Theme] = {
    "cyber": Theme("cyber", "#00e5ff", "#ff2bd6", "rgba(0,229,255,0.55)"),
    "amber": Theme("amber", "#ffb020", "#ff5c39", "rgba(255,176,32,0.55)"),
    "matrix": Theme("matrix", "#39ff88", "#00c2a8", "rgba(57,255,136,0.55)"),
    "violet": Theme("violet", "#a06bff", "#ff6bd6", "rgba(160,107,255,0.55)"),
    "crimson": Theme("crimson", "#ff4d6d", "#ff9e00", "rgba(255,77,109,0.55)"),
    "ice": Theme("ice", "#7fe9ff", "#5b8cff", "rgba(127,233,255,0.55)"),
}


@dataclass
class LabMeta:
    """一个靶场的描述。``levels`` 由调用方在 ``to_json`` 时传入。"""

    id: str
    title: str
    subtitle: str = ""
    engine: str = "jinja"
    engine_title: str = ""
    description: str = ""
    no_egress: bool = False
    no_egress_note: str = ""
    flag_path: str = ""
    flag_format: str = "flag{...}"
    theme: Theme = field(default_factory=lambda: THEMES["cyber"])
    hint: str = ""
    doc_url: str = ""

    def __post_init__(self) -> None:
        if not self.flag_path:
            self.flag_path = Config.FLAG_PATH
        if not self.no_egress:
            # 以环境变量为准：compose 里切开出网后，镜像内的提示自动生效
            self.no_egress = Config.NO_EGRESS
        if self.no_egress and not self.no_egress_note:
            self.no_egress_note = (
                "容器已切断出网：反弹 shell、DNSLog、外连下载全部不可用，"
                "必须走内存马或写文件回显。"
            )
        if not self.engine_title:
            self.engine_title = self.engine.title()

    def to_json(
        self,
        levels: list[Any],
        engines: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        level_json = [lv.to_json() for lv in levels]
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "engine": self.engine,
            "engine_title": self.engine_title,
            "description": self.description,
            "no_egress": self.no_egress,
            "no_egress_note": self.no_egress_note,
            "flag_path": self.flag_path,
            "flag_format": self.flag_format,
            "theme": self.theme.to_json(),
            "hint": self.hint,
            "doc_url": self.doc_url,
            "engines": engines or [{"id": self.engine, "title": self.engine_title}],
            "levels": level_json,
            # 兼容契约里 `levels` 之外的便捷字段
            "level_count": len(level_json),
        }
