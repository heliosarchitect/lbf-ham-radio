# FT-991A Control — Feature Roadmap

> `pip install ft991a-control` | PyPI: [ft991a-control](https://pypi.org/project/ft991a-control/)
> GitHub: [heliosarchitect/lbf-ham-radio](https://github.com/heliosarchitect/lbf-ham-radio)

**Version plan**: v0.3.1 → v1.0.0 = **7 minor version increments** (7 feature milestones)

---

## v0.3.x — Foundation (✅ COMPLETE)

- [x] CAT control library (full FT-991A command set)
- [x] FastAPI web GUI with WebSocket real-time updates
- [x] MCP server (14 tools) for AI integration
- [x] CLI entry points (`ft991a-web`, `ft991a-cli`, `ft991a-mcp`)
- [x] PyPI package published
- [x] CI/CD (GitHub Actions + Gitea, auto-publish on tag)
- [x] Unit tests (15 passing, mocked serial)
- [x] Research doc (existing Linux ham software ecosystem)
- [x] Traefik reverse proxy config for HTTPS (v0.3.3)

---

## v0.4.0 — Hardware Validation & Audio (✅ COMPLETE — shipped in v0.6.x)

**Goal**: Verified working on real hardware, audio routing functional.

- [x] Audio level meters in web GUI — FFT waterfall visualization (v0.6.0)
- [x] Audio recording/playback — monitor received audio from browser (v0.6.0)
- [x] S-meter history chart with real-time display (v0.6.0)
- [x] Antenna auto-tune button (ATU control via CAT) (v0.6.1)
- [x] Mobile navigation bar for tab access (v0.6.0)
- [x] First-time setup wizard for guided radio configuration (v0.6.0)
- [x] Precision fine-tuning controls in LCARS GUI (v0.6.0)
- [ ] Integration tests with live FT-991A hardware (deferred — requires physical access)
- [ ] USB device auto-detection (`/dev/ttyUSB0`, `/dev/ttyUSB1`, USB CODEC AUDIO)
- [ ] PulseAudio/PipeWire audio routing for USB sound card
- [ ] Squelch status indicator
- [ ] Connection auto-reconnect on USB disconnect/reconnect
- [ ] Fix any CAT command timing issues discovered on real hardware
- [ ] Systemd service validated and documented

---

## v0.5.0 — Digital Modes Integration (⚠️ SCAFFOLDED — `digital.py` exists, 511 lines)

**Goal**: First-class FT8/FT4 and digital mode support.

- [x] Digital modes module with `DigitalModes` class (v0.6.0)
- [ ] WSJT-X integration (auto-configure CAT + audio routing)
- [ ] fldigi integration (launch, configure, monitor)
- [ ] Hamlib `rigctld` wrapper (shared CAT access for multiple programs)
- [ ] FT8 decode display in web GUI (via WSJT-X UDP stream)
- [ ] Digital mode quick-switch buttons (FT8 @ 14.074, FT4 @ 14.080, etc.)
- [ ] Auto-set radio to correct mode/frequency for digital operation
- [ ] WSJT-X log parsing → contact display in GUI

---

## v0.6.0 — CW / Morse Code (✅ COMPLETE)

**Goal**: Full CW operation from the web GUI + AI-assisted decode.

- [x] CW encoder (text → Morse code, full ITU alphabet + numbers + punctuation + prosigns) (v0.6.0)
- [x] CW decoder (Morse code → text, robust spacing handling) (v0.6.0)
- [x] CW keyer (precise timing via CAT TX commands, 5-40 WPM) (v0.6.0)
- [x] CLI: `ft991a-cli cw encode/decode/send/listen` (v0.6.0)
- [x] Speed control (WPM parameter) (v0.6.0)
- [x] Safety: TX requires `--confirm` flag + license warning (v0.6.0)
- [x] Emergency stop for keying (v0.6.0)
- [x] Prosigns support: `<SK>`, `<KA>`, `<SN>` (v0.6.0)
- [x] 39 tests passing including round-trip validation (v0.6.0)
- [ ] CW keyboard mode in web GUI (type text, radio sends morse)
- [ ] CW practice/training mode (generate random callsigns, copy practice)
- [ ] Decode waterfall display
- [ ] AI-assisted CW: auto-respond to CQ calls with proper QSO format

---

## v0.7.0 — Band Monitoring & Intelligence (✅ MOSTLY COMPLETE)

**Goal**: AI-powered band awareness and signal detection.

- [x] SDR panadapter waterfall via SDRplay RSP2pro + SoapySDR (v0.7.0)
- [x] Click-to-tune: click waterfall to set VFO-A (v0.7.0)
- [x] Bandwidth selector: 500 kHz–10 MHz (v0.7.0)
- [x] FFT resolution: 256–2048 bins (v0.7.0)
- [x] 5 color palettes (RADIO, AMBER, BLUE, GREEN, GRAY) (v0.7.0)
- [x] Frequency axis labels + radio frequency indicator (v0.7.0)
- [x] Automatic frequency tracking — SDR follows VFO-A (v0.7.0)
- [x] Signal level meter with peak strength display (v0.7.0)
- [x] Scanner module (`scanner.py`, 332 lines) (v0.7.0)
- [ ] Propagation overlay (integrate solar/HF prediction data)
- [ ] DX cluster feed integration (live DX spots)
- [ ] Band condition alerts (push notification when target band opens)
- [ ] Contest mode: highlight multipliers, track worked grids/zones

---

## v0.8.0 — AI-Assisted Monitoring & Broadcast (✅ PARTIALLY COMPLETE)

**Goal**: Draft → review → transmit workflow for newsletters and alerts.

- [x] Channel monitor tab — live AI transcription + translation (v0.8.0)
- [x] Whisper API + gpt-4o-mini for Spanish→English translation (v0.8.0)
- [x] Callsign detection (KP4, WP4, W, K, N prefixes) (v0.8.0)
- [x] JSONL transcript logging with export (v0.8.0)
- [x] Standalone monitoring script: `scripts/radio-monitor.sh` (v0.7.2)
- [x] Broadcast module (`broadcast.py`, 426 lines) (v0.8.0)
- [x] Dynamic version display in GUI (v0.8.1)
- [ ] TX queue in web GUI (queued messages awaiting operator PTT)
- [ ] Text-to-speech synthesis for voice broadcasts (TTS → audio → TX)
- [ ] CW bulletin formatting (auto-format text as CW-ready)
- [ ] Digital mode message formatting (JS8Call, Winlink)
- [ ] Simultaneous web audio stream (stream TX audio to web listeners)
- [ ] WebSDR/KiwiSDR integration links for remote verification
- [ ] Broadcast templates (emergency alert, weather, news, net check-in)
- [ ] Broadcast log (what was sent, when, on what frequency/mode)
- [ ] Sub-10-minute draft-to-air pipeline

---

## v0.9.0 — QSO Logging & Contact Management

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

## v0.10.0 — APRS, Packet Radio & Emergency Comms (⚠️ SCAFFOLDED — `aprs.py` exists, 522 lines)

**Goal**: Position reporting, packet capabilities, and ARES/RACES readiness.

- [x] APRS module with `APRSPacketType` enum and packet handling (scaffolded, v0.8.0)
- [ ] APRS position beacon (via Direwolf bridge)
- [ ] APRS message send/receive
- [ ] APRS map display in web GUI
- [ ] Packet radio TNC (software TNC via Direwolf)
- [ ] Winlink email gateway integration
- [ ] ARES/RACES net frequencies pre-programmed
- [ ] Emergency beacon mode
- [ ] Cross-band repeat capability
- [ ] Mesh networking (JS8Call relay)

---

## v1.0.0 — Production Release

**Goal**: Stable, feature-complete, documented, community-ready.

- [ ] Comprehensive documentation site
- [ ] Plugin architecture (extend via Python packages)
- [ ] Multi-radio support (IC-7300, FT-891, etc. via Hamlib)
- [ ] User authentication for web GUI (optional, for remote access)
- [ ] TLS/HTTPS support
- [ ] Configuration persistence (save/restore radio profiles)
- [ ] Backup/restore radio memories via GUI
- [ ] Performance optimization (minimize CAT polling overhead)
- [ ] Accessibility (screen reader support, keyboard navigation)

---

## v1.x+ — Advanced / Experimental

### AI-Assisted Operation
- [ ] Natural language radio control ("tune to the 20 meter FT8 frequency")
- [ ] Automatic QSO detection and logging
- [ ] Voice-to-text for received SSB audio
- [ ] AI band recommendation ("20m is open to Europe right now")
- [ ] Automatic contest operation (AI handles exchanges)

### Satellite
- [ ] Satellite pass prediction (gpredict integration)
- [ ] Auto-Doppler correction during satellite passes
- [ ] ISS contact scheduling
- [ ] Satellite transponder tuning presets

### Hardware Extensions
- [ ] Antenna rotator control (via Hamlib rotctld)
- [ ] SDR panadapter overlay (RTL-SDR waterfall display)
- [ ] Remote head operation (control radio from anywhere via web)
- [ ] Multi-operator support (shared radio, queue-based TX)

---

## Version Summary

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.3.x | Foundation | ✅ Complete |
| v0.4.0 | Hardware validation + audio | ✅ Complete (shipped in v0.6.x) |
| v0.5.0 | Digital modes (FT8, fldigi) | ⚠️ Scaffolded |
| v0.6.0 | CW / Morse code | ✅ Complete |
| v0.7.0 | Band monitoring & intelligence | ✅ Mostly complete |
| v0.8.0 | AI broadcast & TX queue | ✅ Partially complete |
| v0.9.0 | QSO logging | ❌ Not started |
| v0.10.0 | APRS + emergency comms | ⚠️ Scaffolded |
| **v1.0.0** | **Production release** | 🔶 TLS done, rest pending |

**Current release: v0.8.1** — actual feature coverage spans v0.3–v0.8 roadmap milestones.
**Next milestone: v0.4.0 hardware validation** (deferred items requiring physical radio access on radio.fleet.wood)

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
