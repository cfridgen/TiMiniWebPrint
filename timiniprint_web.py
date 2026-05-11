#!/usr/bin/env python3
from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "timiniprint.app.web:app",
        host="0.0.0.0",
        port=int(os.environ.get("APP_PORT", "8901")),
        reload=True,
        log_level="debug",
        access_log=True,
    )
