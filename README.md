# 🖨️ TiMini Print — Enhanced Docker Edition

> **🔗 Community Fork of [Dejniel's TiMini-Print](https://github.com/Dejniel/TiMini-Print)**
> 
> This is a production-enhanced fork adding containerization, robust Bluetooth support, and release/development channel separation. **All original functionality is preserved** — this is an enhancement, not a reimplementation.

## ✨ What is TiMini Print?

A powerful alternative to proprietary apps for **Chinese Bluetooth thermal printers** that use proprietary protocols (not ESC/POS). Works as a replacement for "Tiny Print", "Fun Print", "Phomemo", "iBleem", and similar apps.

**Supports 200+ printer models** — from A200 to ZPA4Z1. [See full list](#supported-printer-models).

### 📋 Core Features

| Feature | Details |
|---------|---------|
| 🖼️ **Images** | PNG, JPG, GIF, BMP with automatic scaling |
| 📄 **PDFs** | Multi-page support with automatic optimization |
| 📝 **Text** | Monospace, bold, word-wrapped output |
| 🌐 **Web App** | Modern UI with live printer detection |
| ⚡ **CLI Mode** | "Fire and forget" automation |
| 🔌 **API** | Build custom integrations with the library |
| 🐧 **Cross-Platform** | Windows, Linux, macOS (no driver needed) |

**Original creator:** [Dejniel](https://github.com/Dejniel) | **[Original Repository](https://github.com/Dejniel/TiMini-Print)**

![TiMini Print LOGO EMX-040256 Printer Psi Patrol](EMX_040256.jpg)

---

## 🚀 Fork-Specific Enhancements

This fork adds production-grade improvements. **Original functionality is 100% intact** — these are additions:

### 1. **Release/Development Channel Architecture** 🔄

Separate deployment pipelines for stability and rapid iteration:

```
Master Branch       
     ↓
     ├─→ dev-latest tag (Port 8901) ← Development Channel
     │   [Latest code, frequent updates, experimental]
     │
     └─→ Git Tag (v1.0.0)
         ↓
         v1.0.0 (Port 8001) ← Release Channel  
         [Pinned image, stable, monitored]
```

- **Release (port 8001)**: Immutable images, comprehensive monitoring, slow steady cadence
- **Development (port 8901)**: Latest features, rapid updates, direct Portainer deployment

### 2. **Fixed Bluetooth on Linux Docker** ✅

Resolved critical containerization issues for Bluetooth scanning:
- ✅ DBus socket mounts (`/run/dbus`, `/var/run/dbus`)
- ✅ udev integration for device discovery (`/run/udev:ro`)
- ✅ Tested multi-device printer detection
- ✅ Host network mode for stable connectivity

### 3. **Consolidated Debug System** 🔧

All debug features managed by one entry point:
- Feature-flagged via `TIMINIPRINT_WEB_DEBUG` environment variable
- Debug UI hidden by default (safe, can't accidentally misconfigure)
- REST API endpoints with proper authorization checks
- Backend and frontend in sync

### 4. **Production-Ready Containerization** 🐳

Docker-first deployment architecture:
- Multi-stage builds for minimal image size
- Prometheus Node Exporter integration (monitoring-ready)
- Environment-driven config (no hardcoded ports/versions)
- Health checks and proper signal handling

### 5. **Clear, Repeatable Release Process** 📦

Professional release management:
- GitHub Actions with channel-aware tagging (`dev-latest`, `v1.0.0`)
- Semantic versioning throughout
- `RELEASE_CHECKLIST.md` with step-by-step procedure
- Immutable release images (no drift from latest)

---

## 🛠️ Quick Start

### From Docker (Recommended)

**Development (latest features):**
```bash
docker-compose up -d
# Access at http://localhost:8901
```

**Release (stable):**
```bash
docker-compose -f docker-compose.release.yml up -d
# Access at http://localhost:8001
```

### From Source

**Web App:**
```bash
python3 timiniprint_web.py
# Opens http://localhost:8901
```

**Command Line CLI:**
(the examples use Linux filenames)
- Print to the first supported Bluetooth printer:
  ```bash
  ./TiMini-Print-Command-Line-Linux-x86_64 /path/to/file.pdf
  ```

- Print to a specific Bluetooth printer:
  ```bash
  ./TiMini-Print-Command-Line-Linux-x86_64 --bluetooth "PRINTER_NAME" /path/to/file.pdf
  ```

- Print via a serial port (skip Bluetooth connection):
  ```bash
  ./TiMini-Print-Command-Line-Linux-x86_64 --bluetooth "PRINTER_NAME" --export-device-config printer.json
  ./TiMini-Print-Command-Line-Linux-x86_64 --serial /dev/rfcomm0 --device-config printer.json /path/to/file.pdf
  ```

- Print raw text without creating a file:
  ```bash
  ./TiMini-Print-Command-Line-Linux-x86_64 --text "Hello from CLI"
  ```

- List available printer profiles:
  ```bash
  ./TiMini-Print-Command-Line-Linux-x86_64 --list-profiles
  ```

- Scan for supported printers:
  ```bash
  ./TiMini-Print-Command-Line-Linux-x86_64 --scan
  ```

---

## 📖 Documentation

### Original Project Documentation
- 🔗 **[Original Repository](https://github.com/Dejniel/TiMini-Print)** — Creator's code, original README, issues
- 📄 [Protocol Reference](docs/protocol.md) — Printer protocol details
- 🏗️ [Architecture Guide](docs/architecture.md) — Design rationale

### Release Management
- 📋 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) — Step-by-step release procedure
- 🔄 Deployment policy: Releases via GitHub tags only, dev direct to Portainer

---

## 🔍 What Changed in This Fork?

### Code Changes
| File | Change | Purpose |
|------|--------|---------|
| `timiniprint/app/web.py` | Debug consolidation in `setupDebugMode()` | Single control point for all debug features |
| `timiniprint/app/web_static/app.js` | Defensive debug guards | Safe UI state management |
| `docker-compose.yml` | Port 8901, dev-latest image | Development channel config |
| `docker-compose.release.yml` | Port 8001, pinned v1.0.0 image | Release channel config |
| `Dockerfile` | Multi-stage, Node Exporter, env vars | Production-grade containerization |
| `.github/workflows/docker-publish.yml` | Channel-aware tagging | Automatic image publishing |

### New Files
- `RELEASE_CHECKLIST.md` — Release procedure (5 steps)
- `docker-compose.release.yml` — Stable release deployment

### No Breaking Changes
✅ Original CLI works unchanged  
✅ Original web app works unchanged  
✅ All 200+ printer models still supported  
✅ Printer detection, printing, features all intact  

---

## 👥 Contributing & Support

### For Bugs/Features in Original Code
Please report to **[Dejniel's Repository](https://github.com/Dejniel/TiMini-Print/issues)** — that's where the core development happens.

### For Fork-Specific Issues (Docker, channels, debug system)
Report here in this repository with `[Fork]` prefix in the title.

### Original Project Support
- 💙 Support Dejniel on [Buy Me a Coffee](https://buymeacoffee.com/dejniel)
- 🔗 [Contact Dejniel](https://inajiffy.eu/) for professional support
- 📚 Original project is open source — contributions welcome

---

## 📋 Supported Formats
- Images: .png .jpg .jpeg .gif .bmp
- PDF: prints all pages
- Text: .txt (monospace bold, word-wrapped by default)

## 📋 CLI Reference

### Notes
- If `--bluetooth` is omitted, the first supported printer found is used
- For `--serial`, you must pass `--device-config`
- `--export-device-config` writes the full resolved runtime config as JSON and `--device-config` loads that JSON back and forces the saved protocol/profile/runtime values
- On first Classic connection on Windows/macOS, the system may request pairing confirmation

### Library Integration
If you want to build your own integration instead of using only the bundled web app or CLI, start with [docs/protocol.md](docs/protocol.md). It is the practical first-steps guide to creating a `PrinterDevice`, building a printable job, and sending it through a connector from your own code. If you also want the package boundaries and design rationale behind that API, continue with [docs/architecture.md](docs/architecture.md).

---

## 🔗 Links

| Link | Purpose |
|------|---------|
| [Dejniel/TiMini-Print](https://github.com/Dejniel/TiMini-Print) | **Original repository** |
| [Releases](https://github.com/Dejniel/TiMini-Print/releases) | Original binary downloads |
| [Buy Me a Coffee](https://buymeacoffee.com/dejniel) | Support the original creator |
| [inajiffy.eu](https://inajiffy.eu/) | Professional support & consulting |

---

<div align="center">

**This is a community enhancement of [Dejniel's excellent project](https://github.com/Dejniel/TiMini-Print).**  
Please support the original creator if you find this tool useful! 💙

</div>

---

## 📋 Supported Printer Models

A200, A33, A41II, A41III, A42II, A43, A4300, CMT-0510, CP01, D1, D100, DL GE225, DL X2, DL X2 Pro, DL X7, DL X7 Pro, DT1-0, DTR-R0, DY03, DY49, EMX-040256, FC02, GB01, GB02, GB02SH, GB03, GB03PH, GB03PL, GB03SH, GB03SL, GB04, GB05, GB06, GL-VS9, GT01, GT03, GT04, GT08, GT09, GT10, GW08, GW09, HD1, HT0125, IM.04, IprintIt Printer, JRX01, JX001, JX002, JX003, JX004, JX005, JX006, JXM800, KF-5, LGM01, LP6, LP100, Label Printer CPLM10, Luxorp.PX10, ML-MP-01, MPA81, MV-B530, Mini Printer CTP500, MX05, MX07, MX08, MX09, MX11, P1, P2, P4, P5, P5AI, P6, P7, P7H, P10, PR02, PR07, PR20, PR25, PR30, PR35, PR88, PR89, PR893, PT001, Pocket Printer, Professional Printer CTP100LG, QDID, QDX01, ROSSMANN, RS9000, S01, S101, S102, SC03, SC03H, SC03h, SC04, SC04H, SC04h, SC05, Seznik Echo, Seznik Neo, Shipping Printer CTP750BY, Shipping Printer CTP800BD, TCM690464, U1, UXPORTMIP, V5X, WL01, WTS07, X100, X101H, X102, X103H, X103h, X16, X2H, X2h, X5, X5H, X5HP, X5h, X6H, X6HP, X6h, X7, X7H, X7HP, X7h, X8, X8-L, X8-W, X9, XC9, XiaoWa, XOPOPPY, YK06, YTB01, ZHHC, ZP801, ZP802, ZPA4Z1, 0019B-C, 0019B-D, 15P3, 58P5, AN01, DY01, Ewtto ET-Z0504, FL01, LT01, LY01, LY02, LY03, LY05, LY11, M01, M2, RT034h
- JX001 and clones: JX01
- JX002 and clones: JX02
- JX003 and clones: JX03
- JX004 and clones: JX04
- JX005 and clones: JX05
- JX006 and clones: JX06
- JXM800 and clones: GG-D2100
- LP100 and clones: LY10
- MX02 and clones: MX03
- MX06 and clones: MXTP-100, CYLO BT PRINTER, EWTTO ET-Z0499
- MX10 and clones: AZ-P2108X, PD01, MX12, MX13, MXW009, MXW010, KP-IM606, GV-MA211
- BQ02 and clones: BQ03, BQ17
- GT02 and clones: MINI PRINTER, JL-BR22
- YT01 and clones: YT02, MX01, MXPC-100, URBANWORX KIDS CAMERA, BQ01, BQ05, BQ06, BQ06B, BQ07, BQ08, BQ7A, BQ7B, BQ95, BQ95B, BQ95C, BQ96, EWTTO ET-N3687, EWTTO ET-N3689, K06, X6
- V5X and clones: AI01, MXW01, MXW01-1, MXW-W5, X1, X2, C17, AC695X_PRINT, JK01, PORTABLEPRINTER, INSTANTPRINTPLUS, REKA, HDMDT-00, KERUI, BH03
- M08F and clones: TP81, TP84, TP85, TP86, TP87, TP88, M832, M836, Q302, Q580, T02, T02E, Q02E, C02E
- PR20 and clones: XW001
- PR25 and clones: XW003
- PR30 and clones: XW002
- PR35 and clones: XW004
- PR88 and clones: XW005
- PR89 and clones: XW006
- PR893 and clones: XW007
- PR02 and clones: XW008
- PR07 and clones: XW009

## Experimental support
These entries are available, but they still need more real-device reports and tuning. In Bluetooth device lists they appear as `[experimental]`

Experimental printer models:
P100, MP100, P100S, MP100S, LP100S, P3, P3S

Experimental Bluetooth names:
- P100 and clones: YINTIBAO-V5, MP200, MP220, AEQ918N4
- P100S and clones: YINTIBAO-V5PRO, MP200S, MP220S
- LP100 and clones: LP220, LY100_BLE
- LP100S and clones: LP220S
- P3 and clones: MP300
- P3S and clones: MP300S
- DCK and clones: C21, D2, E2, NEWSMY
- V10G and clones: MXW-A4
