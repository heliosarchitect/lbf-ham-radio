#!/usr/bin/env python3
"""
Unit tests for FT-991A Band Scanner module.
Uses mocked radio interface — no physical radio needed.
"""

import pytest
from unittest.mock import Mock, patch, call
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ft991a.scanner import BandScanner, ScanResult, ActivityResult
from ft991a.cat import FT991A, Mode


class TestBandScanner:

    @pytest.fixture
    def mock_radio(self):
        """Create a mocked radio for testing."""
        radio = Mock(spec=FT991A)
        radio.get_frequency_a.return_value = 14074000  # Default FT8 frequency
        radio.get_mode.return_value = "DATA_USB"
        radio.get_s_meter.return_value = 25  # Default S-meter reading
        return radio

    @pytest.fixture
    def scanner(self, mock_radio):
        """Create scanner with mocked radio."""
        return BandScanner(mock_radio)

    def test_init(self, mock_radio):
        """Test scanner initialization."""
        scanner = BandScanner(mock_radio)
        assert scanner.radio == mock_radio
        assert scanner._original_frequency is None
        assert scanner._original_mode is None

    def test_save_restore_radio_state(self, scanner, mock_radio):
        """Test radio state save/restore functionality."""
        mock_radio.get_frequency_a.return_value = 14074000
        mock_radio.get_mode.return_value = "DATA_USB"
        
        scanner._save_radio_state()
        assert scanner._original_frequency == 14074000
        assert scanner._original_mode == "DATA_USB"
        
        # Restore should set frequency and mode back
        scanner._restore_radio_state()
        mock_radio.set_frequency_a.assert_called_with(14074000)
        # Mode restoration requires enum conversion - just check it was called
        assert mock_radio.set_mode.called

    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_scan_band_basic(self, mock_sleep, scanner, mock_radio):
        """Test basic band scanning functionality."""
        # Set up mock S-meter readings that vary
        mock_radio.get_s_meter.side_effect = [10, 25, 45, 30, 15]
        
        results = scanner.scan_band(14000000, 14020000, 5000, dwell_ms=100)
        
        # Should have scanned 5 frequencies: 14.000, 14.005, 14.010, 14.015, 14.020
        assert len(results) == 5
        
        expected_freqs = [14000000, 14005000, 14010000, 14015000, 14020000]
        expected_s_meters = [10, 25, 45, 30, 15]
        
        for i, (freq, s_meter) in enumerate(results):
            assert freq == expected_freqs[i]
            assert s_meter == expected_s_meters[i]
        
        # Verify radio was tuned to each frequency
        expected_calls = [call(freq) for freq in expected_freqs]
        mock_radio.set_frequency_a.assert_has_calls(expected_calls)
        
        # Verify sleep was called with correct dwell time
        assert mock_sleep.call_count == 5
        mock_sleep.assert_called_with(0.1)  # 100ms dwell time

    def test_scan_band_empty_range(self, scanner, mock_radio):
        """Test scanning with empty range."""
        results = scanner.scan_band(14010000, 14005000, 5000)  # end < start
        assert len(results) == 0

    @patch('ft991a.scanner.BandScanner.scan_band')
    def test_find_activity(self, mock_scan_band, scanner):
        """Test activity detection functionality."""
        # Mock scan_band to return different results for different bands
        mock_scan_band.side_effect = [
            [(1800000, 60), (1850000, 25)],     # 160m: one active
            [(3500000, 70), (3600000, 80)],     # 80m: two active  
            [],                                  # 60m: none
            [(7000000, 45), (7100000, 30)],     # 40m: none above threshold
        ] + [[] for _ in range(6)]  # Remaining bands empty
        
        active = scanner.find_activity(threshold=50)
        
        # Should find 3 active frequencies: 1.8 MHz (S60), 3.5 MHz (S70), 3.6 MHz (S80)
        assert len(active) == 3
        
        # Check results are sorted by frequency
        assert active[0].frequency_hz == 1800000
        assert active[0].s_meter == 60
        assert active[1].frequency_hz == 3500000
        assert active[1].s_meter == 70
        assert active[2].frequency_hz == 3600000
        assert active[2].s_meter == 80
        
        # Check frequency MHz conversion
        assert abs(active[0].frequency_mhz - 1.8) < 0.001
        assert abs(active[1].frequency_mhz - 3.5) < 0.001

    @patch('ft991a.scanner.BandScanner.scan_band')
    def test_fine_scan(self, mock_scan_band, scanner):
        """Test fine scanning around specific frequency."""
        mock_scan_band.return_value = [(14239000, 30), (14249000, 50), (14259000, 25)]
        
        results = scanner.fine_scan(center_hz=14249000, width_hz=20000, step_hz=1000)
        
        # Verify scan_band was called with correct parameters
        expected_start = 14249000 - 10000  # center - width/2
        expected_end = 14249000 + 10000    # center + width/2
        mock_scan_band.assert_called_once_with(expected_start, expected_end, 1000, dwell_ms=200)
        
        assert results == [(14239000, 30), (14249000, 50), (14259000, 25)]

    @patch('ft991a.scanner.BandScanner.scan_band')
    def test_scan_all_hf(self, mock_scan_band, scanner):
        """Test full HF band scanning."""
        # Mock different results for each band
        scan_results = [
            [(1800000, 15), (1850000, 25)],    # 160m
            [(3500000, 12), (3600000, 30)],    # 80m
        ] + [[] for _ in range(8)]  # Remaining bands empty
        
        mock_scan_band.side_effect = scan_results
        
        activity = scanner.scan_all_hf()
        
        # Should call scan_band for all 10 HF bands
        assert mock_scan_band.call_count == 10
        
        # Should return all signals above noise threshold (10)
        expected_results = 4  # 1800: 15, 1850: 25, 3500: 12, 3600: 30
        assert len(activity) == expected_results
        
        # Verify results are sorted by frequency
        assert activity[0].frequency_hz == 1800000
        assert activity[1].frequency_hz == 1850000

    def test_format_scan_results_empty(self, scanner):
        """Test formatting empty scan results."""
        result = scanner.format_scan_results([], "Test Results")
        assert "Test Results" in result
        assert "(No results)" in result

    def test_format_scan_results_with_data(self, scanner):
        """Test formatting scan results with data."""
        results = [
            (14074000, 30),
            (14076000, 60),
            (14078000, 45)
        ]
        
        formatted = scanner.format_scan_results(results, "FT8 Activity")
        
        assert "FT8 Activity" in formatted
        assert "14.074 MHz" in formatted
        assert "14.076 MHz" in formatted  
        assert "14.078 MHz" in formatted
        assert "3 scanned" in formatted
        
        # Should contain bar chart characters
        assert "█" in formatted or "░" in formatted

    def test_format_activity_results_empty(self, scanner):
        """Test formatting empty activity results."""
        result = scanner.format_activity_results([], "Activity Test")
        assert "Activity Test" in result
        assert "(No activity detected)" in result

    def test_format_activity_results_with_data(self, scanner):
        """Test formatting activity results with data."""
        activities = [
            ActivityResult(14074000, 45, 14.074, "S1"),
            ActivityResult(21074000, 60, 21.074, "S2")
        ]
        
        formatted = scanner.format_activity_results(activities, "HF Activity")
        
        assert "HF Activity" in formatted
        assert "14.074 MHz" in formatted
        assert "21.074 MHz" in formatted
        assert "Total: 2 active" in formatted

    def test_s_meter_conversion(self, scanner):
        """Test S-meter raw value to S-units conversion."""
        assert scanner._s_meter_to_units(0) == 0
        assert scanner._s_meter_to_units(28) == 1  # 28 // 28 = 1
        assert scanner._s_meter_to_units(56) == 2  # 56 // 28 = 2
        assert scanner._s_meter_to_units(84) == 3  # 84 // 28 = 3
        assert scanner._s_meter_to_units(255) == 9  # S9 maximum

    def test_hf_voice_bands_constant(self, scanner):
        """Test that HF_VOICE_BANDS constant is properly defined."""
        bands = scanner.HF_VOICE_BANDS
        
        # Should have 10 amateur HF bands
        assert len(bands) == 10
        
        # Each band should be a tuple of (start_hz, end_hz)
        for start_hz, end_hz in bands:
            assert isinstance(start_hz, int)
            assert isinstance(end_hz, int)
            assert start_hz < end_hz
        
        # Verify some known bands
        assert (1_800_000, 2_000_000) in bands  # 160m
        assert (14_000_000, 14_350_000) in bands  # 20m
        assert (28_000_000, 29_700_000) in bands  # 10m

    @patch('time.sleep')
    def test_keyboard_interrupt_handling(self, mock_sleep, scanner, mock_radio):
        """Test that KeyboardInterrupt is handled gracefully during scanning."""
        # Make sleep raise KeyboardInterrupt after first call
        mock_sleep.side_effect = [None, KeyboardInterrupt()]
        mock_radio.get_s_meter.side_effect = [25, 30]
        
        results = scanner.scan_band(14000000, 14010000, 5000)
        
        # Should return partial results - KeyboardInterrupt breaks the loop
        # after first frequency is processed and second sleep() fails
        assert len(results) == 1  # Got one reading before interrupt
        assert results[0] == (14000000, 25)

    def test_activity_result_dataclass(self):
        """Test ActivityResult dataclass creation and attributes."""
        result = ActivityResult(
            frequency_hz=14074000,
            s_meter=45,
            frequency_mhz=14.074,
            s_level_text="S1"
        )
        
        assert result.frequency_hz == 14074000
        assert result.s_meter == 45
        assert result.frequency_mhz == 14.074
        assert result.s_level_text == "S1"

    def test_scan_result_dataclass(self):
        """Test ScanResult dataclass creation and attributes."""
        timestamp = time.time()
        result = ScanResult(
            frequency_hz=14074000,
            s_meter=45,
            timestamp=timestamp
        )
        
        assert result.frequency_hz == 14074000
        assert result.s_meter == 45
        assert result.timestamp == timestamp