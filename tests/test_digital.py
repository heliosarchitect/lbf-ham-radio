#!/usr/bin/env python3
"""
Unit tests for FT-991A Digital Modes module.
Tests digital mode configuration, audio device detection, and WSJT-X config generation.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from ft991a.cat import Mode, RadioStatus
from ft991a.digital import DigitalModes

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestDigitalModes:

    @pytest.fixture
    def mock_radio(self):
        """Create a mocked FT991A instance"""
        radio = Mock()
        radio.port = "/dev/ttyUSB0"
        radio.baudrate = 38400
        radio.serial = Mock()
        radio.serial.is_open = True

        # Mock successful responses
        radio.set_frequency_a.return_value = True
        radio.set_mode.return_value = True
        radio.set_power_level.return_value = True
        radio._send_command.return_value = "OK"

        # Mock status response
        status = RadioStatus(
            frequency_a=14074000,
            frequency_b=14074000,
            mode="DATA_USB",
            tx_active=False,
            squelch_open=False,
            s_meter=50,
            power_output=25.0,
            swr=1.2,
        )
        radio.get_status.return_value = status

        return radio

    @pytest.fixture
    def digital_modes(self, mock_radio):
        """Create DigitalModes instance with mocked radio"""
        return DigitalModes(mock_radio)

    def test_init_requires_connected_radio(self):
        """Test that DigitalModes requires connected radio"""
        radio = Mock()
        radio.serial = None

        with pytest.raises(ValueError, match="Radio must be connected"):
            DigitalModes(radio)

        # Test with closed serial
        radio.serial = Mock()
        radio.serial.is_open = False

        with pytest.raises(ValueError, match="Radio must be connected"):
            DigitalModes(radio)

    def test_setup_ft8_default_20m(self, digital_modes, mock_radio):
        """Test FT8 setup with default 20m frequency"""
        result = digital_modes.setup_ft8()

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(14074000)  # 20m FT8
        mock_radio.set_mode.assert_called_with(Mode.DATA_USB)
        mock_radio.set_power_level.assert_called_with(25)

    def test_setup_ft8_specific_frequency(self, digital_modes, mock_radio):
        """Test FT8 setup with specific frequency"""
        result = digital_modes.setup_ft8(frequency=7074000)  # 40m FT8

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(7074000)
        mock_radio.set_mode.assert_called_with(Mode.DATA_USB)

    def test_setup_ft8_by_band(self, digital_modes, mock_radio):
        """Test FT8 setup by band selection"""
        result = digital_modes.setup_ft8(band="40m")

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(7074000)  # 40m FT8
        mock_radio.set_mode.assert_called_with(Mode.DATA_USB)

    def test_setup_ft8_frequency_failure(self, digital_modes, mock_radio):
        """Test FT8 setup when frequency setting fails"""
        mock_radio.set_frequency_a.return_value = False

        result = digital_modes.setup_ft8()
        assert result is False

    def test_setup_ft8_mode_failure(self, digital_modes, mock_radio):
        """Test FT8 setup when mode setting fails"""
        mock_radio.set_mode.return_value = False

        result = digital_modes.setup_ft8()
        assert result is False

    def test_setup_ft4_default_20m(self, digital_modes, mock_radio):
        """Test FT4 setup with default 20m frequency"""
        result = digital_modes.setup_ft4()

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(14080000)  # 20m FT4
        mock_radio.set_mode.assert_called_with(Mode.DATA_USB)
        mock_radio.set_power_level.assert_called_with(25)

    def test_setup_ft4_by_band(self, digital_modes, mock_radio):
        """Test FT4 setup by band selection"""
        result = digital_modes.setup_ft4(band="80m")

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(3575000)  # 80m FT4

    def test_setup_js8call_default_20m(self, digital_modes, mock_radio):
        """Test JS8Call setup with default 20m frequency"""
        result = digital_modes.setup_js8call()

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(14078000)  # 20m JS8
        mock_radio.set_mode.assert_called_with(Mode.DATA_USB)
        mock_radio.set_power_level.assert_called_with(20)

    def test_setup_js8call_by_band(self, digital_modes, mock_radio):
        """Test JS8Call setup by band selection"""
        result = digital_modes.setup_js8call(band="40m")

        assert result is True
        mock_radio.set_frequency_a.assert_called_with(7078000)  # 40m JS8

    def test_get_audio_device_proc_asound(self, digital_modes):
        """Test audio device detection via /proc/asound/cards"""
        mock_data = " 0 [CODEC   ]: USB Audio CODEC - C-Media USB Audio Device\n"

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=mock_data):
                device = digital_modes.get_audio_device()

                assert device is not None
                assert device["card"] == "0"
                assert device["device"] == "0"
                assert "USB Audio CODEC" in device["name"]
                assert device["alsa_name"] == "plughw:0,0"

    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=False)
    def test_get_audio_device_arecord(self, mock_exists, mock_run, digital_modes):
        """Test audio device detection via arecord command"""
        # Mock arecord output
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "card 1: CODEC [USB Audio CODEC], device 0: USB Audio [USB Audio]"
        )

        device = digital_modes.get_audio_device()

        assert device is not None
        assert device["card"] == "1"
        assert device["device"] == "0"
        assert "USB Audio CODEC" in device["name"]

    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=False)
    def test_get_audio_device_pulseaudio(self, mock_exists, mock_run, digital_modes):
        """Test audio device detection via PulseAudio"""
        # Mock failed arecord, successful pactl
        mock_run.side_effect = [
            Mock(returncode=1),  # arecord fails
            Mock(
                returncode=0,
                stdout="0\talsa_input.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo",
            ),
        ]

        device = digital_modes.get_audio_device()

        assert device is not None
        assert "USB Audio Device" in device["name"]
        assert (
            device["pulse_name"]
            == "alsa_input.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo"
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=False)
    def test_get_audio_device_not_found(self, mock_exists, mock_run, digital_modes):
        """Test when no audio device is found"""
        # Mock all detection methods failing
        mock_run.return_value.returncode = 1

        device = digital_modes.get_audio_device()
        assert device is None

    @patch("pathlib.Path.mkdir")
    def test_create_wsjtx_config(self, mock_mkdir, digital_modes, mock_radio):
        """Test WSJT-X configuration file generation"""
        with patch("builtins.open", mock_open()) as mock_file:
            # Mock home directory
            with patch("pathlib.Path.home", return_value=Path("/home/test")):
                config_path = digital_modes.create_wsjtx_config("KO4TUV", "EM75")

                assert config_path == "/home/test/.config/WSJT-X/WSJT-X.ini"

                # Verify file was opened for writing
                mock_file.assert_called_once()

                # Verify config directory creation
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_create_wsjtx_config_with_audio_device(self, digital_modes, mock_radio):
        """Test WSJT-X config generation with detected audio device"""
        # Mock audio device detection
        with patch.object(digital_modes, "get_audio_device") as mock_get_audio:
            mock_get_audio.return_value = {
                "card": "1",
                "device": "0",
                "name": "USB Audio CODEC",
                "alsa_name": "plughw:1,0",
            }

            with patch("builtins.open", mock_open()) as mock_file:
                with patch("pathlib.Path.home", return_value=Path("/home/test")):
                    with patch("pathlib.Path.mkdir"):
                        config_path = digital_modes.create_wsjtx_config(
                            "KO4TUV", "EM75"
                        )

                        assert config_path is not None
                        mock_get_audio.assert_called_once()

    def test_menu_item_setting(self, digital_modes, mock_radio):
        """Test internal menu item setting method"""
        mock_radio._send_command.return_value = "OK"

        result = digital_modes._set_menu_item("050", "040")

        assert result is True
        mock_radio._send_command.assert_called_with("EX050040;")

    def test_menu_item_setting_failure(self, digital_modes, mock_radio):
        """Test menu item setting when command fails"""
        mock_radio._send_command.return_value = None

        result = digital_modes._set_menu_item("050", "040")
        assert result is False

    def test_get_digital_status(self, digital_modes, mock_radio):
        """Test digital status reporting"""
        # Mock radio status for 20m FT8
        status = RadioStatus(
            frequency_a=14074000,
            frequency_b=14074000,
            mode="DATA_USB",
            tx_active=False,
            squelch_open=False,
            s_meter=75,
            power_output=25.0,
            swr=1.2,
        )
        mock_radio.get_status.return_value = status

        # Mock audio device
        with patch.object(digital_modes, "get_audio_device") as mock_get_audio:
            mock_get_audio.return_value = {"name": "USB Audio CODEC"}

            digital_status = digital_modes.get_digital_status()

            assert digital_status["frequency"] == 14074000
            assert digital_status["mode"] == "DATA_USB"
            assert digital_status["is_digital"] is True
            assert digital_status["likely_digital_mode"] == "FT8 (20m)"
            assert digital_status["power"] == 25.0
            assert digital_status["tx_active"] is False
            assert digital_status["s_meter"] == 75

    def test_get_digital_status_failure(self, digital_modes, mock_radio):
        """Test digital status when radio status fails"""
        mock_radio.get_status.return_value = None

        digital_status = digital_modes.get_digital_status()
        assert digital_status == {}

    def test_frequency_constants(self):
        """Test that frequency constants are correctly defined"""
        # Test FT8 frequencies
        assert DigitalModes.FT8_FREQUENCIES["20m"] == 14074000
        assert DigitalModes.FT8_FREQUENCIES["40m"] == 7074000
        assert DigitalModes.FT8_FREQUENCIES["80m"] == 3573000

        # Test FT4 frequencies
        assert DigitalModes.FT4_FREQUENCIES["20m"] == 14080000
        assert DigitalModes.FT4_FREQUENCIES["40m"] == 7047500

        # Test JS8 frequencies
        assert DigitalModes.JS8_FREQUENCIES["20m"] == 14078000
        assert DigitalModes.JS8_FREQUENCIES["40m"] == 7078000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
