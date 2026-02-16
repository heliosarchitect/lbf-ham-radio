# FT-991A Control — Feature Roadmap

> `pip install ft991a-control` | PyPI: [ft991a-control](https://pypi.org/project/ft991a-control/)
> GitHub: [heliosarchitect/lbf-ham-radio](https://github.com/heliosarchitect/lbf-ham-radio)

---

## v0.3.x — Foundation (✅ CURRENT)

- [x] CAT control library (full FT-991A command set)
- [x] FastAPI web GUI with WebSocket real-time updates
- [x] MCP server (14 tools) for AI integration
- [x] CLI entry points (`ft991a-web`, `ft991a-cli`, `ft991a-mcp`)
- [x] PyPI package published
- [x] CI/CD (GitHub Actions + Gitea, auto-publish on tag)
- [x] Unit tests (15 passing, mocked serial)
- [x] Research doc (existing Linux ham software ecosystem)

---

## v0.4.0 — Hardware Validation & Audio

**Goal**: Verified working on real hardware, audio routing functional.

- [ ] Integration tests with live FT-991A hardware
- [ ] USB device auto-detection (`/dev/ttyUSB0`, `/dev/ttyUSB1`, USB CODEC AUDIO)
- [ ] PulseAudio/PipeWire audio routing for USB sound card
- [ ] Audio level meters in web GUI (RX audio visualizer)
- [ ] Audio recording/playback (monitor received audio from browser)
- [ ] Squelch status indicator
- [ ] Connection auto-reconnect on USB disconnect/reconnect
- [ ] Fix any CAT command timing issues discovered on real hardware
- [ ] Systemd service validated and documented

---

## v0.5.0 — Digital Modes Integration

**Goal**: First-class FT8/FT4 and digital mode support.

- [ ] WSJT-X integration (auto-configure CAT + audio routing)
- [ ] fldigi integration (launch, configure, monitor)
- [ ] Hamlib `rigctld` wrapper (shared CAT access for multiple programs)
- [ ] FT8 decode display in web GUI (via WSJT-X UDP stream)
- [ ] Digital mode quick-switch buttons (FT8 @ 14.074, FT4 @ 14.080, etc.)
- [ ] Auto-set radio to correct mode/frequency for digital operation
- [ ] WSJT-X log parsing → contact display in GUI

---

## v0.6.0 — CW / Morse Code

**Goal**: Full CW operation from the web GUI + AI-assisted decode.

- [ ] CW decoder (audio → text) using DSP or fldigi bridge
- [ ] CW encoder (text → keying via CAT)
- [ ] CW keyboard mode in web GUI (type text, radio sends morse)
- [ ] Speed control (WPM slider)
- [ ] CW practice/training mode (generate random callsigns, copy practice)
- [ ] Decode waterfall display
- [ ] AI-assisted CW: auto-respond to CQ calls with proper QSO format
- [ ] Morse code prosigns and abbreviations reference

---

## v0.7.0 — Band Monitoring & Intelligence

**Goal**: AI-powered band awareness and signal detection.

- [ ] Band scope integration (if available via CAT, otherwise via audio FFT)
- [ ] Automatic band scan (sweep frequencies, log active signals)
- [ ] Signal strength heatmap by frequency/time
- [ ] Propagation overlay (integrate solar/HF prediction data)
- [ ] DX cluster feed integration (live DX spots)
- [ ] Automatic frequency logging (what's active, when)
- [ ] Band condition alerts (push notification when target band opens)
- [ ] Contest mode: highlight multipliers, track worked grids/zones

---

## v0.8.0 — Logging & QSO Management

**Goal**: Integrated logging without needing external software.

- [ ] QSO logger built into web GUI
- [ ] ADIF export/import
- [ ] Callsign lookup (QRZ.com / HamQTH API integration)
- [ ] Duplicate contact detection
- [ ] Grid square / distance calculation
- [ ] LOTW (Logbook of the World) upload
- [ ] eQSL integration
- [ ] Contest logging mode (serial numbers, exchange tracking)
- [ ] POTA/SOTA activation support

---

## v0.9.0 — APRS & Packet Radio

**Goal**: Position reporting and digital packet capabilities.

- [ ] APRS position beacon (via Direwolf bridge)
- [ ] APRS message send/receive
- [ ] APRS map display in web GUI
- [ ] Packet radio TNC (software TNC via Direwolf)
- [ ] Winlink email gateway integration
- [ ] APRS weather station reporting
- [ ] IS-gate functionality

---

## v1.0.0 — Production Release

**Goal**: Stable, feature-complete, documented, community-ready.

- [ ] Comprehensive documentation site
- [ ] Plugin architecture (extend via Python packages)
- [ ] Multi-radio support (not just FT-991A — extend to IC-7300, FT-891, etc.)
- [ ] User authentication for web GUI (optional, for remote access)
- [ ] TLS/HTTPS support
- [ ] Configuration persistence (save/restore radio profiles)
- [ ] Backup/restore radio memories via GUI
- [ ] Performance optimization (minimize CAT polling overhead)
- [ ] Accessibility (screen reader support, keyboard navigation)
- [ ] Internationalization (i18n)

---

## v1.x+ — Advanced / Experimental

### AI-Assisted Operation
- [ ] Natural language radio control ("tune to the 20 meter FT8 frequency")
- [ ] Automatic QSO detection and logging
- [ ] Voice-to-text for received SSB audio
- [ ] AI band recommendation ("20m is open to Europe right now")
- [ ] Automatic contest operation (AI handles exchanges)

### Emergency Communications
- [ ] Emergency beacon mode (automatic distress signaling)
- [ ] ARES/RACES integration (emergency net frequencies pre-programmed)
- [ ] Automatic position reporting in emergency mode
- [ ] Cross-band repeat capability
- [ ] Mesh networking (JS8Call relay)

### Satellite
- [ ] Satellite pass prediction (gpredict integration)
- [ ] Auto-Doppler correction during satellite passes
- [ ] ISS contact scheduling
- [ ] Satellite transponder tuning presets

### Hardware Extensions
- [ ] Antenna rotator control (via Hamlib rotctld)
- [ ] Antenna tuner integration (external auto-tuner support)
- [ ] SDR panadapter overlay (RTL-SDR waterfall display)
- [ ] Remote head operation (control radio from anywhere via web)
- [ ] Multi-operator support (shared radio, queue-based TX)

---

## Architecture Principles

1. **PyPI-first**: Always installable via `pip install ft991a-control`
2. **No heavy dependencies**: No React, no npm, no Electron. Python + vanilla JS
3. **Hardware-optional development**: All features testable with mocked serial
4. **MCP-native**: Every new feature gets an MCP tool alongside the web UI
5. **Hamlib-compatible**: Use rigctld for shared access, don't reinvent rig control
6. **Safety by default**: TX lockout on by default, deliberate PTT required
7. **Offline-capable**: Core functionality works without internet

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

File issues at: https://github.com/heliosarchitect/lbf-ham-radio/issues
