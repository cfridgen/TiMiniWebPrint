#!/usr/bin/env python3
from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "timiniprint.app.web:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug",
        access_log=True,
    )
