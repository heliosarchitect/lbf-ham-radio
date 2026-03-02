# FT-991A Control Package

[![PyPI version](https://badge.fury.io/py/ft991a-control.svg)](https://badge.fury.io/py/ft991a-control)
[![Python Version](https://img.shields.io/pypi/pyversions/ft991a-control)](https://pypi.org/project/ft991a-control/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI-controllable Yaesu FT-991A transceiver interface with **LCARS-themed web GUI**, **command-line tools**, and **MCP server** for AI integration.

> **🤖 AI Assistants:** This package exposes FT-991A ham radio control via MCP (Model Context Protocol). Use `ft991a-mcp` to launch the MCP server, then control frequency, mode, power, PTT, and monitor S-meter readings through standardized MCP tools.

## Features

### 🌐 LCARS Web GUI (Star Trek Theme)
- **10+ tabbed interface** — VFO Control, Audio/Waterfall, Band Scanner, Memory Channels, System, Config, Status, Diagnostics
- **Audio Waterfall** — Real-time spectrogram via PCM2903B USB CODEC + browser-side FFT
- **Spectrum Analyzer** — Overlay with gradient fill, grid lines, center frequency marker
- **5 Color Palettes** — RADIO (default), AMBER, BLUE, GREEN, GRAY with pre-computed color LUTs
- **Inline VFO Tuner** — Click-to-type frequency entry, UP/DN buttons, step selector (10 Hz–1 MHz), arrow key tuning
- **S-Meter History Chart** — Last 120 readings with peak/avg labels and color gradient
- **Band Scanner** — Sweep frequency ranges with configurable step size and squelch, click-to-tune results, CSV export
- **Memory Channel Manager** — List, recall, store, and clear channels 001-099
- **Antenna Auto-Tune** — ATU control button (AC001/AC002 CAT commands)
- **SDR Panadapter** — Wideband waterfall via SDRplay RSP2pro (SoapySDR)
- **Audio Streaming** — Listen to radio audio directly in the browser
- **WebSocket Real-time Updates** — Live frequency, mode, S-meter, TX status
- **Mobile Responsive** — Horizontal scrollable tab bar for phone/tablet

### 🖥️ CLI Tools
- `ft991a-cli status` — Get radio status
- `ft991a-cli freq set <hz>` — Set frequency
- `ft991a-cli mode set <mode>` — Change mode
- `ft991a-cli cw encode/decode/send` — Morse code operations
- `ft991a-cli scan band --heatmap [--max-bins N] [--hotspots --hotspot-threshold S --hotspot-top N] [--hotspot-windows --window-gap-hz HZ] [--window-plan --plan-cycle-ms MS] [--window-timeline] [--window-clock] [--window-now] [--window-upcoming --upcoming-count N] [--window-brief --upcoming-count N] [--window-cue] [--window-action --action-ready-ms MS] [--window-decision --action-critical-ms MS] [--window-ops --upcoming-count N] [--window-directive --upcoming-count N] [--window-handoff --upcoming-count N] [--window-snapshot --upcoming-count N] [--window-fingerprint] [--window-stability]` — Adaptive RX band activity heatmap + ranked hotspots + merged hotspot windows + ranked RX review plan + cycle timeline projection + wall-clock sync schedule + upcoming handoff projection + compact live handoff brief + one-line live handoff cue + HOLD/READY/SWITCH handoff action signal + urgency/recheck decision signal + compact ops card with queue snapshot + actionable directive checklist + compact shift-handoff packet + machine-friendly one-line snapshot + deterministic fingerprint + stability classification (Features 1/20–18/20)

#### Adaptive Heatmap — Operator Note (Interface-Controlled)
- Scope is restricted to the existing `scan band` command path.
- `--heatmap` enables adaptive RX activity summarization; `--max-bins` limits output density.
- `--hotspots` adds ranked candidate frequencies from the same adaptive heatmap model (`--hotspot-threshold`, `--hotspot-top`).
- `--hotspot-windows` merges nearby hotspot bins into tune-ready windows (`--window-gap-hz`) to reduce frequency hopping during manual review.
- `--window-plan` builds a ranked, dwell-timed RX review sequence from hotspot windows (`--plan-cycle-ms`) for faster manual monitoring loops.
- `--window-timeline` projects that ranked plan into one-cycle offsets (`start/end/revisit`) so operators can coordinate listen windows without changing radio state.
- `--window-clock` anchors timeline offsets to current local wall-clock time so teams can synchronize manual RX monitoring in real time.
- `--window-now` resolves the current active window plus next scheduled step from that wall-clock plan for live RX handoff guidance.
- `--window-upcoming` projects the next queued handoff steps from the current wall-clock position (`--upcoming-count`) so operators can pre-brief upcoming manual tune sequence.
- `--window-brief` provides one compact RX handoff brief (active frequency, switch countdown, and upcoming queue) to reduce operator context switching during manual monitoring.
- `--window-cue` provides a single-line active→next handoff cue for low-overhead terminal glance checks.
- `--window-action` adds a one-line HOLD/READY/SWITCH directive derived from live handoff timing; tune READY sensitivity via `--action-ready-ms`.
- `--window-decision` adds one-line action+urgency escalation (LOW/MEDIUM/HIGH/CRITICAL) plus a recommended recheck cadence; tune HIGH/CRITICAL boundary via `--action-critical-ms`.
- `--window-ops` adds a compact multi-line operator ops card that combines decision state with a near-term handoff queue (`--upcoming-count`) for lower-overhead manual RX execution.
- `--window-directive` adds a concise actionable checklist distilled from ops-card state to reduce handoff misses during manual RX loops.
- `--window-handoff` adds a compact shift-handoff packet (headline + immediate steps + queued steps) for fast operator transitions.
- `--window-snapshot` adds a one-line machine-friendly handoff snapshot (`key=value`) for logs/automation glue while staying RX-only.
- `--window-fingerprint` adds deterministic snapshot signatures for dedupe/change-tracking automation.
- `--window-stability` adds a stability score (`STABLE`/`WATCH`/`VOLATILE`) from urgency + countdown pressure.
- These features are receive-side analysis only; they do not add or modify TX behavior.
- No new top-level CLI groups or web/MCP API surfaces are introduced by these features.

### 🤖 MCP Server (AI Integration)
- Full radio control via Model Context Protocol
- Compatible with Claude, GPT, and other MCP-capable assistants

### 📡 CAT Protocol
- Complete Yaesu CAT command implementation
- Frequency, mode, power, PTT, S-meter, band switching
- Memory channel read/write (MR/MC/MW commands)
- Antenna tuner control (AC commands)
- VFO swap, A→B copy
- TX lockout safety

## Quick Install

```bash
# Install from PyPI
pip install ft991a-control

# Launch LCARS web GUI
ft991a-web --host 0.0.0.0 --port 8000 --radio-port /dev/ttyUSB0

# Launch MCP server for AI
ft991a-mcp

# Direct CLI control
ft991a-cli status
```

## Hardware Setup

### Required
1. **Yaesu FT-991A** with USB-A to USB-B cable
2. **Linux host** (tested on Ubuntu 22.04)
3. Radio Menu → 031 CAT RATE → **38400 baud**
4. Add user to `dialout` group: `sudo usermod -a -G dialout $USER`

### Recommended
- **USB Audio CODEC** (e.g., PCM2903B) for audio waterfall
- **SDRplay RSP2pro** (or compatible SoapySDR device) for wideband panadapter

### Udev Rules (Stable Device Paths)
```bash
# /etc/udev/rules.d/99-ft991a.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea70", \
  ATTRS{bInterfaceNumber}=="01", SYMLINK+="ft991a-cat"
```

Then use `--radio-port /dev/ft991a-cat` for stable access regardless of USB enumeration order.

## Architecture

```
┌─────────────────┐    WebSocket     ┌─────────────────┐
│   Web Browser   │◄────────────────►│   FastAPI        │
│   LCARS GUI     │  Real-time       │   Web Server     │
│                 │  Audio/FFT       │   (ft991a-web)   │
└─────────────────┘                  └────────┬─────────┘
                                              │
┌─────────────────┐                          │
│   AI Assistant  │◄── MCP Protocol ─────────┤
│   (Claude, etc) │                          │
└─────────────────┘                          │
                                              │
┌─────────────────┐    ┌─────────────────┐   │
│   SDRplay       │    │   USB Audio     │   │
│   RSP2pro       │    │   CODEC         │   │
│   (SoapySDR)    │    │   (PCM2903B)    │   │
└────────┬────────┘    └────────┬────────┘   │
         │ IQ Data              │ PCM Audio  │
         └──────────────────────┴────────────┤
                                              │
                    ┌─────────────────────────┴───────────┐
                    │         FT991A CAT Library          │
                    │         (ft991a.cat)                │
                    └─────────────────┬───────────────────┘
                                      │ USB Serial
                                      │ 38400 baud, 2 stop bits
                                      ▼
                                ┌─────────────────┐
                                │  Yaesu FT-991A  │
                                │  Transceiver    │
                                └─────────────────┘
```

## Web GUI Tabs

| Tab | Description |
|-----|-------------|
| **VFO Control** | Frequency display, mode buttons, band presets, power slider, VFO swap/copy, ATU |
| **Audio** | Audio waterfall, spectrum analyzer, inline tuner, S-meter history, listen button |
| **SDR** | Wideband panadapter waterfall via SDRplay (click-to-tune, bandwidth selector) |
| **Scanner** | Band scanner with preset bands, custom range, step sizes, squelch threshold, and adaptive RX heatmap (`ft991a-cli scan band --heatmap`) |
| **Memory** | Memory channel manager — list, recall, store, clear channels 001-099 |
| **System** | Audio device config, WebSocket status, connection info |
| **Config** | Serial port settings, baud rate, connection test |
| **Status** | Live radio status, VFO-A/B, mode, power, S-meter, SWR |
| **Diagnostics** | Error log, raw CAT command testing, system health |

## CI/CD

GitHub Actions automatically publishes to PyPI on version tag push:

```bash
# Bump version in pyproject.toml and __init__.py, then:
git tag v0.6.2
git push github main --tags
# → GitHub Actions builds and publishes to PyPI
```

## Configuration

### Serial Port Settings
```bash
ft991a-web --radio-port /dev/ft991a-cat --radio-baud 38400 --host 0.0.0.0 --port 8000
```

### Radio Menu Settings
- **Menu 031** (CAT RATE): **38400** (or match `--radio-baud`)
- **Menu 032** (CAT TOT): **10 min** or longer
- **Menu 033** (CAT RTS): **Enable**

## Safety

⚠️ **Important:**
- Always verify proper antenna connection before TX
- Use TX lockout when not actively transmitting
- Ensure amateur radio license privileges for frequency/mode
- Start with low power (5-10W) for testing
- **Never transmit without a licensed operator present**

🔒 **Built-in Safety:**
- Frequency range validation (30 kHz – 470 MHz)
- Power limits (5-100W)
- TX lockout toggle
- Mode validation per frequency
- Serial timeout protection

## Python API

```python
from ft991a import FT991A, Mode

radio = FT991A(port="/dev/ft991a-cat", baudrate=38400)
radio.connect()

# Read status
status = radio.get_status()
print(f"Frequency: {status.frequency_a} Hz")
print(f"Mode: {status.mode}")
print(f"S-Meter: {status.s_meter}")

# Tune
radio.set_frequency_a(14_250_000)  # 20m SSB
radio.set_mode(Mode.USB)

# Antenna tuner
radio.tuner_start()  # Auto-tune

# Memory channels
radio.recall_memory(1)
radio.store_memory(5)
```

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Radio status (frequency, mode, S-meter, TX) |
| `/api/frequency/a` | POST | Set VFO-A frequency |
| `/api/frequency/b` | POST | Set VFO-B frequency |
| `/api/mode` | POST | Set operating mode |
| `/api/power` | POST | Set TX power |
| `/api/tuner/start` | POST | Start antenna auto-tune |
| `/api/tuner/on` | POST | Turn ATU on |
| `/api/tuner/off` | POST | Turn ATU off |
| `/api/vfo/swap` | POST | Swap VFO-A ⇄ VFO-B |
| `/api/vfo/a-to-b` | POST | Copy VFO-A → VFO-B |
| `/api/scan` | POST | Start band scan |
| `/api/scan/stop` | POST | Stop scan |
| `/api/memory/list` | GET | List memory channels |
| `/api/memory/recall` | POST | Recall memory channel |
| `/api/memory/store` | POST | Store to memory channel |
| `/api/memory/clear` | POST | Clear memory channel |
| `/ws` | WebSocket | Real-time status updates |
| `/ws/audio` | WebSocket | Audio FFT stream |
| `/ws/sdr` | WebSocket | SDR wideband FFT stream |

## Contributing

```bash
git clone https://github.com/heliosarchitect/lbf-ham-radio.git
cd lbf-ham-radio
pip install -e .[dev]
pytest tests/
```

## License

MIT License — see [LICENSE](LICENSE).

## Links

- **PyPI**: https://pypi.org/project/ft991a-control/
- **GitHub**: https://github.com/heliosarchitect/lbf-ham-radio
- **Gitea**: https://gitea.fleet.wood/Helios/lbf-ham-radio

---

**73 de KO4TUV!** 📡 *AI-controlled ham radio with LCARS style*
