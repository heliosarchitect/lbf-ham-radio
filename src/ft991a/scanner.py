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
from typing import List, Tuple

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
        logger.debug(f"Saved radio state: {self._original_frequency} Hz, {self._original_mode}")

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
        logger.debug(f"Restored radio state: {self._original_frequency} Hz, {self._original_mode}")

    def scan_band(self, start_hz: int, end_hz: int, step_hz: int, dwell_ms: int = 150) -> List[Tuple[int, int]]:
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
        logger.info(f"Scanning {start_hz:,} - {end_hz:,} Hz (step: {step_hz:,} Hz, dwell: {dwell_ms}ms)")

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
        logger.info(f"Searching for activity above S{self._s_meter_to_units(threshold)} threshold")

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

    def fine_scan(self, center_hz: int, width_hz: int = 20000, step_hz: int = 1000) -> List[Tuple[int, int]]:
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

        logger.info(f"Fine scanning around {center_hz/1e6:.3f} MHz (±{width_hz/1000:.0f} kHz)")

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
            band_name = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"][i]
            logger.info(f"Scanning {band_name} band: {start_hz/1e6:.3f} - {end_hz/1e6:.3f} MHz")

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

    def format_scan_results(self, results: List[Tuple[int, int]], title: str = "Band Scan Results") -> str:
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
            ["", f"Scale: 0 - S{self._s_meter_to_units(max_s)} (0-{max_s})", f"Frequencies: {len(results)} scanned"]
        )

        return "\n".join(lines)

    def format_activity_results(self, results: List[ActivityResult], title: str = "Active Frequencies") -> str:
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
