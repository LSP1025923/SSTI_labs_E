"""运行时配置：全部来自环境变量，便于同一镜像在本地/CTF 平台间迁移。"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Config:
    """进程级配置。属性在导入时求值；测试中可直接改类属性。"""

    #: 靶场 id（通常等于 labs/ 下的目录名去掉序号前缀）
    LAB_ID: str = os.environ.get("LAB_ID", "ssti-lab")

    #: flag 文件路径（容器内）
    FLAG_PATH: str = os.environ.get("FLAG_PATH", "/flag")

    #: 渲染输出最大字符数，防止 `__subclasses__()` 之类撑爆响应
    MAX_OUTPUT_CHARS: int = _env_int("SSTI_MAX_OUTPUT_CHARS", 262144)

    #: /api/admin/reset 所需令牌；为空则拒绝重置
    RESET_TOKEN: str = os.environ.get("RESET_TOKEN", "")

    #: 是否已在网络层切断出网（仅用于前端提示，真正的切断在 entrypoint 里做）
    NO_EGRESS: bool = _env_bool("SSTI_NO_EGRESS", False)

    #: 监听地址/端口
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = _env_int("PORT", 5000)

    #: 允许直接写文件系统的目录（无回显靶场的回显目录）
    ECHO_DIR: str = os.environ.get("SSTI_ECHO_DIR", "/app/public/echo")
