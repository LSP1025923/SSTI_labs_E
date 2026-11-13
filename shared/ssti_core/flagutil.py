"""Flag 读取与写入。

优先级与主流 CTF 平台对齐（先命中先用）：

1. ``GZCTF_FLAG``  —— GZCTF 动态 flag（每队/每实例不同）
2. ``DASFLAG``     —— 部分平台使用的变量名
3. ``FLAG``        —— 通用兜底
4. ``STATIC_FLAG`` —— 本地/演示用的固定 flag

约定：容器 entrypoint 启动时把解析结果写入 ``/flag``（不进镜像层），
应用内必须通过 SSTI 实际读文件才能拿到，因此不要在 API 里回显 flag。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_STATIC_FLAG = "flag{ssti_lab_change_me}"

_ENV_ORDER = ("GZCTF_FLAG", "DASFLAG", "FLAG", "STATIC_FLAG")


def resolve_flag() -> str:
    """按优先级从环境变量解析 flag。"""
    for key in _ENV_ORDER:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return DEFAULT_STATIC_FLAG


def write_flag_file(path: str | None = None) -> str:
    """把当前 flag 写到文件（默认 ``Config.FLAG_PATH``），返回写入内容。"""
    target = Path(path or os.environ.get("FLAG_PATH", "/flag"))
    flag = resolve_flag()
    target.parent.mkdir(parents=True, exist_ok=True)
    # 先写临时文件再 rename，避免容器重启瞬间被读到半截
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(flag, encoding="utf-8")
    tmp.replace(target)
    try:
        target.chmod(0o644)
    except OSError:
        pass
    return flag


def read_flag_file(path: str | None = None) -> str:
    """读取 flag 文件；失败返回空串（调用方无需处理异常）。"""
    try:
        return Path(path or os.environ.get("FLAG_PATH", "/flag")).read_text("utf-8").strip()
    except OSError:
        return ""


def flag_found_in(text: str, path: str | None = None) -> bool:
    """判断渲染输出里是否出现了 flag（用于前端「拿到 flag」庆祝提示）。"""
    flag = read_flag_file(path)
    if not flag:
        return False
    return flag in (text or "")


def mask(flag: str) -> str:
    """日志用：只保留前缀，避免 flag 进日志。"""
    if not flag:
        return "<empty>"
    if "{" in flag:
        head, _, tail = flag.partition("{")
        return f"{head}{{***}}"
    return flag[:6] + "***"
