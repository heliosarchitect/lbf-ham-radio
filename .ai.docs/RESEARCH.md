# FT-991A Linux Software Research
> Compiled 2026-02-16

## Existing Linux Software Ecosystem

### Rig Control (CAT)
| Software | Type | FT-991A Support | Notes |
|----------|------|-----------------|-------|
| **Hamlib** (`rigctld`) | Daemon/lib | ✅ Native (rig #1036) | Industry standard. Shared CAT access via TCP. Single serial client limitation solved by rigctld daemon |
| **flrig** | GUI + daemon | ✅ | Standalone rig control GUI by W1HKJ. Works with fldigi. Handles CAT, PTT, frequency, mode |
| **grig** | GTK GUI | ✅ via Hamlib | Simple rig control front-end |
| **991A-Commander** | CLI (bash/Python) | ✅ Purpose-built | github.com/rfrht/991A-Commander. Status monitor, SWR protection, memory backup/restore, SPR/SPW raw memory access |
| **891ctrl** (DO1ZL) | Browser GUI | ❌ FT-891 only | Inspiration for our approach — browser-based CAT + panadapter. Cross-platform |
| **catmacs** | Emacs Lisp | ✅ | Emacs minor mode for RX CAT control. Niche but shows feasibility |

### Digital Modes
| Software | Modes | FT-991A Notes |
|----------|-------|---------------|
| **WSJT-X** | FT8, FT4, JT65, JT9, WSPR | Primary FT8 software. Uses Hamlib or flrig for CAT. Audio via USB sound card |
| **fldigi** | PSK31, RTTY, CW, Olivia, MFSK, Throb, DominoEX, Hell | Multi-mode digital modem. CW decode/encode built in |
| **JS8Call** | JS8 (keyboard FT8 variant) | QSO-style digital messaging over HF |
| **FreeDV** | Digital voice (HF) | Open codec2-based digital voice |
| **Direwolf** | APRS, AX.25 packet | Software TNC, APRS encoder/decoder, digipeater |

### CW / Morse Code
| Software | Function | Platform |
|----------|----------|----------|
| **fldigi** | CW decode + encode | Linux native |
| **CW Skimmer** | Multi-channel CW decoder | Windows (Wine possible) |
| **unixcw** | CLI CW tools (cw, cwgen, cwcp, xcwcp) | Linux native |
| **qrq** | CW training / speed practice | Linux native |
| **MRP40** | CW decoder | Windows only |
| **MultiPSK** | CW + multi-mode | Windows (free CW) |

### Logging
| Software | Platform | Notes |
|----------|----------|-------|
| **CQRlog** | Linux | Most popular Linux logging |
| **Log4OM2** | Cross-platform | |
| **JTDX** | Cross-platform | Enhanced FT8/JT65 with logging |

### Other Useful Tools
| Software | Function |
|----------|----------|
| **CHIRP** | Radio memory programmer (supports FT-991A) |
| **xastir** | APRS mapping & messaging |
| **gpredict** | Satellite tracking |
| **xnec2c** | Antenna modeling |
| **NanoVNA Saver** | Antenna analyzer GUI |

## FT-991A USB Architecture

The FT-991A presents **3 USB devices** through a single USB-B cable:
1. **Serial port 1** (`/dev/ttyUSB0`) — CAT control (standard commands)
2. **Serial port 2** (`/dev/ttyUSB1`) — Enhanced CAT / special commands
3. **USB Audio** ("USB CODEC AUDIO") — Built-in sound card (no extra cables needed!)

### CAT Settings
- Menu item **031**: CAT baud rate → set to **38400** for best performance
- Menu item **032**: CAT TOT (timeout) → default OK
- Menu item **033**: CAT RTS → default OK

### Key Constraints
- **Only ONE program can connect to a serial port at a time**
- Solution: Run `rigctld` as daemon, all programs connect via TCP (localhost:4532)
- USB cable quality matters — use shielded cable with ferrite chokes
- The FT-991A has a known issue where CAT interface drops with poor USB cables

## Architecture Decision: What We Build vs. What We Reuse

### REUSE (don't reinvent)
- **Hamlib/rigctld** — rig control daemon (shared access)
- **WSJT-X** — FT8/FT4 (gold standard, no point rebuilding)
- **fldigi** — multi-mode digital (PSK31, RTTY, CW decode)
- **CHIRP** — memory programming

### BUILD (our web GUI)
A unified web interface that:
1. **Wraps rigctld** (not direct serial) for shared CAT access
2. **Full transceiver control** — everything via browser
3. **REST + WebSocket API** — so OpenClaw can control the radio programmatically
4. **Integrates with existing tools** — launch/configure WSJT-X, fldigi from the GUI
5. **Audio routing dashboard** — PulseAudio/PipeWire config for USB sound card
6. **Unique value**: AI-assisted operation (band monitoring, auto-logging, CW decode display)

### Why Build Our Own GUI
- 891ctrl (DO1ZL) proves browser-based CAT works but is FT-891 specific
- 991A-Commander is CLI only, no GUI
- flrig is a GUI but not web-based (can't access remotely)
- No existing tool has AI integration or API for programmatic control
- We want ONE interface that ties everything together

## Installation Checklist (for the Linux box)

```bash
# 1. Base packages
sudo apt install -y hamlib-utils python3-pip python3-venv pulseaudio pavucontrol

# 2. Ham radio software
sudo apt install -y fldigi flrig wsjtx js8call chirp direwolf

# 3. Serial port access
sudo usermod -aG dialout $USER

# 4. Verify FT-991A USB devices
# After connecting USB cable:
ls /dev/ttyUSB*     # Should show ttyUSB0 and ttyUSB1
aplay -l            # Should show "USB CODEC AUDIO"
arecord -l          # Same

# 5. Start rigctld daemon
rigctld -m 1036 -r /dev/ttyUSB0 -s 38400 &

# 6. Test CAT connection
rigctl -m 2 -r localhost:4532 f   # Should return current frequency
```

## References
- [PA0ROB's Ubuntu + FT-991A guide](http://pa0rob.vandenhoff.info/linux-ubuntu)
- [991A-Commander (GitHub)](https://github.com/rfrht/991A-Commander)
- [FT-991A memory map (KI5BPK)](https://www.kloepfer.org/ft991a/memory-map.txt)
- [Arch Wiki: Amateur Radio](https://wiki.archlinux.org/title/Amateur_radio)
- [LinuxWolfPack FT-991 fldigi setup](https://www.linuxwolfpack.com/ft991-fldigi-linux.php)
- Yaesu FT-991A CAT Operation Reference Manual (1711-D)
