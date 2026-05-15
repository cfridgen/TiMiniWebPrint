#!/usr/bin/env python3
from __future__ import annotations

import os

import uvicorn


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _uvicorn_kwargs() -> dict[str, object]:
    reload_enabled = _env_flag("TIMINIPRINT_RELOAD", True)
    log_to_stdout = _env_flag("TIMINIPRINT_LOG_TO_STDOUT", True)
    kwargs: dict[str, object] = {
        "host": os.environ.get("APP_ADDR", "0.0.0.0"),
        "port": int(os.environ.get("APP_PORT", "8901")),
        "reload": reload_enabled,
        "log_level": os.environ.get("TIMINIPRINT_LOG_LEVEL", "debug" if reload_enabled else "info"),
        "access_log": _env_flag("TIMINIPRINT_ACCESS_LOG", False),
    }
    if not log_to_stdout:
        kwargs["log_config"] = None
    return kwargs


if __name__ == "__main__":
    uvicorn.run("timiniprint.app.web:app", **_uvicorn_kwargs())
