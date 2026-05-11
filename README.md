# 🖨️ TiMini Print — Enhanced Docker Edition

> **🔗 Community Fork of [Dejniel's TiMini-Print](https://github.com/Dejniel/TiMini-Print)**
> 
> This is a production-enhanced fork adding containerization, robust Bluetooth support, and release/development channel separation. **All original functionality is preserved** — this is an enhancement, not a reimplementation.

## ✨ What is TiMini Print?

A practical desktop/web tool for **Chinese Bluetooth thermal printers** (non ESC/POS), compatible with apps like Tiny Print, Fun Print, Phomemo, and iBleem.

**Supports 200+ printer models**. This fork keeps upstream behavior and adds deployment and operations improvements.

**Original creator:** [Dejniel](https://github.com/Dejniel) | **Upstream repo:** [Dejniel/TiMini-Print](https://github.com/Dejniel/TiMini-Print)

![TiMini Print LOGO EMX-040256 Printer Psi Patrol](EMX_040256.jpg)

---

## 🚀 Fork Changes (Only)

| Area | What we added | Why it matters |
|------|----------------|----------------|
| Channels | Release channel on `8001`, Dev channel on `8901` | Stable releases + fast iteration |
| Linux Bluetooth in Docker | DBus + udev mounts, host networking | Printer scan/connect works reliably |
| Debug handling | Unified `setupDebugMode()` + feature flag | Predictable behavior, safer default UI |
| Containerization | Production Dockerfile + monitoring hooks | Better observability and operations |
| Releases | Tag-driven GitHub release images (`v1.0.0`) | Reproducible deployments without hash juggling |

### ✅ What remains unchanged from upstream
- Core protocol and printer compatibility
- CLI behavior and print pipeline
- Web app core flow (scan, connect, print)
- Supported printer model catalog

### 🔄 Deployment flow
`master` -> `dev-latest` (port `8901`)  
`git tag vX.Y.Z` -> `vX.Y.Z` + `release-latest` (port `8001`)

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

**CLI quick example:**
```bash
./TiMini-Print-Command-Line-Linux-x86_64 --scan
```

For full CLI options and integration details, see [docs/protocol.md](docs/protocol.md) and [docs/architecture.md](docs/architecture.md).

---

## 📌 Important Links

- Upstream repository: [Dejniel/TiMini-Print](https://github.com/Dejniel/TiMini-Print)
- Upstream issues: [github.com/Dejniel/TiMini-Print/issues](https://github.com/Dejniel/TiMini-Print/issues)
- Release process (this fork): [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
- Fork governance and upstream sync policy: [FORK_POLICY.md](FORK_POLICY.md)
- Protocol docs: [docs/protocol.md](docs/protocol.md)
- Architecture docs: [docs/architecture.md](docs/architecture.md)

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
