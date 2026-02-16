# FT-991A Web GUI

Full-featured web interface for controlling the Yaesu FT-991A amateur radio transceiver via CAT (Computer Aided Transceiver) protocol.

> **🤖 AI Agents:** This is a standalone ham radio control project with web GUI, CAT library, and real-time WebSocket updates. Core files: `ft991a.py` (CAT library), `server.py` (FastAPI backend), `static/index.html` (web interface).

## Overview
Web-based control panel for the Yaesu FT-991A HF/VHF/UHF transceiver. Provides real-time frequency, mode, and status monitoring via WebSocket, plus complete remote control capabilities. Designed for shack integration, digital mode operation, and mobile/tablet use alongside the physical radio.

## Architecture
```
┌─────────────────┐    USB/Serial    ┌─────────────────┐
│   Web Browser   │◄──── WebSocket ──┤   FastAPI       │
│   (Frontend)    │      Updates      │   Server        │
└─────────────────┘                  │   (server.py)   │
                                     │                 │
┌─────────────────┐                  │                 │
│  REST API       │◄─────────────────┤                 │
│  (OpenClaw)     │    HTTP/JSON     │                 │
└─────────────────┘                  │                 │
                                     │                 │
                                     │   ft991a.py     │
                                     │   (CAT Library) │
                                     └─────┬───────────┘
                                           │ 38400 baud
                                           │ ASCII CAT
                                           ▼
                                     ┌─────────────────┐
                                     │  Yaesu FT-991A  │
                                     │  Transceiver    │
                                     └─────────────────┘
```

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Connect FT-991A via USB (appears as /dev/ttyUSB0)
# Ensure CAT is enabled on radio: Menu → 031 CAT RATE → 38400

# Start web server
python3 server.py

# Access web interface
firefox http://localhost:8991

# Or start as systemd service
systemctl --user enable systemd/ft991a-web.service
systemctl --user start ft991a-web.service
```

## Configuration
| Setting | Location | Description |
|---------|----------|-------------|
| CAT Rate | Radio Menu 031 | Must be set to 38400 baud |
| USB Serial | `/dev/ttyUSB0` | Radio's built-in USB-serial adapter |
| Web Port | `server.py --port` | Default 8991, configurable |
| Audio Device | `pulseaudio/pipewire` | USB sound card for digital modes |

## Services
| Service | Command | Port | Status |
|---------|---------|------|--------|
| ft991a-web | `systemctl --user status ft991a-web` | 8991 | Development |

## Features

### 🎛️ Complete Transceiver Control
- **Frequency Control**: Direct entry, VFO knob simulation, band switching
- **Mode Selection**: LSB/USB/CW/FM/AM/DATA/C4FM (all FT-991A modes)
- **Power Control**: 5-100W adjustable (HF), 5-50W (VHF/UHF)
- **VFO Operations**: A/B swap, copy A→B, split operation
- **Memory Channels**: Read/write/recall (via CAT commands)

### 📡 Real-Time Monitoring
- **Live S-Meter**: Real-time signal strength via WebSocket (2 Hz updates)
- **TX/RX Status**: Visual PTT indicator with safety lockout
- **SWR Monitoring**: Antenna match indication during transmission
- **Squelch Status**: SQL open/closed indication

### 📱 Modern Interface
- **Responsive Design**: Works on desktop, tablet, mobile
- **Touch-Friendly**: Large buttons, gesture support for VFO tuning
- **Dark Theme**: Easy on eyes during long operating sessions
- **WebSocket Updates**: No page refresh needed, live data

### 🔒 Safety Features
- **TX Lockout**: Prevents accidental transmission
- **Deliberate PTT**: Large button requires intentional press
- **Auto PTT-Off**: Ensures PTT releases on disconnect
- **Visual TX Warning**: Animated PTT indicator when transmitting

### 🎧 Digital Mode Integration
Built-in USB sound card routing for:
- **FT8/FT4**: WSJT-X integration via USB audio
- **PSK31**: Digital mode software compatibility  
- **CW Decoding**: Audio monitoring and control
- **Packet Radio**: Terminal Node Controller support

## API Endpoints

### Radio Control
- `GET /api/status` - Current radio status
- `POST /api/frequency/a` - Set VFO-A frequency
- `POST /api/mode` - Change operating mode
- `POST /api/power` - Set TX power level
- `POST /api/ptt` - PTT control (with lockout check)
- `POST /api/lockout` - Toggle TX safety lockout

### WebSocket
- `WS /ws` - Real-time status updates, 2 Hz

## Audio Setup (Linux)

The FT-991A includes a USB sound card. Configure PulseAudio/PipeWire:

```bash
# List available audio devices
pactl list short sources | grep -i yaesu
pactl list short sinks | grep -i yaesu

# Set as default for digital modes
pactl set-default-source "alsa_input.usb-YAESU_FT-991A..."
pactl set-default-sink "alsa_output.usb-YAESU_FT-991A..."

# Or use pavucontrol GUI
pavucontrol
```

### WSJT-X Configuration
1. **Audio Tab**: Select "USB Audio CODEC" for both input/output
2. **Radio Tab**: Select "Yaesu FT-991A" with CAT control
3. **Frequencies**: Use FT8 quick buttons in web interface

## ⛔ Constraints (What NOT To Do)
- **NO PTT without lockout check** — Accidental transmission can cause interference or damage. Always verify TX lockout status.
- **NO high duty cycle modes at full power** — FT8/FT4 at 100W can overheat finals. Use 50W max for continuous digital modes.
- **NO operation without antenna** — High SWR can damage PA. Monitor SWR meter during tuning.
- **NO CAT commands while transmitting** — Radio may not respond during TX. Check TX status before API calls.

## Development

### File Structure
```
lbf-ham-radio/
├── ft991a.py              # CAT control library
├── server.py              # FastAPI web server
├── static/index.html      # Web interface (self-contained)
├── requirements.txt       # Python dependencies
├── systemd/               # Service files
│   └── ft991a-web.service
└── README.md
```

### Adding New Features
1. **CAT Commands**: Add to `ft991a.py` following existing patterns
2. **API Endpoints**: Add to `server.py` with proper error handling
3. **Frontend**: Update `static/index.html` - single file with embedded CSS/JS
4. **WebSocket**: Broadcast updates in `monitor_radio()` function

### Testing
```bash
# Test CAT library directly
python3 ft991a.py --port /dev/ttyUSB0 status

# Test web server
curl http://localhost:8991/api/status

# Test WebSocket
websocat ws://localhost:8991/ws
```

## Related Repos
| Repo | Purpose |
|------|---------|
| [OpenClaw](https://github.com/lbf/openclaw) | Agent framework providing API integration |
| [WSJT-X](https://physics.princeton.edu/pulsar/K1JT/wsjtx.html) | Digital mode software for FT8/FT4 |

---
*Part of the LBF Operations ecosystem. Managed by Helios.*
*Template: lbf-templates/project/README.md*