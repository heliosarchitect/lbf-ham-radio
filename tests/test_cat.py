#!/usr/bin/env python3
"""
Unit tests for FT-991A CAT control library.
Uses mocked serial interface — no physical radio needed.
"""

import pytest
from unittest.mock import Mock, patch, PropertyMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ft991a.cat import FT991A, Mode, Band, RadioStatus


def make_serial_response(*responses):
    """Create a mock serial that returns byte-by-byte for read(1), cycling through responses."""
    all_bytes = []
    for resp in responses:
        if isinstance(resp, str):
            resp = resp.encode('ascii')
        all_bytes.extend([bytes([b]) for b in resp])
    # After all responses exhausted, return empty bytes (timeout)
    all_bytes.extend([b''] * 100)
    return iter(all_bytes)


class TestFT991A:

    @pytest.fixture
    def mock_serial(self):
        with patch('ft991a.cat.serial.Serial') as mock_cls:
            mock_conn = Mock()
            mock_cls.return_value = mock_conn
            mock_conn.is_open = True
            # Default: connect() calls get_frequency_a which sends "FA;" and expects "FA014074000;"
            mock_conn.read.side_effect = make_serial_response("FA014074000;")
            yield mock_conn, mock_cls

    @pytest.fixture
    def radio(self, mock_serial):
        mock_conn, mock_cls = mock_serial
        radio = FT991A(port="/dev/mock", baudrate=38400)
        radio.connect()
        return radio

    def _reset_serial(self, mock_conn, *responses):
        """Reset mock serial to return new responses."""
        mock_conn.read.side_effect = make_serial_response(*responses)

    # --- Init & Connect ---

    def test_initialization(self, mock_serial):
        mock_conn, mock_cls = mock_serial
        radio = FT991A(port="/dev/ttyUSB0", baudrate=38400)
        assert radio.port == "/dev/ttyUSB0"
        assert radio.baudrate == 38400

    def test_connect_success(self, mock_serial):
        mock_conn, mock_cls = mock_serial
        radio = FT991A(port="/dev/mock", baudrate=38400)
        result = radio.connect()
        assert result is True
        mock_cls.assert_called_once()

    def test_connect_failure(self):
        with patch('ft991a.cat.serial.Serial') as mock_cls:
            from serial import SerialException
            mock_cls.side_effect = SerialException("Port not found")
            radio = FT991A(port="/dev/nonexistent")
            result = radio.connect()
            assert result is False

    # --- Frequency ---

    def test_get_frequency(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "FA007074000;")
        freq = radio.get_frequency_a()
        assert freq == 7074000

    def test_set_frequency(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "FA014074000;")
        radio.set_frequency_a(14074000)
        # Verify write was called with FA command
        calls = [c for c in mock_conn.write.call_args_list if b"FA" in c[0][0]]
        assert len(calls) > 0

    # --- Mode ---

    def test_get_mode(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "MD02;")
        mode = radio.get_mode()
        assert mode is not None

    def test_set_mode(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "MD0C;")
        radio.set_mode(Mode.USB)
        calls = [c for c in mock_conn.write.call_args_list if b"MD" in c[0][0]]
        assert len(calls) > 0

    # --- Power ---

    def test_set_tx_power(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "PC050;")
        radio.set_power_level(50)
        mock_conn.write.assert_called()

    # --- S-Meter ---

    def test_get_smeter(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "SM0120;")
        level = radio.get_s_meter()
        assert isinstance(level, int)

    # --- PTT ---

    def test_ptt_on(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "TX1;")
        radio.ptt_on()
        calls = mock_conn.write.call_args_list
        written = b''.join(c[0][0] for c in calls)
        assert b"TX" in written

    def test_ptt_off(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        self._reset_serial(mock_conn, "TX0;")
        radio.ptt_off()
        mock_conn.write.assert_called()

    # --- Disconnect ---

    def test_disconnect(self, radio, mock_serial):
        mock_conn, _ = mock_serial
        radio.disconnect()
        mock_conn.close.assert_called()

    # --- Enums ---

    def test_mode_enum_values(self):
        assert Mode.LSB.value == "1"
        assert Mode.USB.value == "2"
        assert Mode.CW.value == "3"
        assert Mode.FM.value == "4"
        assert Mode.AM.value == "5"
        assert Mode.DATA_USB.value == "C"

    def test_band_enum_values(self):
        assert len(Band) > 0


class TestRadioStatus:
    def test_radio_status_creation(self):
        status = RadioStatus(
            frequency_a=14074000,
            frequency_b=7074000,
            mode="USB",
            tx_active=False,
            squelch_open=True,
            s_meter=45,
            power_output=50.0,
            swr=1.2,
        )
        assert status.frequency_a == 14074000
        assert status.mode == "USB"
        assert status.tx_active is False
        assert status.s_meter == 45
