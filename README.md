# FT-991A Control Package

[![PyPI version](https://badge.fury.io/py/ft991a-control.svg)](https://badge.fury.io/py/ft991a-control)
[![Python Version](https://img.shields.io/pypi/pyversions/ft991a-control)](https://pypi.org/project/ft991a-control/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI-controllable Yaesu FT-991A transceiver interface with **web GUI**, **command-line tools**, and **MCP server** for AI integration.

> **🤖 AI Assistants:** This package exposes FT-991A ham radio control via MCP (Model Context Protocol). Use `ft991a-mcp` to launch the MCP server, then control frequency, mode, power, PTT, and monitor S-meter readings through standardized MCP tools.

## Features

- **🌐 Web GUI**: Real-time web interface with WebSocket updates
- **🖥️ CLI Tools**: Direct command-line control (`ft991a-cli`)  
- **🤖 MCP Server**: AI integration via Model Context Protocol (`ft991a-mcp`)
- **📡 Full CAT Control**: Frequency, mode, power, PTT, S-meter, band switching
- **🔒 Safety Features**: TX lockout, power limits, frequency validation
- **📊 Real-time Monitoring**: Live status updates and S-meter readings
- **🎛️ Memory Management**: Access programmed memory channels
- **🔌 Hardware Interface**: USB serial CAT control (38400 baud)

## Quick Install

```bash
# Install from PyPI
pip install ft991a-control

# Launch web GUI
ft991a-web

# Launch MCP server for AI
ft991a-mcp

# Direct CLI control  
ft991a-cli status
```

## Quick Start Guide

### 1. Hardware Setup

1. **Connect FT-991A**: USB-A to USB-B cable between radio and computer
2. **Enable CAT**: Radio Menu → 031 CAT RATE → 38400 baud  
3. **Check Device**: Verify `/dev/ttyUSB0` appears (Linux)
4. **Permissions**: Add user to `dialout` group: `sudo usermod -a -G dialout $USER`

### 2. Web GUI Mode

```bash
# Start web server
ft991a-web

# Open browser
firefox http://localhost:8000
```

**Web Interface Features:**
- Real-time frequency/mode display
- Click-to-tune frequency control  
- S-meter visualization
- Mode buttons (LSB/USB/CW/FM/AM/FT8)
- Power control slider
- PTT button (with safety confirmation)
- Band switching buttons

### 3. Command Line Mode

```bash
# Get radio status
ft991a-cli status

# Set frequency (20m FT8)
ft991a-cli freq set 14074000

# Change mode to USB  
ft991a-cli mode set DATA_USB

# Set power to 50W
ft991a-cli power set 50

# Switch to 40m band
ft991a-cli band 40M

# Get S-meter reading
ft991a-cli smeter
```

### 4. MCP Server Mode (AI Integration)

```bash
# Launch MCP server
ft991a-mcp --port /dev/ttyUSB0 --baud 38400
```

**Available MCP Tools:**
- `get_frequency` / `set_frequency` - Tune the radio
- `get_mode` / `set_mode` - Change operating modes  
- `get_power` / `set_power` - Control TX power
- `ptt_on` / `ptt_off` - Key/unkey transmitter
- `get_smeter` - Read signal strength
- `get_status` - Complete radio status
- `set_band` - Switch amateur bands
- `get_memories` / `recall_memory` - Memory channels

## Architecture

```
┌─────────────────┐    WebSocket     ┌─────────────────┐
│   Web Browser   │◄─────────────────┤   FastAPI       │
│   (ft991a-web)  │    Real-time     │   Web Server    │
└─────────────────┘    Updates       └─────────────────┘
                                             │
┌─────────────────┐                         │
│   AI Assistant  │◄── MCP Protocol ────────┤
│   (Claude, etc) │                         │
└─────────────────┘                         │
                                             │
┌─────────────────┐                         │
│   CLI Tools     │◄── Direct Access ───────┤
│   (ft991a-cli)  │                         │
└─────────────────┘                         │
                                             │
                          ┌─────────────────┴─────────────────┐
                          │         FT991A CAT Library        │
                          │         (ft991a.cat)             │
                          └─────────────────┬─────────────────┘
                                           │ USB Serial
                                           │ 38400 baud 
                                           │ ASCII CAT
                                           ▼
                                     ┌─────────────────┐
                                     │  Yaesu FT-991A  │
                                     │  Transceiver    │
                                     └─────────────────┘
```

## Installation Options

### From PyPI (Recommended)
```bash
pip install ft991a-control
```

### Development Install
```bash
git clone https://github.com/heliosarchitect/lbf-ham-radio.git
cd lbf-ham-radio
pip install -e .
```

### With Optional Dependencies
```bash
# Development tools
pip install ft991a-control[dev]

# Audio processing (future)  
pip install ft991a-control[audio]
```

## Configuration

### Serial Port Settings
```bash
# Default settings
--port /dev/ttyUSB0
--baud 38400

# Custom settings
ft991a-cli --port /dev/ttyACM0 --baud 9600 status
ft991a-web --radio-port /dev/ttyUSB1 --radio-baud 19200
ft991a-mcp --port /dev/serial/by-id/usb-FTDI... --baud 38400
```

### Radio Menu Settings
- **Menu 031** (CAT RATE): Set to **38400** or match `--baud` parameter
- **Menu 032** (CAT TOT): **10 min** or longer for continuous operation  
- **Menu 033** (CAT RTS): **Enable** for hardware flow control

## Safety & Best Practices

⚠️ **Important Safety Notes:**
- **RF Exposure**: Observe FCC/IC RF exposure limits
- **Antenna**: Always verify proper antenna connection before PTT
- **Power**: Start with low power (5-10W) for testing
- **Licensing**: Ensure amateur radio license privileges for frequency/mode
- **TX Lock**: Use `toggle_tx_lock` tool to prevent accidental transmission

🔒 **Built-in Safety Features:**
- Frequency range validation (30kHz - 56MHz)
- Power limits (5-100W) 
- Mode validation per frequency
- TX lockout functionality
- Serial timeout protection

## Troubleshooting

### Connection Issues
```bash
# Check USB device
lsusb | grep -i ftdi

# Check serial ports  
ls -la /dev/ttyUSB*

# Test permissions
groups $USER | grep dialout

# Manual connection test
ft991a-cli --port /dev/ttyUSB0 status
```

### Common Problems
- **Permission denied**: Add user to `dialout` group, logout/login
- **Device not found**: Check USB cable, try different port
- **Radio not responding**: Verify CAT enabled (Menu 031), correct baud rate
- **Web GUI not accessible**: Check firewall, try `--host 0.0.0.0`

## API Reference

### Python Library
```python
from ft991a import FT991A, Mode

# Connect to radio
radio = FT991A(port="/dev/ttyUSB0", baud=38400)
radio.connect()

# Basic operations
freq = radio.get_frequency()
radio.set_frequency(14074000)  # 20m FT8
radio.set_mode(Mode.DATA_USB)
status = radio.get_status()
```

### REST API (Web Server)
- `GET /api/status` - Get radio status
- `POST /api/frequency` - Set frequency  
- `POST /api/mode` - Set mode
- `POST /api/power` - Set TX power
- `WebSocket /ws` - Real-time updates

## Contributing

```bash
# Development setup
git clone https://github.com/heliosarchitect/lbf-ham-radio.git
cd lbf-ham-radio
pip install -e .[dev]

# Run tests
pytest tests/

# Code formatting  
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Hardware Support

**Tested Hardware:**
- Yaesu FT-991A (primary target)
- Linux (Ubuntu 22.04+, Debian 11+)
- USB-A to USB-B cables

**Future Hardware:** 
- Other Yaesu radios with compatible CAT
- Windows/macOS support
- CI-V interface (Icom)

## Screenshots

*[Screenshots placeholder - will be added after web deployment]*

## Related Projects

- **[Hamlib](https://hamlib.github.io/)**: Cross-platform radio control library
- **[flrig](https://github.com/w1hkj/flrig)**: Rig control GUI by W1HKJ  
- **[WSJT-X](https://wsjt.sourceforge.io/)**: Weak signal digital modes
- **[fldigi](https://sourceforge.net/projects/fldigi/)**: Multi-mode digital modem

---

**73!** 📡 *Happy hamming with AI-controlled FT-991A*