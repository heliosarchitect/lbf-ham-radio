# Changelog

All notable changes to **ft991a-control** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

*Generated automatically by `scripts/generate-changelog.py`*

## [v0.25.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Deterministic Fingerprint (Feature 17/20)**
  - Added fingerprint model + builder + formatter (`HotspotWindowFingerprint`, `BandScanner.build_hotspot_window_fingerprint`, `BandScanner.format_hotspot_window_fingerprint`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-fingerprint`
  - RX/analysis only; no TX behavior changes.

### ✅ Tests

- Added scanner test for deterministic fingerprint generation + formatter output.

## [v0.24.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Machine Snapshot (Feature 16/20)**
  - Added machine-friendly snapshot model + builder from existing handoff packet state (`HotspotWindowSnapshot`, `BandScanner.build_hotspot_window_snapshot`)
  - Added one-line key=value formatter for logging/automation glue (`BandScanner.format_hotspot_window_snapshot`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-snapshot [--action-ready-ms MS] [--action-critical-ms MS] [--upcoming-count N]`
  - Composes with existing Feature 1..15 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief/cue/action/decision/ops/directive/handoff flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 16 source details were not explicitly documented in repo planning files; implemented conservatively as a machine-readable summary layer over Feature 15 handoff output.

### ✅ Tests

- Added scanner tests for snapshot composition and formatter output.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.24.0`.

## [v0.23.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Shift Handoff Packet (Feature 15/20)**
  - Added shift-handoff packet model + builder for operator transitions (`HotspotWindowHandoff`, `BandScanner.build_hotspot_window_handoff`)
  - Added compact handoff formatter with headline, immediate steps, and queued steps (`BandScanner.format_hotspot_window_handoff`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-handoff [--action-ready-ms MS] [--action-critical-ms MS] [--upcoming-count N]`
  - Composes with existing Feature 1/2/3/4/5/6/7/8/9/10/11/12/13/14 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief/cue/action/decision/ops/directive flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 15 source details were not explicitly documented in repo planning files; implemented conservatively as an operator shift-handoff layer over existing ops/directive state.

### ✅ Tests

- Added scanner tests for handoff packet composition and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.23.0`.

## [v0.22.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Actionable Directive Checklist (Feature 14/20)**
  - Added directive model + builder that distills existing ops-card state into immediate execution guidance (`HotspotWindowDirective`, `BandScanner.build_hotspot_window_directive`)
  - Added concise directive formatter with checklist output for manual RX handoff loops (`BandScanner.format_hotspot_window_directive`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-directive [--action-ready-ms MS] [--action-critical-ms MS] [--upcoming-count N]`
  - Composes with existing Feature 1/2/3/4/5/6/7/8/9/10/11/12/13 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief/cue/action/decision/ops flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 14 source details were not explicitly documented in repo planning files; implemented conservatively as an actionable checklist layer over existing ops-card output.

### ✅ Tests

- Added scanner tests for directive composition and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.22.0`.

## [v0.21.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Ops Card (Feature 13/20)**
  - Added compact ops-card model + builder combining decision urgency with near-term handoff queue (`HotspotWindowOps`, `BandScanner.build_hotspot_window_ops`)
  - Added compact multi-line terminal formatter for low-overhead manual RX loop execution (`BandScanner.format_hotspot_window_ops`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-ops [--action-ready-ms MS] [--action-critical-ms MS] [--upcoming-count N]`
  - Composes with existing Feature 1/2/3/4/5/6/7/8/9/10/11/12 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief/cue/action/decision flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 13 source details were not explicitly documented in repo planning files; implemented conservatively as a compact synthesis layer over existing decision + upcoming outputs.

### ✅ Tests

- Added scanner tests for ops-card composition and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.21.0`.

## [v0.20.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Escalation Decision Signal (Feature 12/20)**
  - Added urgency-aware decision model + builder with LOW/MEDIUM/HIGH/CRITICAL escalation (`HotspotWindowDecision`, `BandScanner.build_hotspot_window_decision`)
  - Added one-line terminal decision formatter including recheck cadence (`BandScanner.format_hotspot_window_decision`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-decision [--action-ready-ms MS] [--action-critical-ms MS]`
  - Composes with existing Feature 1/2/3/4/5/6/7/8/9/10/11 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief/cue/action flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 12 source details were not explicitly documented in repo planning files; implemented conservatively as an urgency overlay on existing action timing.

### ✅ Tests

- Added scanner tests for decision urgency classification tiers and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.20.0`.

## [v0.19.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Live Action Signal (Feature 11/20)**
  - Added live handoff action model + builder with HOLD/READY/SWITCH states (`HotspotWindowAction`, `BandScanner.build_hotspot_window_action`)
  - Added one-line terminal action formatter for low-latency operator timing cues (`BandScanner.format_hotspot_window_action`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-action [--action-ready-ms MS]`
  - Composes with existing Feature 1/2/3/4/5/6/7/8/9/10 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief/cue flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 11 source details were not explicitly documented in repo planning files; implemented conservatively as a timing-state overlay on existing cue data.

### ✅ Tests

- Added scanner tests for action-state classification (HOLD/READY/SWITCH) and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.19.0`.

## [v0.18.0] - 2026-03-01

### ✨ Features

- **Hotspot Window One-Line Live Cue (Feature 10/20)**
  - Added single-line operator cue model + builder from wall-clock schedule state (`HotspotWindowCue`, `BandScanner.build_hotspot_window_cue`)
  - Added compact terminal cue formatter for active→next handoff glance checks (`BandScanner.format_hotspot_window_cue`)
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-cue`
  - Composes with existing Feature 1/2/3/4/5/6/7/8/9 heatmap → hotspot → window → plan → timeline → clock → now/upcoming/brief flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 10 source details were not explicitly documented in repo planning files; implemented conservatively as a low-overhead handoff cue layer over existing now-state scheduling.

### ✅ Tests

- Added scanner tests for cue composition and concise formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.18.0`.

## [v0.17.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Compact Live Brief (Feature 9/20)**
  - Added compact live brief composer for active + next + queued handoff context (`BandScanner.build_hotspot_window_brief`)
  - Added compact terminal brief formatter for fast operator review (`BandScanner.format_hotspot_window_brief`)
  - Added `HotspotWindowBrief` model for explicit scanner-layer summary handoff metadata
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-brief [--upcoming-count N]`
  - Composes with existing Feature 1/2/3/4/5/6/7/8 heatmap → hotspot → window → plan → timeline → clock → now/upcoming flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only
  - **Assumption note:** Feature 9 source details were not explicitly documented in repo planning files; implemented conservatively as a compact synthesis layer over existing now/upcoming outputs to preserve interface continuity.

### ✅ Tests

- Added scanner tests for compact brief composition and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.17.0`.

## [v0.16.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Upcoming Handoff Projection (Feature 8/20)**
  - Added upcoming handoff resolver for wall-clock hotspot schedules (`BandScanner.build_hotspot_window_upcoming`)
  - Added upcoming handoff terminal formatter for near-term operator sequencing (`BandScanner.format_hotspot_window_upcoming`)
  - Added `HotspotWindowUpcomingStep` model for explicit sequence/ETA/cycle metadata
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-upcoming [--upcoming-count N]`
  - Composes with existing Feature 1/2/3/4/5/6/7 heatmap → hotspot → window → plan → timeline → clock → now flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for upcoming handoff projection ordering/cycle wrap and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.16.0`.

## [v0.15.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Live Now-State Advisory (Feature 7/20)**
  - Added schedule-position resolver for wall-clock hotspot plans (`BandScanner.get_hotspot_window_now`)
  - Added active/next terminal formatter for live operator guidance (`BandScanner.format_hotspot_window_now`)
  - Added `HotspotWindowNowState` model for explicit active-step and upcoming-step metadata
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-now`
  - Composes with existing Feature 1/2/3/4/5/6 heatmap → hotspot → window → plan → timeline → clock flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for now-state resolution, cycle wrap handling, and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.15.0`.

## [v0.14.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Clock Sync Projection (Feature 6/20)**
  - Added wall-clock projection from timeline steps (`BandScanner.build_hotspot_window_clock`)
  - Added wall-clock terminal formatter (`BandScanner.format_hotspot_window_clock`)
  - Added `HotspotWindowClockStep` model for explicit absolute-time schedule boundaries
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-clock`
  - Composes with existing Feature 1/2/3/4/5 heatmap → hotspot → window → plan → timeline flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for clock projection anchoring and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.14.0`.

## [v0.13.0] - 2026-03-01

### ✨ Features

- **Hotspot Window Timeline Projection (Feature 5/20)**
  - Added timeline projection from ranked hotspot review plans (`BandScanner.build_hotspot_window_timeline`)
  - Added timeline terminal formatter with start/end/revisit offsets (`BandScanner.format_hotspot_window_timeline`)
  - Added `HotspotWindowTimelineStep` model for explicit cycle schedule boundaries
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-timeline`
  - Composes with existing Feature 1/2/3/4 heatmap → hotspot → window → plan flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for timeline offset projection and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.13.0`.

## [v0.12.0] - 2026-03-01

### ✨ Features

- **Ranked Hotspot Window Review Plan (Feature 4/20)**
  - Added ranked RX review plan builder from merged hotspot windows (`BandScanner.build_hotspot_window_plan`)
  - Added review plan terminal formatter (`BandScanner.format_hotspot_window_plan`)
  - Added `HotspotWindowPlanStep` data model for explicit scanner-layer review sequencing
  - Exposed only through existing CLI surface: `ft991a-cli scan band --window-plan [--plan-cycle-ms MS]`
  - Composes with existing Feature 1/2/3 heatmap → hotspot → window flow
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for hotspot window plan ranking/dwell allocation and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.12.0`.

## [v0.11.0] - 2026-03-01

### ✨ Features

- **Adaptive Hotspot Window Merging (Feature 3/20)**
  - Added hotspot window merger from ranked adaptive bins (`BandScanner.merge_hotspot_windows`)
  - Added hotspot window terminal formatter (`BandScanner.format_hotspot_windows`)
  - Added `HotspotWindow` data model for explicit scanner-layer output boundaries
  - Exposed only through existing CLI surface: `ft991a-cli scan band --hotspot-windows [--window-gap-hz HZ]`
  - Composes with existing Feature 1/2 heatmap + hotspot flow and remains RX/analysis only
  - No new top-level command groups, endpoints, or TX controls introduced

### ✅ Tests

- Added scanner tests for hotspot window merging and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.11.0`.

## [v0.10.0] - 2026-03-01

### ✨ Features

- **Adaptive Heatmap Hotspot Ranking (Feature 2/20)**
  - Added hotspot extraction from adaptive RX heatmap bins (`BandScanner.extract_heatmap_hotspots`)
  - Added hotspot terminal formatter (`BandScanner.format_heatmap_hotspots`)
  - Added `HeatmapHotspot` data model to keep scanner-layer boundaries explicit
  - Exposed only through existing CLI surface: `ft991a-cli scan band --hotspots [--hotspot-threshold S] [--hotspot-top N]`
  - Option composes with existing Feature 1 heatmap controls and reuses same scan data path
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for hotspot extraction ranking/filtering and formatter rendering.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.10.0`.

## [v0.9.0] - 2026-03-01

### ✨ Features

- **Adaptive Band Activity Heatmap (Feature 1/20)**
  - Added adaptive heatmap generation for RX band scans (`BandScanner.build_adaptive_heatmap`)
  - Added terminal heatmap renderer (`BandScanner.format_adaptive_heatmap`)
  - Added `HeatmapBin` data model to preserve scanner module boundaries
  - Exposed only through existing CLI surface: `ft991a-cli scan band --heatmap [--max-bins N]`
  - No new top-level command groups, endpoints, or TX controls introduced
  - RX/analysis only

### ✅ Tests

- Added scanner tests for adaptive heatmap binning and formatter output.

### 🛠️ Versioning

- **Semver reason:** new operator-visible feature added via existing interface contract → **minor bump** to `0.9.0`.

## [v0.8.0] - 2026-02-17 (planned)

### ✨ Features

- **Channel Monitor Tab** — Live radio monitoring with AI transcription & translation
  - New "Monitor" tab in LCARS interface
  - Real-time transcript feed: Spanish (original) + English translation side by side
  - Callsign detection and highlighting (KP4, WP4, W, K, N prefixes)
  - Start/Stop monitoring controls
  - Configurable: clip duration, capture interval, language, S-meter threshold
  - WebSocket push for live transcript updates (`/ws/monitor`)
  - JSONL transcript logging with export
  - Stats panel: total clips, callsigns found, monitoring duration
- **New API endpoints**: `/api/monitor/start`, `/api/monitor/stop`, `/api/monitor/status`, `/api/monitor/transcripts`, `/api/monitor/transcripts/export`
- **Backend**: Python asyncio monitor (Whisper API + gpt-4o-mini translation)
- **Standalone script**: `scripts/radio-monitor.sh` for headless monitoring

## [v0.7.2] - 2026-02-17

### 🐛 Bug Fixes

- **Waterfall scroll race**: Audio waterfall was scrolling on every animation frame (~60fps) regardless of new FFT data. Now only scrolls when new data arrives.

### ✨ Features

- **Radio monitor script**: `scripts/radio-monitor.sh` — standalone capture/transcribe/translate pipeline using Whisper API + gpt-4o-mini. JSONL logging, S-meter gating, callsign extraction, hallucination filtering.

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
