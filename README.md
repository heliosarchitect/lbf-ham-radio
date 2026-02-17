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
| **Scanner** | Band scanner with preset bands, custom range, step sizes, squelch threshold |
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
