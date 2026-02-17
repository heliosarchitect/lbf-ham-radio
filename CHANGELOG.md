# Changelog

All notable changes to **ft991a-control** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

*Generated automatically by `scripts/generate-changelog.py`*

## [v0.7.0] - 2026-02-17

### ✨ Features

- **SDR Panadapter Waterfall** — Wideband spectrum display via SDRplay RSP2pro (SoapySDR)
  - New "SDR" tab in LCARS interface
  - Real-time FFT waterfall with heat map visualization
  - Click-to-tune: click anywhere on waterfall to set VFO-A frequency
  - Bandwidth selector: 500 kHz, 1 MHz, 2 MHz, 5 MHz, 10 MHz
  - FFT resolution: 256, 512, 1024, 2048 bins
  - 5 color palettes: RADIO, AMBER, BLUE, GREEN, GRAY
  - Frequency axis labels (MHz) across bandwidth
  - Radio frequency indicator (red line showing current VFO-A)
  - Automatic frequency tracking — SDR follows radio's VFO-A
  - Signal level meter with peak strength display
- **New API endpoints**: `/api/sdr/status`, `/api/sdr/bandwidth`, `/api/sdr/fft_size`
- **New WebSocket**: `/ws/sdr` for real-time IQ → FFT streaming (~10-15 fps)
- **SDRConnectionManager**: Graceful SoapySDR initialization with fallback

---

## [v0.6.1] - 2026-02-17

### 🐛 Bug Fixes

- **NaN frequency display**: `updateTunerStrip()` was called before WebSocket status arrived, causing `undefined / 1000000 = NaN`
- **Waterfall center frequency**: Was hardcoded to `14.074.000 MHz` instead of tracking actual VFO-A frequency
- **Tuner step selector**: `setTunerStep()` used implicit `event` variable — now passes `this` from onclick
- **`radioStatus` guard**: All tuner functions now check for valid status before accessing `frequency_a`

### ✨ Features

- **Antenna Auto-Tune button**: Gold ⚡ AUTO TUNE button on both Audio and VFO tabs
  - Sends CAT `AC001;` (tuner ON) + `AC002;` (start tune)
  - Visual feedback: turns red "TUNING..." for 8 seconds
  - FT-991A AC command is write-only (no status query available)
- **Console logging**: `tuneUp`/`tuneDown` now log frequency changes to browser console for debugging
- **CI/CD**: GitHub Actions → PyPI publish on `v*` tag push

### 🛠️ Maintenance

- Version bump: `__init__.py` synced to 0.6.1
- Both Gitea and GitHub remotes synced

---

## [v0.6.0] - 2026-02-16

### ✨ Features

- **CW Module**: Complete CW (Morse code) implementation with encoding, decoding, and keying
- **CW Encoding**: Text to Morse code conversion with full ITU alphabet, numbers, punctuation, and prosigns
- **CW Decoding**: Morse code to text conversion with robust spacing handling
- **CW Keyer**: Precise timing-based CW transmission via FT-991A TX commands (5-40 WPM)
- **CW Decoder**: Placeholder for future audio decoding with Goertzel algorithm stub
- **CLI Commands**: 
  - `ft991a-cli cw encode` - Convert text to Morse code
  - `ft991a-cli cw decode` - Convert Morse code to text  
  - `ft991a-cli cw send` - Key CW via radio (requires --confirm flag and license)
  - `ft991a-cli cw listen` - Placeholder for CW decoder
- **Safety Features**: TX commands require --confirm flag and display license warnings
- **Comprehensive Testing**: Full test suite with 39/42 tests passing, including round-trip validation

### 🔧 Technical

- Precise CW timing: dit = 1200/WPM ms, proper element/letter/word gaps
- Emergency stop functionality for keying safety
- Support for prosigns: <SK>, <KA>, <SN>
- Robust error handling and logging

---

## [v0.3.3] - 2026-02-16

### ✨ Features

- add Traefik reverse proxy config for HTTPS [`687c9617`]

### 🛠️ Maintenance

- bump v0.3.3 — Traefik HTTPS config [`3c60e91f`]

---

## [v0.3.2] - 2026-02-16

### ✨ Features

- add Traefik reverse proxy config for HTTPS [`687c9617`]

### 🛠️ Maintenance

- bump v0.3.3 — Traefik HTTPS config [`3c60e91f`]

---

## [v0.3.1] - 2026-02-16

### 📚 Documentation

- version-forensics roadmap — 7 feature increments to v1.0.0 [`ffdbb2cc`]
- add feature roadmap v0.4 through v1.0+ [`1977837e`]

### 🛠️ Maintenance

- bump v0.3.2 — roadmap revision (added broadcast feature, renumbered milestones) [`cc714c36`]
- bump to v0.3.1 [`d03fdb4b`]

---

## [v0.3.0] - 2026-02-16

### 🔄 CI/CD

- add GitHub Actions + Gitea CI/CD, fix tests to match actual API [`70778f44`]

### 📝 Miscellaneous

- 📝 Update README: Note test API signature mismatch [`c4a3d0b6`]

---

## [v0.2.0] - 2026-02-16

### 📝 Miscellaneous

- 🏗️ Major restructure: PyPI package + MCP server (v0.3.0) [`1c736d03`]

---

## [v0.1.0] - 2026-02-16

### ✨ Features

- Complete FT-991A web GUI with real-time control [`cecc735b`]

---

## [v0.0.0] - 2026-02-16

### ✨ Features

- FT-991A CAT control library v0.1.0 [`0e071bd2`]

---

## Links

- 📖 [Repository](https://github.com/heliosarchitect/lbf-ham-radio)
- 🐛 [Issues](https://github.com/heliosarchitect/lbf-ham-radio/issues)
- 🚀 [Releases](https://github.com/heliosarchitect/lbf-ham-radio/releases)

---

*Generated with ❤️ by the changelog automation system*
