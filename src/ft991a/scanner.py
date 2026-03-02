#!/usr/bin/env python3
"""
FT-991A Band Scanner Module
===========================
Band scanning functionality for signal monitoring and frequency sweeping.

Features:
- scan_band(): Sweep frequency ranges with S-meter readings
- find_activity(): Detect active frequencies above threshold
- fine_scan(): Detailed scanning around specific frequencies
- scan_all_hf(): Complete HF band sweep (160m-10m)
- ASCII bar chart visualization for terminal display

Usage:
    scanner = BandScanner(radio)
    results = scanner.scan_band(14_000_000, 14_350_000, 5000)
    active = scanner.find_activity(threshold=50)
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from statistics import mean
from typing import List, Optional, Tuple

from .cat import FT991A, Mode

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Single frequency scan result"""

    frequency_hz: int
    s_meter: int
    timestamp: float


@dataclass
class ActivityResult:
    """Active frequency detection result"""

    frequency_hz: int
    s_meter: int
    frequency_mhz: float
    s_level_text: str


@dataclass
class HeatmapBin:
    """Adaptive activity heatmap bin for a frequency range."""

    start_hz: int
    end_hz: int
    center_hz: int
    avg_s_meter: float
    peak_s_meter: int
    sample_count: int
    activity_score: float


@dataclass
class HeatmapHotspot:
    """Top candidate hotspot derived from adaptive heatmap bins."""

    start_hz: int
    end_hz: int
    center_hz: int
    avg_s_meter: float
    peak_s_meter: int
    sample_count: int
    activity_score: float


@dataclass
class HotspotWindow:
    """Merged hotspot window formed from adjacent hotspot bins."""

    start_hz: int
    end_hz: int
    center_hz: int
    peak_s_meter: int
    avg_score: float
    hotspot_count: int


@dataclass
class HotspotWindowPlanStep:
    """Operator review plan step derived from merged hotspot windows."""

    rank: int
    center_hz: int
    start_hz: int
    end_hz: int
    dwell_ms: int
    priority_score: float
    hotspot_count: int


@dataclass
class HotspotWindowTimelineStep:
    """Timeline projection for one window-plan step within a review cycle."""

    rank: int
    center_hz: int
    dwell_ms: int
    start_offset_ms: int
    end_offset_ms: int
    revisit_after_ms: int


@dataclass
class HotspotWindowClockStep:
    """Wall-clock projection for timeline steps anchored to a cycle start."""

    rank: int
    center_hz: int
    dwell_ms: int
    start_epoch_ms: int
    end_epoch_ms: int
    revisit_epoch_ms: int


@dataclass
class HotspotWindowNowState:
    """Current/next step advisory from a hotspot wall-clock schedule."""

    now_epoch_ms: int
    cycle_ms: int
    cycle_offset_ms: int
    active_rank: int
    active_center_hz: int
    active_start_epoch_ms: int
    active_end_epoch_ms: int
    ms_until_switch: int
    next_rank: int
    next_center_hz: int
    next_start_epoch_ms: int


@dataclass
class HotspotWindowUpcomingStep:
    """Upcoming schedule handoff derived from wall-clock hotspot windows."""

    sequence: int
    rank: int
    center_hz: int
    starts_in_ms: int
    start_epoch_ms: int
    end_epoch_ms: int
    dwell_ms: int
    cycle_index: int


@dataclass
class HotspotWindowBrief:
    """Compact operator handoff brief from now-state + upcoming schedule."""

    generated_epoch_ms: int
    cycle_ms: int
    active_rank: int
    active_center_hz: int
    ms_until_switch: int
    next_rank: int
    next_center_hz: int
    upcoming: List[HotspotWindowUpcomingStep]


@dataclass
class HotspotWindowCue:
    """Single-line operator cue derived from compact hotspot brief state."""

    generated_epoch_ms: int
    active_rank: int
    active_center_hz: int
    next_rank: int
    next_center_hz: int
    ms_until_switch: int


@dataclass
class HotspotWindowAction:
    """Operator action tag derived from cue countdown for faster handoff timing."""

    generated_epoch_ms: int
    active_rank: int
    active_center_hz: int
    next_rank: int
    next_center_hz: int
    ms_until_switch: int
    action: str
    action_reason: str


@dataclass
class HotspotWindowDecision:
    """Escalated operator decision payload derived from action countdown state."""

    generated_epoch_ms: int
    active_rank: int
    active_center_hz: int
    next_rank: int
    next_center_hz: int
    ms_until_switch: int
    action: str
    urgency: str
    recommended_check_ms: int
    decision_reason: str


@dataclass
class HotspotWindowOps:
    """Operator ops-card payload combining decision and near-term handoff queue."""

    generated_epoch_ms: int
    action: str
    urgency: str
    recommended_check_ms: int
    active_rank: int
    active_center_hz: int
    next_rank: int
    next_center_hz: int
    ms_until_switch: int
    upcoming: List[HotspotWindowUpcomingStep]


@dataclass
class HotspotWindowDirective:
    """Execution directive distilled from ops state for immediate RX handoff action."""

    generated_epoch_ms: int
    summary: str
    action: str
    urgency: str
    recheck_ms: int
    checklist: List[str]


