# ThermoFlow Print - Docker Edition for End Users

This project is a fork of the original TiMini Print by Dejniel:
- Original repository: https://github.com/Dejniel/TiMini-Print
- Original releases: https://github.com/Dejniel/TiMini-Print/releases

## 1) What you can do with it (User Guide)

ThermoFlow Print lets you print to many small Bluetooth thermal printers (cat printers, mini printers, sticker printers) directly from a browser.

You can print:
- Images: PNG, JPG, JPEG, GIF, BMP
- PDF files
- Plain text

You do not need to be a software developer to use this.

## 2) Quick Install for normal users (Portainer)

If you use Portainer, this is the easiest way.

### Step 1: Open Stacks in Portainer
- Go to Stacks
- Click Add stack
- Name it: `timiniprint`

### Step 2: Paste this compose file
Use the stable release image:

```yaml
services:
  timiniprint:
    image: ghcr.io/cfridgen/timiniwebprint:v1.0.0
    restart: unless-stopped
    privileged: true
    network_mode: host
    environment:
      DBUS_SYSTEM_BUS_ADDRESS: "unix:path=/run/dbus/system_bus_socket"
      APP_PORT: "8001"
    volumes:
      - /run/dbus:/run/dbus
      - /var/run/dbus:/var/run/dbus
      - /run/udev:/run/udev:ro
    security_opt:
      - seccomp=unconfined
```

### Step 3: Deploy
- Click Deploy the stack
- Wait until container status is running

### Step 4: Open the web app
Open in your browser:
- `http://YOUR_SERVER_IP:8001`

Example:
- `http://192.168.1.20:8001`

## 3) First print in 60 seconds

1. Open the web page
2. Click Scan for printers
3. Select your printer
4. Upload image or PDF
5. Click Print

If no printer appears:
- Make sure Bluetooth is enabled on the host
- Keep printer close to the server (first test within 1-2 meters)
- Restart printer and scan again

## 4) Compatibility and supported models

The project supports many models. If your model name is not listed, it can still work (many devices are clones with different names).

Tip:
- Best way to verify compatibility is: deploy, scan, test-print a small image.

<details>
<summary>Show detailed supported model list</summary>

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

Experimental support:
- P100, MP100, P100S, MP100S, LP100S, P3, P3S

</details>

## 5) Installation alternatives (if you do not use Portainer)

### Docker Compose on Linux

Clone this repo and run:

```bash
docker compose -f docker-compose.release.yml up -d
```

Then open:
- `http://127.0.0.1:8001`

### Run from Python source (advanced users)

```bash
pip install -r requirements.txt
python3 timiniprint_web.py
```

Default development web port is:
- `http://127.0.0.1:8901`

## 6) Troubleshooting (simple)

### No printers found
- Confirm host Bluetooth service is running
- Confirm DBus mounts are present (`/run/dbus`, `/var/run/dbus`)
- Reboot printer and retry scan

### Page opens, but print does not start
- Test with a small black/white image first
- Try one-page PDF first
- Reconnect printer and retry

### Port is already used
- Release uses port `8001`
- Development uses port `8901`

## 7) Branding and visual assets

This fork keeps the original printing logic and focuses on making installation and daily usage easier for normal users who just want to print.

![ThermoFlow Print brand banner](thermoflow_wordmark_dark.png)

<p align="left">
  <img src="thermoflow_appicon.png" alt="ThermoFlow Print app icon" width="180" />
</p>

Brand assets:
- Dark wordmark: [thermoflow_wordmark_dark.png](thermoflow_wordmark_dark.png)
- Light wordmark: [thermoflow_wordmark_light.png](thermoflow_wordmark_light.png)
- App icon: [thermoflow_appicon.png](thermoflow_appicon.png)
- Usage rules: [brand/BRAND_GUIDELINES.md](brand/BRAND_GUIDELINES.md)

## 8) Information for self-hosters and developers

Technical docs:
- Protocol guide: [docs/protocol.md](docs/protocol.md)
- Architecture: [docs/architecture.md](docs/architecture.md)

Release management docs:
- Release checklist: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)

## 9) Development and release model

This fork uses two deployment channels:

- Release channel:
  - Image: `ghcr.io/cfridgen/timiniwebprint:v1.0.0`
  - Port: `8001`
  - Goal: stability for normal users

- Development channel:
  - Image: `ghcr.io/cfridgen/timiniwebprint:dev-latest`
  - Port: `8901`
  - Goal: rapid testing of new changes

Build and publish policy:
- Release images are created via GitHub tag workflow
- Development images track latest development state

## 10) Fork details (end of document by design)

What this fork is:
- A compatibility-preserving enhancement of the original project
- Focused on easier container deployment and operations
- Not a rewrite and not a replacement of upstream

What this fork changed:
- Better Docker/Portainer out-of-the-box setup
- More robust Bluetooth support inside containers
- Clear release/dev separation
- Consolidated debug controls

Upstream policy:
- We do not push changes back to Dejniel's repository directly from here
- We can review upstream changes and selectively integrate them after testing

Detailed governance:
- [FORK_POLICY.md](FORK_POLICY.md)