class BandScanner:
    """
    Band scanning capability for FT-991A.

    Provides frequency sweeping with S-meter readings, activity detection,
    and terminal-friendly result formatting.

    Usage:
        scanner = BandScanner(radio)

        # Basic band scan
        results = scanner.scan_band(14_000_000, 14_350_000, 5000)

        # Find active frequencies
        active = scanner.find_activity(threshold=50)

        # Fine scan around frequency
        detail = scanner.fine_scan(14_249_000, width_hz=20000)

        # Full HF sweep
        hf_activity = scanner.scan_all_hf()
    """

    # HF amateur band voice segments (Hz)
    HF_VOICE_BANDS = [
        (1_800_000, 2_000_000),  # 160m
        (3_500_000, 4_000_000),  # 80m
        (5_330_000, 5_404_000),  # 60m
        (7_000_000, 7_300_000),  # 40m
        (10_100_000, 10_150_000),  # 30m
        (14_000_000, 14_350_000),  # 20m
        (18_068_000, 18_168_000),  # 17m
        (21_000_000, 21_450_000),  # 15m
        (24_890_000, 24_990_000),  # 12m
        (28_000_000, 29_700_000),  # 10m
    ]

    def __init__(self, radio: FT991A):
        """Initialize scanner with radio instance."""
        self.radio = radio
        self._original_frequency = None
        self._original_mode = None

    def _save_radio_state(self):
        """Save current radio state for restoration."""
        self._original_frequency = self.radio.get_frequency_a()
        self._original_mode = self.radio.get_mode()
        logger.debug(
            f"Saved radio state: {self._original_frequency} Hz, {self._original_mode}"
        )

    def _restore_radio_state(self):
        """Restore saved radio state."""
        if self._original_frequency:
            self.radio.set_frequency_a(self._original_frequency)
        if self._original_mode:
            # Convert mode string back to Mode enum
            for mode in Mode:
                if mode.name == self._original_mode:
                    self.radio.set_mode(mode)
                    break
        logger.debug(
            f"Restored radio state: {self._original_frequency} Hz, {self._original_mode}"
        )

    def scan_band(
        self, start_hz: int, end_hz: int, step_hz: int, dwell_ms: int = 150
    ) -> List[Tuple[int, int]]:
        """
        Scan a frequency band and return S-meter readings.

        Args:
            start_hz: Starting frequency in Hz
            end_hz: Ending frequency in Hz
            step_hz: Step size in Hz
            dwell_ms: Dwell time per frequency in milliseconds

        Returns:
            List of (frequency_hz, s_meter) tuples
        """
        logger.info(
            f"Scanning {start_hz:,} - {end_hz:,} Hz (step: {step_hz:,} Hz, dwell: {dwell_ms}ms)"
        )

        self._save_radio_state()
        results = []
        dwell_sec = dwell_ms / 1000.0

        try:
            current_freq = start_hz
            while current_freq <= end_hz:
                # Tune to frequency
                self.radio.set_frequency_a(current_freq)

                # Wait for settling
                time.sleep(dwell_sec)

                # Read S-meter
                s_meter = self.radio.get_s_meter()
                results.append((current_freq, s_meter))

                logger.debug(f"{current_freq:,} Hz: S{self._s_meter_to_units(s_meter)}")

                current_freq += step_hz

        except KeyboardInterrupt:
            logger.info("Scan interrupted by user")
        except Exception as e:
            logger.error(f"Scan error: {e}")
        finally:
            self._restore_radio_state()

        logger.info(f"Scan complete: {len(results)} frequencies")
        return results

    def find_activity(self, threshold: int = 50) -> List[ActivityResult]:
        """
        Find active frequencies above S-meter threshold.

        Performs a quick scan of common amateur bands and returns
        frequencies with activity above the specified threshold.

        Args:
            threshold: S-meter threshold (0-255)

        Returns:
            List of ActivityResult objects with active frequencies
        """
        logger.info(
            f"Searching for activity above S{self._s_meter_to_units(threshold)} threshold"
        )

        active_frequencies = []

        for start_hz, end_hz in self.HF_VOICE_BANDS:
            # Quick scan with larger steps for activity detection
            step_hz = min(25000, (end_hz - start_hz) // 20)  # 20 points per band max

            scan_results = self.scan_band(start_hz, end_hz, step_hz, dwell_ms=100)

            for freq_hz, s_meter in scan_results:
                if s_meter >= threshold:
                    result = ActivityResult(
                        frequency_hz=freq_hz,
                        s_meter=s_meter,
                        frequency_mhz=freq_hz / 1e6,
                        s_level_text=f"S{self._s_meter_to_units(s_meter)}",
                    )
                    active_frequencies.append(result)

        # Sort by frequency
        active_frequencies.sort(key=lambda x: x.frequency_hz)

        logger.info(f"Found {len(active_frequencies)} active frequencies")
        return active_frequencies

    def fine_scan(
        self, center_hz: int, width_hz: int = 20000, step_hz: int = 1000
    ) -> List[Tuple[int, int]]:
        """
        Perform detailed scan around a specific frequency.

        Args:
            center_hz: Center frequency in Hz
            width_hz: Scan width in Hz (±width_hz/2 around center)
            step_hz: Step size in Hz

        Returns:
            List of (frequency_hz, s_meter) tuples
        """
        half_width = width_hz // 2
        start_hz = center_hz - half_width
        end_hz = center_hz + half_width

        logger.info(
            f"Fine scanning around {center_hz/1e6:.3f} MHz (±{width_hz/1000:.0f} kHz)"
        )

        return self.scan_band(start_hz, end_hz, step_hz, dwell_ms=200)

    def scan_all_hf(self) -> List[ActivityResult]:
        """
        Scan all amateur HF bands for activity.

        Performs a comprehensive sweep of 160m through 10m voice segments.

        Returns:
            List of ActivityResult objects for all detected signals
        """
        logger.info("Starting full HF band sweep (160m-10m)")

        all_activity = []

        for i, (start_hz, end_hz) in enumerate(self.HF_VOICE_BANDS):
            band_name = [
                "160m",
                "80m",
                "60m",
                "40m",
                "30m",
                "20m",
                "17m",
                "15m",
                "12m",
                "10m",
            ][i]
            logger.info(
                f"Scanning {band_name} band: {start_hz/1e6:.3f} - {end_hz/1e6:.3f} MHz"
            )

            # Medium step size for comprehensive coverage
            step_hz = 10000  # 10 kHz steps

            scan_results = self.scan_band(start_hz, end_hz, step_hz, dwell_ms=150)

            # Add all results above noise floor
            noise_threshold = 10  # Low threshold to catch weak signals
            for freq_hz, s_meter in scan_results:
                if s_meter >= noise_threshold:
                    result = ActivityResult(
                        frequency_hz=freq_hz,
                        s_meter=s_meter,
                        frequency_mhz=freq_hz / 1e6,
                        s_level_text=f"S{self._s_meter_to_units(s_meter)}",
                    )
                    all_activity.append(result)

        # Sort by frequency
        all_activity.sort(key=lambda x: x.frequency_hz)

        logger.info(f"HF sweep complete: {len(all_activity)} signals detected")
        return all_activity

    def build_adaptive_heatmap(
        self,
        results: List[Tuple[int, int]],
        bucket_hz: Optional[int] = None,
        max_bins: int = 48,
        min_bucket_hz: int = 2000,
    ) -> List[HeatmapBin]:
        """
        Build an adaptive activity heatmap from scan data.

        The bucket size is derived from scan span and constrained by max_bins,
        then normalized against the observed noise floor so the output adapts to
        changing band conditions.

        Args:
            results: List of (frequency_hz, s_meter) tuples from scan_band()
            bucket_hz: Optional fixed bucket size in Hz; adaptive if omitted
            max_bins: Maximum number of bins in adaptive mode
            min_bucket_hz: Lower bound for adaptive bucket sizing

        Returns:
            List of HeatmapBin entries sorted by frequency
        """
        if not results:
            return []

        ordered = sorted(results, key=lambda x: x[0])
        freqs = [freq for freq, _ in ordered]
        levels = [level for _, level in ordered]

        start_hz = freqs[0]
        end_hz = freqs[-1]
        span_hz = max(1, end_hz - start_hz)

        if bucket_hz is None:
            adaptive_size = ceil(span_hz / max(1, max_bins))
            bucket_hz = max(min_bucket_hz, adaptive_size)
        bucket_hz = max(1, bucket_hz)

        bucket_count = max(1, ceil((span_hz + 1) / bucket_hz))
        grouped: List[List[Tuple[int, int]]] = [[] for _ in range(bucket_count)]

        for freq_hz, s_meter in ordered:
            idx = min(bucket_count - 1, max(0, (freq_hz - start_hz) // bucket_hz))
            grouped[idx].append((freq_hz, s_meter))

        sorted_levels = sorted(levels)
        floor_idx = int(0.35 * (len(sorted_levels) - 1))
        noise_floor = sorted_levels[floor_idx]
        max_level = max(levels)
        dynamic_range = max(1.0, float(max_level - noise_floor))

        bins: List[HeatmapBin] = []
        for idx, bucket in enumerate(grouped):
            bucket_start = start_hz + idx * bucket_hz
            bucket_end = min(end_hz, bucket_start + bucket_hz - 1)

            if not bucket:
                bins.append(
                    HeatmapBin(
                        start_hz=bucket_start,
                        end_hz=bucket_end,
                        center_hz=(bucket_start + bucket_end) // 2,
                        avg_s_meter=0.0,
                        peak_s_meter=0,
                        sample_count=0,
                        activity_score=0.0,
                    )
                )
                continue

            bucket_levels = [s for _, s in bucket]
            avg_level = mean(bucket_levels)
            peak_level = max(bucket_levels)
            score = max(0.0, min(1.0, (avg_level - noise_floor) / dynamic_range))

            bins.append(
                HeatmapBin(
                    start_hz=bucket_start,
                    end_hz=bucket_end,
                    center_hz=(bucket_start + bucket_end) // 2,
                    avg_s_meter=avg_level,
                    peak_s_meter=peak_level,
                    sample_count=len(bucket),
                    activity_score=score,
                )
            )

        return bins

    def format_adaptive_heatmap(
        self,
        bins: List[HeatmapBin],
        title: str = "Adaptive Band Activity Heatmap",
    ) -> str:
        """Render adaptive heatmap bins as terminal-friendly text output."""
        if not bins:
            return f"{title}\n(No heatmap data)"

        gradient = "▁▂▃▄▅▆▇█"
        lines = [f"{title}", "=" * len(title), ""]

        for entry in bins:
            mhz = entry.center_hz / 1e6
            level_idx = min(len(gradient) - 1, int(round(entry.activity_score * 7)))
            block = gradient[level_idx] * 8
            lines.append(
                f"{mhz:8.3f} MHz │{block}│ score={entry.activity_score:0.2f} avg={entry.avg_s_meter:5.1f} peak={entry.peak_s_meter:3} n={entry.sample_count:2}"
            )

        lines.extend(["", f"Bins: {len(bins)} (adaptive)"])
        return "\n".join(lines)

    def extract_heatmap_hotspots(
        self,
        bins: List[HeatmapBin],
        min_score: float = 0.65,
        top_n: int = 5,
        min_samples: int = 1,
    ) -> List[HeatmapHotspot]:
        """
        Rank likely activity hotspots from adaptive heatmap bins.

        Args:
            bins: Heatmap bins produced by build_adaptive_heatmap()
            min_score: Minimum activity score (0.0-1.0) required
            top_n: Maximum hotspots to return
            min_samples: Minimum number of raw samples represented in a bin

        Returns:
            List of HeatmapHotspot entries sorted by activity confidence
        """
        if not bins or top_n <= 0:
            return []

        filtered = [
            b
            for b in bins
            if b.sample_count >= max(0, min_samples)
            and b.activity_score >= max(0.0, min(1.0, min_score))
        ]

        ranked = sorted(
            filtered,
            key=lambda b: (b.activity_score, b.peak_s_meter, b.sample_count),
            reverse=True,
        )

        return [
            HeatmapHotspot(
                start_hz=entry.start_hz,
                end_hz=entry.end_hz,
                center_hz=entry.center_hz,
                avg_s_meter=entry.avg_s_meter,
                peak_s_meter=entry.peak_s_meter,
                sample_count=entry.sample_count,
                activity_score=entry.activity_score,
            )
            for entry in ranked[:top_n]
        ]

    def format_heatmap_hotspots(
        self,
        hotspots: List[HeatmapHotspot],
        title: str = "Adaptive Heatmap Hotspots",
    ) -> str:
        """Render ranked hotspot candidates for fast operator review."""
        if not hotspots:
            return f"{title}\n(No hotspots above threshold)"

        lines = [f"{title}", "=" * len(title), ""]
        for idx, hs in enumerate(hotspots, start=1):
            lines.append(
                f"#{idx:<2} {hs.center_hz/1e6:8.3f} MHz  range={hs.start_hz/1e6:8.3f}-{hs.end_hz/1e6:8.3f}  score={hs.activity_score:0.2f}  peak={hs.peak_s_meter:3}  avg={hs.avg_s_meter:5.1f}  n={hs.sample_count:2}"
            )

        lines.extend(["", f"Candidates: {len(hotspots)}"])
        return "\n".join(lines)

    def merge_hotspot_windows(
        self, hotspots: List[HeatmapHotspot], max_gap_hz: int = 1000
    ) -> List[HotspotWindow]:
        """Merge nearby hotspot bins into tune-ready frequency windows."""
        if not hotspots:
            return []

        ordered = sorted(hotspots, key=lambda h: h.start_hz)
        windows: List[HotspotWindow] = []

        group: List[HeatmapHotspot] = [ordered[0]]

        def _finalize(grouped: List[HeatmapHotspot]) -> HotspotWindow:
            start_hz = grouped[0].start_hz
            end_hz = grouped[-1].end_hz
            avg_score = mean(h.activity_score for h in grouped)
            peak_s = max(h.peak_s_meter for h in grouped)
            return HotspotWindow(
                start_hz=start_hz,
                end_hz=end_hz,
                center_hz=(start_hz + end_hz) // 2,
                peak_s_meter=peak_s,
                avg_score=avg_score,
                hotspot_count=len(grouped),
            )

        for current in ordered[1:]:
            prev = group[-1]
            if current.start_hz <= (prev.end_hz + max(0, max_gap_hz)):
                group.append(current)
            else:
                windows.append(_finalize(group))
                group = [current]

        windows.append(_finalize(group))
        return windows

    def format_hotspot_windows(
        self,
        windows: List[HotspotWindow],
        title: str = "Hotspot Windows",
    ) -> str:
        """Render merged hotspot windows for quick operator tuning."""
        if not windows:
            return f"{title}\n(No hotspot windows)"

        lines = [f"{title}", "=" * len(title), ""]
        for idx, window in enumerate(windows, start=1):
            lines.append(
                f"W{idx:<2} {window.center_hz/1e6:8.3f} MHz  range={window.start_hz/1e6:8.3f}-{window.end_hz/1e6:8.3f}  avg-score={window.avg_score:0.2f}  peak={window.peak_s_meter:3}  bins={window.hotspot_count:2}"
            )

        lines.extend(["", f"Windows: {len(windows)}"])
        return "\n".join(lines)

    def build_hotspot_window_plan(
        self,
        windows: List[HotspotWindow],
        cycle_ms: int = 30000,
        min_dwell_ms: int = 1200,
    ) -> List[HotspotWindowPlanStep]:
        """Build a ranked operator review plan from hotspot windows.

        Produces receive-only review guidance (order + dwell time) without
        changing radio state.
        """
        if not windows:
            return []

        safe_cycle_ms = max(min_dwell_ms * len(windows), cycle_ms)
        scored = sorted(
            windows,
            key=lambda w: (w.avg_score, w.peak_s_meter, w.hotspot_count),
            reverse=True,
        )

        weights = [max(0.01, w.avg_score * max(1, w.hotspot_count)) for w in scored]
        weight_sum = sum(weights) or 1.0

        plan: List[HotspotWindowPlanStep] = []
        for idx, (window, weight) in enumerate(zip(scored, weights), start=1):
            share = weight / weight_sum
            dwell_ms = max(min_dwell_ms, int(round(safe_cycle_ms * share)))
            priority_score = window.avg_score * (1.0 + (0.15 * (window.hotspot_count - 1)))
            plan.append(
                HotspotWindowPlanStep(
                    rank=idx,
                    center_hz=window.center_hz,
                    start_hz=window.start_hz,
                    end_hz=window.end_hz,
                    dwell_ms=dwell_ms,
                    priority_score=priority_score,
                    hotspot_count=window.hotspot_count,
                )
            )

        return plan

    def format_hotspot_window_plan(
        self,
        steps: List[HotspotWindowPlanStep],
        title: str = "Hotspot Window Review Plan",
    ) -> str:
        """Render ranked hotspot window review plan for operator workflow."""
        if not steps:
            return f"{title}\n(No review plan)"

        lines = [f"{title}", "=" * len(title), ""]
        total_dwell_ms = 0
        for step in steps:
            total_dwell_ms += step.dwell_ms
            lines.append(
                f"P{step.rank:<2} {step.center_hz/1e6:8.3f} MHz  range={step.start_hz/1e6:8.3f}-{step.end_hz/1e6:8.3f}  dwell={step.dwell_ms:5} ms  priority={step.priority_score:0.2f}  bins={step.hotspot_count:2}"
            )

        lines.extend(["", f"Plan steps: {len(steps)}  cycle={total_dwell_ms} ms"])
        return "\n".join(lines)

    def build_hotspot_window_timeline(
        self,
        steps: List[HotspotWindowPlanStep],
    ) -> List[HotspotWindowTimelineStep]:
        """Project ranked plan steps into a single-cycle time timeline.

        RX/analysis only: does not tune or transmit, only computes schedule offsets.
        """
        if not steps:
            return []

        ordered = sorted(steps, key=lambda s: s.rank)
        cycle_ms = sum(step.dwell_ms for step in ordered)

        timeline: List[HotspotWindowTimelineStep] = []
        offset_ms = 0
        for step in ordered:
            end_offset = offset_ms + step.dwell_ms
            timeline.append(
                HotspotWindowTimelineStep(
                    rank=step.rank,
                    center_hz=step.center_hz,
                    dwell_ms=step.dwell_ms,
                    start_offset_ms=offset_ms,
                    end_offset_ms=end_offset,
                    revisit_after_ms=cycle_ms,
                )
            )
            offset_ms = end_offset

        return timeline

    def format_hotspot_window_timeline(
        self,
        steps: List[HotspotWindowTimelineStep],
        title: str = "Hotspot Window Timeline",
    ) -> str:
        """Render timeline offsets for one review cycle."""
        if not steps:
            return f"{title}\n(No timeline)"

        lines = [f"{title}", "=" * len(title), ""]
        for step in steps:
            lines.append(
                f"T{step.rank:<2} {step.center_hz/1e6:8.3f} MHz  start=+{step.start_offset_ms:5} ms  end=+{step.end_offset_ms:5} ms  dwell={step.dwell_ms:5} ms  revisit={step.revisit_after_ms:5} ms"
            )

        lines.extend(["", f"Timeline steps: {len(steps)}"])
        return "\n".join(lines)

    def build_hotspot_window_clock(
        self,
        steps: List[HotspotWindowTimelineStep],
        start_epoch_ms: Optional[int] = None,
    ) -> List[HotspotWindowClockStep]:
        """Anchor timeline steps to wall-clock times for operator synchronization.

        RX/analysis only: computes schedule timestamps, does not tune or transmit.
        """
        if not steps:
            return []

        anchor_ms = int(time.time() * 1000) if start_epoch_ms is None else int(start_epoch_ms)

        clock_steps: List[HotspotWindowClockStep] = []
        for step in steps:
            clock_steps.append(
                HotspotWindowClockStep(
                    rank=step.rank,
                    center_hz=step.center_hz,
                    dwell_ms=step.dwell_ms,
                    start_epoch_ms=anchor_ms + step.start_offset_ms,
                    end_epoch_ms=anchor_ms + step.end_offset_ms,
                    revisit_epoch_ms=anchor_ms + step.revisit_after_ms,
                )
            )

        return clock_steps

    def format_hotspot_window_clock(
        self,
        steps: List[HotspotWindowClockStep],
        title: str = "Hotspot Window Clock Sync",
    ) -> str:
        """Render wall-clock schedule for one hotspot review cycle."""
        if not steps:
            return f"{title}\n(No clock schedule)"

        lines = [f"{title}", "=" * len(title), ""]

        def _fmt(epoch_ms: int) -> str:
            dt = datetime.fromtimestamp(epoch_ms / 1000.0)
            return dt.strftime("%H:%M:%S.%f")[:-3]

        for step in steps:
            lines.append(
                f"C{step.rank:<2} {step.center_hz/1e6:8.3f} MHz  start={_fmt(step.start_epoch_ms)}  end={_fmt(step.end_epoch_ms)}  dwell={step.dwell_ms:5} ms  revisit={_fmt(step.revisit_epoch_ms)}"
            )

        lines.extend(["", f"Clock steps: {len(steps)}"])
        return "\n".join(lines)

    def get_hotspot_window_now(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
    ) -> Optional[HotspotWindowNowState]:
        """Resolve the active and upcoming review steps at the current wall-clock time."""
        if not steps:
            return None

        ordered = sorted(steps, key=lambda s: (s.start_epoch_ms, s.rank))
        anchor_ms = ordered[0].start_epoch_ms
        cycle_ms = max(
            1,
            max(step.revisit_epoch_ms - step.start_epoch_ms for step in ordered),
        )

        now_ms = int(time.time() * 1000) if now_epoch_ms is None else int(now_epoch_ms)
        if now_ms < anchor_ms:
            cycle_index = 0
            cycle_offset_ms = 0
        else:
            delta = now_ms - anchor_ms
            cycle_index = delta // cycle_ms
            cycle_offset_ms = delta % cycle_ms

        offsets = [
            (
                step,
                max(0, step.start_epoch_ms - anchor_ms),
                max(0, step.end_epoch_ms - anchor_ms),
            )
            for step in ordered
        ]

        active_idx = 0
        for idx, (_, start_off, end_off) in enumerate(offsets):
            if start_off <= cycle_offset_ms < end_off:
                active_idx = idx
                break
        else:
            if cycle_offset_ms >= offsets[-1][2]:
                active_idx = len(offsets) - 1

        active_step, active_start_off, active_end_off = offsets[active_idx]
        active_start_epoch_ms = anchor_ms + (cycle_index * cycle_ms) + active_start_off
        active_end_epoch_ms = anchor_ms + (cycle_index * cycle_ms) + active_end_off

        next_idx = (active_idx + 1) % len(offsets)
        next_step, next_start_off, _ = offsets[next_idx]
        next_cycle_index = cycle_index + (1 if next_idx == 0 else 0)
        next_start_epoch_ms = anchor_ms + (next_cycle_index * cycle_ms) + next_start_off

        return HotspotWindowNowState(
            now_epoch_ms=now_ms,
            cycle_ms=cycle_ms,
            cycle_offset_ms=cycle_offset_ms,
            active_rank=active_step.rank,
            active_center_hz=active_step.center_hz,
            active_start_epoch_ms=active_start_epoch_ms,
            active_end_epoch_ms=active_end_epoch_ms,
            ms_until_switch=max(0, active_end_epoch_ms - now_ms),
            next_rank=next_step.rank,
            next_center_hz=next_step.center_hz,
            next_start_epoch_ms=next_start_epoch_ms,
        )

    def format_hotspot_window_now(
        self,
        state: Optional[HotspotWindowNowState],
        title: str = "Hotspot Window Now",
    ) -> str:
        """Render active/next review guidance for the current schedule position."""
        if state is None:
            return f"{title}\n(No active schedule)"

        def _fmt(epoch_ms: int) -> str:
            dt = datetime.fromtimestamp(epoch_ms / 1000.0)
            return dt.strftime("%H:%M:%S.%f")[:-3]

        lines = [f"{title}", "=" * len(title), ""]
        lines.append(
            f"Now: {_fmt(state.now_epoch_ms)}  cycle={state.cycle_ms} ms  offset=+{state.cycle_offset_ms} ms"
        )
        lines.append(
            f"Active: P{state.active_rank} @ {state.active_center_hz/1e6:8.3f} MHz  "
            f"window={_fmt(state.active_start_epoch_ms)}→{_fmt(state.active_end_epoch_ms)}  "
            f"switch-in={state.ms_until_switch} ms"
        )
        lines.append(
            f"Next:   P{state.next_rank} @ {state.next_center_hz/1e6:8.3f} MHz  "
            f"starts={_fmt(state.next_start_epoch_ms)}"
        )
        return "\n".join(lines)

    def build_hotspot_window_upcoming(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
        count: int = 3,
    ) -> List[HotspotWindowUpcomingStep]:
        """Project next schedule handoffs from the current wall-clock position."""
        if not steps or count <= 0:
            return []

        ordered = sorted(steps, key=lambda s: (s.start_epoch_ms, s.rank))
        anchor_ms = ordered[0].start_epoch_ms
        cycle_ms = max(
            1,
            max(step.revisit_epoch_ms - step.start_epoch_ms for step in ordered),
        )

        now_ms = int(time.time() * 1000) if now_epoch_ms is None else int(now_epoch_ms)

        if now_ms < anchor_ms:
            cycle_index = 0
            cycle_offset_ms = 0
        else:
            delta = now_ms - anchor_ms
            cycle_index = delta // cycle_ms
            cycle_offset_ms = delta % cycle_ms

        offsets = [
            (
                step,
                max(0, step.start_epoch_ms - anchor_ms),
                max(0, step.end_epoch_ms - anchor_ms),
            )
            for step in ordered
        ]

        start_idx = None
        for idx, (_, start_off, _) in enumerate(offsets):
            if start_off > cycle_offset_ms:
                start_idx = idx
                break

        start_cycle = cycle_index
        if start_idx is None:
            start_idx = 0
            start_cycle += 1

        upcoming: List[HotspotWindowUpcomingStep] = []
        current_idx = start_idx
        current_cycle = start_cycle

        for seq in range(1, count + 1):
            step, start_off, end_off = offsets[current_idx]
            start_epoch_ms = anchor_ms + (current_cycle * cycle_ms) + start_off
            end_epoch_ms = anchor_ms + (current_cycle * cycle_ms) + end_off
            upcoming.append(
                HotspotWindowUpcomingStep(
                    sequence=seq,
                    rank=step.rank,
                    center_hz=step.center_hz,
                    starts_in_ms=max(0, start_epoch_ms - now_ms),
                    start_epoch_ms=start_epoch_ms,
                    end_epoch_ms=end_epoch_ms,
                    dwell_ms=max(0, end_epoch_ms - start_epoch_ms),
                    cycle_index=current_cycle,
                )
            )

            current_idx += 1
            if current_idx >= len(offsets):
                current_idx = 0
                current_cycle += 1

        return upcoming

    def format_hotspot_window_upcoming(
        self,
        steps: List[HotspotWindowUpcomingStep],
        title: str = "Hotspot Window Upcoming",
    ) -> str:
        """Render upcoming handoff schedule for near-term operator planning."""
        if not steps:
            return f"{title}\n(No upcoming schedule)"

        def _fmt(epoch_ms: int) -> str:
            dt = datetime.fromtimestamp(epoch_ms / 1000.0)
            return dt.strftime("%H:%M:%S.%f")[:-3]

        lines = [f"{title}", "=" * len(title), ""]
        for step in steps:
            lines.append(
                f"U{step.sequence:<2} P{step.rank:<2} @ {step.center_hz/1e6:8.3f} MHz  "
                f"starts-in={step.starts_in_ms:5} ms  start={_fmt(step.start_epoch_ms)}  "
                f"end={_fmt(step.end_epoch_ms)}  dwell={step.dwell_ms:5} ms  cycle={step.cycle_index}"
            )

        lines.extend(["", f"Upcoming steps: {len(steps)}"])
        return "\n".join(lines)

    def build_hotspot_window_brief(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
        upcoming_count: int = 3,
    ) -> Optional[HotspotWindowBrief]:
        """Build compact live handoff brief for operator situational awareness."""
        state = self.get_hotspot_window_now(steps, now_epoch_ms=now_epoch_ms)
        if state is None:
            return None

        upcoming = self.build_hotspot_window_upcoming(
            steps,
            now_epoch_ms=state.now_epoch_ms,
            count=max(0, upcoming_count),
        )
        return HotspotWindowBrief(
            generated_epoch_ms=state.now_epoch_ms,
            cycle_ms=state.cycle_ms,
            active_rank=state.active_rank,
            active_center_hz=state.active_center_hz,
            ms_until_switch=state.ms_until_switch,
            next_rank=state.next_rank,
            next_center_hz=state.next_center_hz,
            upcoming=upcoming,
        )

    def format_hotspot_window_brief(
        self,
        brief: Optional[HotspotWindowBrief],
        title: str = "Hotspot Window Brief",
    ) -> str:
        """Render compact now + upcoming handoff brief for manual RX operations."""
        if brief is None:
            return f"{title}\n(No active schedule)"

        lines = [f"{title}", "=" * len(title), ""]
        lines.append(
            f"Active now: P{brief.active_rank} @ {brief.active_center_hz/1e6:8.3f} MHz"
        )
        lines.append(
            f"Switch in: {brief.ms_until_switch} ms  → Next: P{brief.next_rank} @ {brief.next_center_hz/1e6:8.3f} MHz"
        )
        lines.append(f"Cycle: {brief.cycle_ms} ms")

        if brief.upcoming:
            lines.append("")
            lines.append("Upcoming handoffs:")
            for step in brief.upcoming:
                lines.append(
                    f"  U{step.sequence}: P{step.rank} @ {step.center_hz/1e6:8.3f} MHz in {step.starts_in_ms} ms"
                )
        else:
            lines.append("")
            lines.append("Upcoming handoffs: none")

        return "\n".join(lines)

    def build_hotspot_window_cue(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
    ) -> Optional[HotspotWindowCue]:
        """Build one-line live operator cue from current hotspot schedule state."""
        state = self.get_hotspot_window_now(steps, now_epoch_ms=now_epoch_ms)
        if state is None:
            return None

        return HotspotWindowCue(
            generated_epoch_ms=state.now_epoch_ms,
            active_rank=state.active_rank,
            active_center_hz=state.active_center_hz,
            next_rank=state.next_rank,
            next_center_hz=state.next_center_hz,
            ms_until_switch=state.ms_until_switch,
        )

    def format_hotspot_window_cue(
        self,
        cue: Optional[HotspotWindowCue],
        title: str = "Hotspot Window Cue",
    ) -> str:
        """Render single-line active→next handoff cue for low-overhead operator glance."""
        if cue is None:
            return f"{title}\n(No active schedule)"

        return (
            f"{title}: P{cue.active_rank} {cue.active_center_hz/1e6:8.3f} MHz"
            f" → P{cue.next_rank} {cue.next_center_hz/1e6:8.3f} MHz"
            f" in {cue.ms_until_switch} ms"
        )

    def build_hotspot_window_action(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
        ready_threshold_ms: int = 5000,
    ) -> Optional[HotspotWindowAction]:
        """Build HOLD/READY/SWITCH action signal from live hotspot window cue state."""
        cue = self.build_hotspot_window_cue(steps, now_epoch_ms=now_epoch_ms)
        if cue is None:
            return None

        ready_ms = max(0, ready_threshold_ms)
        switch_floor_ms = min(250, ready_ms) if ready_ms > 0 else 0
        if cue.ms_until_switch <= switch_floor_ms:
            action = "SWITCH"
            reason = "handoff due now"
        elif cue.ms_until_switch <= ready_ms:
            action = "READY"
            reason = f"handoff inside {ready_ms} ms window"
        else:
            action = "HOLD"
            reason = "continue active window"

        return HotspotWindowAction(
            generated_epoch_ms=cue.generated_epoch_ms,
            active_rank=cue.active_rank,
            active_center_hz=cue.active_center_hz,
            next_rank=cue.next_rank,
            next_center_hz=cue.next_center_hz,
            ms_until_switch=cue.ms_until_switch,
            action=action,
            action_reason=reason,
        )

    def format_hotspot_window_action(
        self,
        action: Optional[HotspotWindowAction],
        title: str = "Hotspot Window Action",
    ) -> str:
        """Render one-line HOLD/READY/SWITCH action cue for manual RX handoffs."""
        if action is None:
            return f"{title}\n(No active schedule)"

        return (
            f"{title}: {action.action} | P{action.active_rank} {action.active_center_hz/1e6:8.3f} MHz"
            f" → P{action.next_rank} {action.next_center_hz/1e6:8.3f} MHz"
            f" in {action.ms_until_switch} ms ({action.action_reason})"
        )

    def build_hotspot_window_decision(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
        ready_threshold_ms: int = 5000,
        critical_threshold_ms: int = 2500,
        switch_floor_ms: int = 1000,
    ) -> Optional[HotspotWindowDecision]:
        """Build urgency-tagged decision payload for low-latency handoff operations."""
        action = self.build_hotspot_window_action(
            steps,
            now_epoch_ms=now_epoch_ms,
            ready_threshold_ms=ready_threshold_ms,
        )
        if action is None:
            return None

        clamped_critical_ms = max(0, critical_threshold_ms)
        ready_ms = max(0, ready_threshold_ms)
        effective_switch_floor_ms = min(max(0, switch_floor_ms), min(250, ready_ms) if ready_ms > 0 else 0)
        if action.ms_until_switch <= effective_switch_floor_ms:
            urgency = "CRITICAL"
            reason = "switch boundary reached"
        elif action.ms_until_switch <= clamped_critical_ms:
            urgency = "HIGH"
            reason = f"handoff inside {clamped_critical_ms} ms critical window"
        elif action.ms_until_switch <= ready_ms:
            urgency = "MEDIUM"
            reason = f"handoff inside {ready_ms} ms ready window"
        else:
            urgency = "LOW"
            reason = "handoff outside ready window"

        if action.ms_until_switch <= 0:
            recommended_check_ms = 250
        else:
            recommended_check_ms = max(250, min(5000, action.ms_until_switch // 2))

        return HotspotWindowDecision(
            generated_epoch_ms=action.generated_epoch_ms,
            active_rank=action.active_rank,
            active_center_hz=action.active_center_hz,
            next_rank=action.next_rank,
            next_center_hz=action.next_center_hz,
            ms_until_switch=action.ms_until_switch,
            action=action.action,
            urgency=urgency,
            recommended_check_ms=recommended_check_ms,
            decision_reason=reason,
        )

    def format_hotspot_window_decision(
        self,
        decision: Optional[HotspotWindowDecision],
        title: str = "Hotspot Window Decision",
    ) -> str:
        """Render one-line action + urgency decision aid for manual RX handoffs."""
        if decision is None:
            return f"{title}\n(No active schedule)"

        return (
            f"{title}: {decision.action}/{decision.urgency} | "
            f"P{decision.active_rank} {decision.active_center_hz/1e6:8.3f} MHz"
            f" → P{decision.next_rank} {decision.next_center_hz/1e6:8.3f} MHz"
            f" in {decision.ms_until_switch} ms"
            f" | recheck={decision.recommended_check_ms} ms"
            f" ({decision.decision_reason})"
        )

    def build_hotspot_window_ops(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
        ready_threshold_ms: int = 5000,
        critical_threshold_ms: int = 2500,
        upcoming_count: int = 2,
    ) -> Optional[HotspotWindowOps]:
        """Build compact operations card from decision state + upcoming handoffs."""
        decision = self.build_hotspot_window_decision(
            steps,
            now_epoch_ms=now_epoch_ms,
            ready_threshold_ms=ready_threshold_ms,
            critical_threshold_ms=critical_threshold_ms,
        )
        if decision is None:
            return None

        upcoming = self.build_hotspot_window_upcoming(
            steps,
            now_epoch_ms=decision.generated_epoch_ms,
            count=max(0, upcoming_count),
        )

        return HotspotWindowOps(
            generated_epoch_ms=decision.generated_epoch_ms,
            action=decision.action,
            urgency=decision.urgency,
            recommended_check_ms=decision.recommended_check_ms,
            active_rank=decision.active_rank,
            active_center_hz=decision.active_center_hz,
            next_rank=decision.next_rank,
            next_center_hz=decision.next_center_hz,
            ms_until_switch=decision.ms_until_switch,
            upcoming=upcoming,
        )

    def format_hotspot_window_ops(
        self,
        ops: Optional[HotspotWindowOps],
        title: str = "Hotspot Window Ops",
    ) -> str:
        """Render compact multi-line operations card for manual RX handoff loop."""
        if ops is None:
            return f"{title}\n(No active schedule)"

        lines = [
            f"{title}: {ops.action}/{ops.urgency} | recheck={ops.recommended_check_ms} ms",
            (
                f"Now: P{ops.active_rank} {ops.active_center_hz/1e6:8.3f} MHz"
                f" → P{ops.next_rank} {ops.next_center_hz/1e6:8.3f} MHz"
                f" in {ops.ms_until_switch} ms"
            ),
        ]

        if ops.upcoming:
            queue = ", ".join(
                f"U{item.sequence}:P{item.rank}@{item.starts_in_ms}ms" for item in ops.upcoming
            )
            lines.append(f"Queue: {queue}")
        else:
            lines.append("Queue: (none)")

        return "\n".join(lines)

    def build_hotspot_window_directive(
        self,
        steps: List[HotspotWindowClockStep],
        now_epoch_ms: Optional[int] = None,
        ready_threshold_ms: int = 5000,
        critical_threshold_ms: int = 2500,
        upcoming_count: int = 2,
    ) -> Optional[HotspotWindowDirective]:
        """Build execution directive checklist from compact ops-card state."""
        ops = self.build_hotspot_window_ops(
            steps,
            now_epoch_ms=now_epoch_ms,
            ready_threshold_ms=ready_threshold_ms,
            critical_threshold_ms=critical_threshold_ms,
            upcoming_count=upcoming_count,
        )
        if ops is None:
            return None

        summary = (
            f"{ops.action}/{ops.urgency}: P{ops.active_rank} {ops.active_center_hz/1e6:8.3f} MHz"
            f" → P{ops.next_rank} {ops.next_center_hz/1e6:8.3f} MHz in {ops.ms_until_switch} ms"
        )

        checklist = [
            f"Monitor active window P{ops.active_rank} on {ops.active_center_hz/1e6:8.3f} MHz",
            f"Recheck in {ops.recommended_check_ms} ms",
        ]
        if ops.action in {"READY", "SWITCH"}:
            checklist.append(
                f"Prepare handoff target P{ops.next_rank} at {ops.next_center_hz/1e6:8.3f} MHz"
            )
        if ops.action == "SWITCH":
            checklist.append("Switch now and confirm signal continuity")
        elif ops.upcoming:
            first = ops.upcoming[0]
            checklist.append(
                f"Queue next: U{first.sequence} P{first.rank} in {first.starts_in_ms} ms"
            )

        return HotspotWindowDirective(
            generated_epoch_ms=ops.generated_epoch_ms,
            summary=summary,
            action=ops.action,
            urgency=ops.urgency,
            recheck_ms=ops.recommended_check_ms,
            checklist=checklist,
        )

    def format_hotspot_window_directive(
        self,
        directive: Optional[HotspotWindowDirective],
        title: str = "Hotspot Window Directive",
    ) -> str:
        """Render short actionable directive with immediate RX checklist."""
        if directive is None:
            return f"{title}\n(No active schedule)"

        lines = [
            f"{title}: {directive.summary}",
            f"Cadence: recheck={directive.recheck_ms} ms",
            "Checklist:",
        ]
        for idx, item in enumerate(directive.checklist, start=1):
            lines.append(f"  {idx}. {item}")
        return "\n".join(lines)

    def format_scan_results(
        self, results: List[Tuple[int, int]], title: str = "Band Scan Results"
    ) -> str:
        """
        Format scan results as ASCII bar chart for terminal display.

        Args:
            results: List of (frequency_hz, s_meter) tuples
            title: Chart title

        Returns:
            Multi-line string with ASCII bar chart
        """
        if not results:
            return f"{title}\n(No results)"

        lines = [f"{title}", "=" * len(title), ""]

        # Find max S-meter value for scaling
        max_s = max(s for _, s in results) if results else 1
        bar_width = 40  # Terminal columns for bar

        for freq_hz, s_meter in results:
            freq_mhz = freq_hz / 1e6
            s_units = self._s_meter_to_units(s_meter)

            # Create bar
            bar_length = int((s_meter / max_s) * bar_width) if max_s > 0 else 0
            bar = "█" * bar_length + "░" * (bar_width - bar_length)

            # Format line
            line = f"{freq_mhz:8.3f} MHz │{bar}│ S{s_units:2} ({s_meter:3})"
            lines.append(line)

        # Add legend
        lines.extend(
            [
                "",
                f"Scale: 0 - S{self._s_meter_to_units(max_s)} (0-{max_s})",
                f"Frequencies: {len(results)} scanned",
            ]
        )

        return "\n".join(lines)

    def format_activity_results(
        self, results: List[ActivityResult], title: str = "Active Frequencies"
    ) -> str:
        """
        Format activity detection results for terminal display.

        Args:
            results: List of ActivityResult objects
            title: Display title

        Returns:
            Multi-line string with formatted results
        """
        if not results:
            return f"{title}\n(No activity detected)"

        lines = [f"{title}", "=" * len(title), ""]

        for result in results:
            line = f"{result.frequency_mhz:8.3f} MHz - {result.s_level_text:4} ({result.s_meter:3})"
            lines.append(line)

        lines.extend(["", f"Total: {len(results)} active frequencies"])

        return "\n".join(lines)

    def _s_meter_to_units(self, s_meter_raw: int) -> int:
        """
        Convert raw S-meter value (0-255) to S-units (0-9).

        Approximate conversion based on typical FT-991A behavior.
        Each S-unit represents ~6dB, with S9 at about 50µV.
        """
        if s_meter_raw <= 0:
            return 0
        elif s_meter_raw >= 255:
            return 9
        else:
            # Linear approximation: 0-255 raw maps to 0-9 S-units
            # Use 28 as threshold to get cleaner math (28*9 = 252, close to 255)
            return min(9, s_meter_raw // 28)
