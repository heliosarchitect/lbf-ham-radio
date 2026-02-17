#!/usr/bin/env python3
"""
FT-991A Digital Modes Support
============================
Configure FT-991A for popular digital modes like FT8, FT4, and JS8Call.
Handles CAT configuration, audio device detection, and external software setup.

External Software Dependencies:
- WSJT-X: Required for FT8 and FT4 operation
- JS8Call: Required for JS8Call digital mode
- ALSA/PulseAudio: Linux audio system integration

Hardware Requirements:
- USB CAT interface (CP2105 dual UART)
- USB audio interface (PCM2903B CODEC recommended)
"""

import logging
import re
import subprocess
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Optional

from .cat import FT991A, Mode

logger = logging.getLogger(__name__)


class DigitalModes:
    """
    Digital mode configuration and control for FT-991A.

    Usage:
        radio = FT991A('/dev/ttyUSB0')
        radio.connect()

        digital = DigitalModes(radio)
        digital.setup_ft8(frequency=14074000)  # FT8 on 20m

        # Verify audio device is available
        device = digital.get_audio_device()
        if device:
            print(f"Audio device: {device}")
    """

    # Common digital mode frequencies (Hz)
    FT8_FREQUENCIES = {
        "160m": 1840000,
        "80m": 3573000,
        "60m": 5357000,
        "40m": 7074000,
        "30m": 10136000,
        "20m": 14074000,
        "17m": 18100000,
        "15m": 21074000,
        "12m": 24915000,
        "10m": 28074000,
        "6m": 50313000,
    }

    FT4_FREQUENCIES = {
        "160m": 1840000,
        "80m": 3575000,
        "60m": 5357000,
        "40m": 7047500,
        "30m": 10140000,
        "20m": 14080000,
        "17m": 18104000,
        "15m": 21140000,
        "12m": 24919000,
        "10m": 28180000,
        "6m": 50318000,
    }

    JS8_FREQUENCIES = {
        "160m": 1842000,
        "80m": 3578000,
        "60m": 5357000,
        "40m": 7078000,
        "30m": 10130000,
        "20m": 14078000,
        "17m": 18104000,
        "15m": 21078000,
        "12m": 24922000,
        "10m": 28078000,
        "6m": 50318000,
    }

    def __init__(self, radio: FT991A):
        """
        Initialize digital modes controller.

        Args:
            radio: Connected FT991A instance
        """
        self.radio = radio
        if not radio.serial or not radio.serial.is_open:
            raise ValueError("Radio must be connected before initializing digital modes")

    def setup_ft8(self, frequency: Optional[int] = None, band: Optional[str] = None) -> bool:
        """
        Configure radio for FT8 operation.

        FT8 Configuration:
        - Mode: DATA-USB (upper sideband data)
        - Audio levels: TX audio gain ~30-50%, ALC ~25%
        - Power: Typically 25-50W (adjust per band conditions)
        - Bandwidth: 2500 Hz (radio default for DATA-USB)

        Args:
            frequency: Specific frequency in Hz (overrides band)
            band: Amateur band (e.g., "20m", "40m")

        Returns:
            bool: True if configuration successful
        """
        logger.info("Configuring FT-991A for FT8")

        try:
            # Determine frequency
            if frequency:
                target_freq = frequency
            elif band and band in self.FT8_FREQUENCIES:
                target_freq = self.FT8_FREQUENCIES[band]
            else:
                target_freq = self.FT8_FREQUENCIES["20m"]  # Default to 20m
                logger.info("No frequency/band specified, defaulting to 20m FT8")

            # Set frequency
            if not self.radio.set_frequency_a(target_freq):
                logger.error("Failed to set FT8 frequency")
                return False

            # Set DATA-USB mode
            if not self.radio.set_mode(Mode.DATA_USB):
                logger.error("Failed to set DATA-USB mode")
                return False

            # Configure audio levels for FT8
            # TX Audio Gain: ~40% (menu item 050)
            # ALC: ~25% for clean transmission (menu item 051)
            self._set_menu_item("050", "040")  # TX Audio Gain 40%
            self._set_menu_item("051", "025")  # ALC 25%

            # Set power to reasonable level for FT8 (typically 25-40W)
            self.radio.set_power_level(25)

            logger.info(f"FT8 configured: {target_freq/1e6:.3f} MHz, DATA-USB, 25W")
            return True

        except Exception as e:
            logger.error(f"FT8 setup failed: {e}")
            return False

    def setup_ft4(self, frequency: Optional[int] = None, band: Optional[str] = None) -> bool:
        """
        Configure radio for FT4 operation.

        FT4 is similar to FT8 but faster (7.5s vs 15s cycles).
        Uses same basic radio configuration as FT8.

        Args:
            frequency: Specific frequency in Hz (overrides band)
            band: Amateur band (e.g., "20m", "40m")

        Returns:
            bool: True if configuration successful
        """
        logger.info("Configuring FT-991A for FT4")

        try:
            # Determine frequency
            if frequency:
                target_freq = frequency
            elif band and band in self.FT4_FREQUENCIES:
                target_freq = self.FT4_FREQUENCIES[band]
            else:
                target_freq = self.FT4_FREQUENCIES["20m"]  # Default to 20m
                logger.info("No frequency/band specified, defaulting to 20m FT4")

            # Set frequency
            if not self.radio.set_frequency_a(target_freq):
                logger.error("Failed to set FT4 frequency")
                return False

            # Set DATA-USB mode
            if not self.radio.set_mode(Mode.DATA_USB):
                logger.error("Failed to set DATA-USB mode")
                return False

            # Configure audio levels (same as FT8)
            self._set_menu_item("050", "040")  # TX Audio Gain 40%
            self._set_menu_item("051", "025")  # ALC 25%

            # Set power to reasonable level
            self.radio.set_power_level(25)

            logger.info(f"FT4 configured: {target_freq/1e6:.3f} MHz, DATA-USB, 25W")
            return True

        except Exception as e:
            logger.error(f"FT4 setup failed: {e}")
            return False

    def setup_js8call(self, frequency: Optional[int] = None, band: Optional[str] = None) -> bool:
        """
        Configure radio for JS8Call operation.

        JS8Call is a keyboard-to-keyboard digital mode derived from FT8.
        Uses wider bandwidth and longer transmission periods.

        Args:
            frequency: Specific frequency in Hz (overrides band)
            band: Amateur band (e.g., "20m", "40m")

        Returns:
            bool: True if configuration successful
        """
        logger.info("Configuring FT-991A for JS8Call")

        try:
            # Determine frequency
            if frequency:
                target_freq = frequency
            elif band and band in self.JS8_FREQUENCIES:
                target_freq = self.JS8_FREQUENCIES[band]
            else:
                target_freq = self.JS8_FREQUENCIES["20m"]  # Default to 20m
                logger.info("No frequency/band specified, defaulting to 20m JS8Call")

            # Set frequency
            if not self.radio.set_frequency_a(target_freq):
                logger.error("Failed to set JS8Call frequency")
                return False

            # Set DATA-USB mode
            if not self.radio.set_mode(Mode.DATA_USB):
                logger.error("Failed to set DATA-USB mode")
                return False

            # Configure audio levels (similar to FT8 but may need adjustment)
            self._set_menu_item("050", "035")  # TX Audio Gain 35% (slightly lower)
            self._set_menu_item("051", "020")  # ALC 20%

            # Set power (JS8Call can use lower power effectively)
            self.radio.set_power_level(20)

            logger.info(f"JS8Call configured: {target_freq/1e6:.3f} MHz, DATA-USB, 20W")
            return True

        except Exception as e:
            logger.error(f"JS8Call setup failed: {e}")
            return False

    def get_audio_device(self) -> Optional[Dict[str, str]]:
        """
        Detect PCM2903B USB audio CODEC on the system.

        The PCM2903B shows up as a USB audio device in ALSA.
        Common names: "USB Audio CODEC", "C-Media USB Audio Device"

        Returns:
            dict: Audio device info with 'card', 'device', 'name' keys, or None
        """
        try:
            # Method 1: Check /proc/asound/cards for USB audio devices
            cards_file = Path("/proc/asound/cards")
            if cards_file.exists():
                content = cards_file.read_text()

                # Look for USB audio devices (PCM2903B typically shows as "USB Audio CODEC")
                for line in content.split("\n"):
                    if "USB" in line and ("Audio" in line or "CODEC" in line):
                        # Parse card number and name
                        match = re.match(r"\s*(\d+)\s+\[([^\]]+)\]\s*:\s*(.+)", line)
                        if match:
                            card_num, card_id, card_name = match.groups()

                            # Check if this looks like PCM2903B
                            if any(keyword in card_name.upper() for keyword in ["USB AUDIO", "PCM2903", "C-MEDIA"]):
                                logger.info(f"Found USB audio device: {card_name} (card {card_num})")
                                return {
                                    "card": card_num,
                                    "device": "0",  # Usually device 0
                                    "name": card_name.strip(),
                                    "alsa_name": f"plughw:{card_num},0",
                                    "pulse_name": f"alsa_input.usb-*_{card_id}*",
                                }

            # Method 2: Use arecord to list capture devices
            try:
                result = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "USB" in line and ("Audio" in line or "CODEC" in line):
                            # Parse: card 1: CODEC [USB Audio CODEC], device 0: USB Audio [USB Audio]
                            match = re.search(r"card\s+(\d+):\s+(\w+)\s+\[([^\]]+)\].*device\s+(\d+)", line)
                            if match:
                                card_num, card_id, card_name, device_num = match.groups()
                                logger.info(f"Found audio device via arecord: {card_name} (card {card_num})")
                                return {
                                    "card": card_num,
                                    "device": device_num,
                                    "name": card_name,
                                    "alsa_name": f"plughw:{card_num},{device_num}",
                                    "pulse_name": f"alsa_input.usb-*_{card_id}*",
                                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.debug("arecord command not available or timed out")

            # Method 3: Check PulseAudio sources
            try:
                result = subprocess.run(
                    ["pactl", "list", "short", "sources"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "usb" in line.lower() and ("audio" in line.lower() or "codec" in line.lower()):
                            parts = line.split("\t")
                            if len(parts) >= 2:
                                source_name = parts[1]
                                logger.info(f"Found PulseAudio USB source: {source_name}")
                                return {
                                    "card": "unknown",
                                    "device": "unknown",
                                    "name": "USB Audio Device (PulseAudio)",
                                    "alsa_name": "default",
                                    "pulse_name": source_name,
                                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.debug("PulseAudio pactl command not available or timed out")

            logger.warning("No PCM2903B or compatible USB audio device found")
            return None

        except Exception as e:
            logger.error(f"Audio device detection failed: {e}")
            return None

    def create_wsjtx_config(self, callsign: str, grid_square: str = "GRID") -> Optional[str]:
        """
        Generate a WSJT-X configuration file with proper CAT and audio settings.

        WSJT-X stores configuration in ~/.config/WSJT-X/WSJT-X.ini
        This creates a template configuration pointing to the FT-991A CAT port
        and detected audio device.

        Args:
            callsign: Amateur radio callsign (e.g., "KO4TUV")
            grid_square: Maidenhead grid locator (e.g., "EM75", leave as "GRID" for placeholder)

        Returns:
            str: Path to created config file, or None on failure
        """
        try:
            # Get audio device info
            audio_device = self.get_audio_device()
            if not audio_device:
                logger.warning("No audio device detected - config will use default")
                audio_input = "default"
                audio_output = "default"
            else:
                # Use ALSA device names for WSJT-X
                audio_input = audio_device["alsa_name"]
                audio_output = audio_device["alsa_name"]

            # WSJT-X configuration template
            config = ConfigParser()
            config.optionxform = str  # Preserve case for keys

            # Main configuration section
            config["Configuration"] = {
                # Station info
                "MyCall": callsign.upper(),
                "MyGrid": grid_square.upper(),
                # Audio settings
                "SoundInName": audio_input,
                "SoundOutName": audio_output,
                "AudioInputDevice": audio_input,
                "AudioOutputDevice": audio_output,
                # CAT settings for FT-991A
                "CATPortName": self.radio.port,
                "CATSerialRate": str(self.radio.baudrate),
                "CATDataBits": "8",
                "CATStopBits": "2",
                "CATParity": "None",
                "CATHandshake": "None",
                "CATPolling": "true",
                "CATPTTEnabled": "true",
                "CATRTSEnabled": "false",
                "CATDTREnabled": "false",
                "RigName": "Yaesu FT-991A",
                "PTTport": self.radio.port,
                "PTTMethod": "0",  # CAT
                # Digital mode settings
                "TxMode": "1",  # USB
                "Data": "1",  # Data mode
                "TxPower": "25",
                "TuneSteps": "5",
                # Other settings
                "DecodeHighlighting": "true",
                "IncludeBlankLine": "false",
                "DeepSearchEnabled": "true",
                "LogQSOEnabled": "true",
                "AutoLogEnabled": "false",
                "EnableVHFContesting": "false",
                "UseUTC": "true",
            }

            # Write to temporary file (user should copy to proper location)
            config_dir = Path.home() / ".config" / "WSJT-X"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "WSJT-X.ini"

            with open(config_file, "w") as f:
                config.write(f)

            logger.info(f"WSJT-X config created: {config_file}")
            logger.info(f"Callsign: {callsign}, Grid: {grid_square}")
            logger.info(f"Audio: {audio_input}")
            logger.info(f"CAT: {self.radio.port} @ {self.radio.baudrate}")

            return str(config_file)

        except Exception as e:
            logger.error(f"WSJT-X config creation failed: {e}")
            return None

    def _set_menu_item(self, item: str, value: str) -> bool:
        """
        Set FT-991A menu item via CAT command.

        Uses EX command: EXnnn<value>; where nnn is 3-digit menu item.

        Args:
            item: 3-digit menu item number (e.g., "050")
            value: Value to set (format depends on menu item)

        Returns:
            bool: True if command successful
        """
        try:
            # Ensure 3-digit format
            item = item.zfill(3)
            command = f"EX{item}{value};"

            response = self.radio._send_command(command)
            success = response is not None

            if success:
                logger.debug(f"Set menu item {item} = {value}")
            else:
                logger.warning(f"Failed to set menu item {item} = {value}")

            return success

        except Exception as e:
            logger.error(f"Menu item {item} set failed: {e}")
            return False

    def get_digital_status(self) -> Dict[str, any]:
        """
        Get current radio status relevant to digital modes.

        Returns:
            dict: Status information including frequency, mode, power, etc.
        """
        try:
            status = self.radio.get_status()
            if not status:
                return {}

            # Check if we're in a digital mode
            is_digital = status.mode in ["DATA_USB", "DATA_LSB", "DATA_FM"]

            # Determine likely digital mode based on frequency
            freq = status.frequency_a
            likely_mode = None

            for band, ft8_freq in self.FT8_FREQUENCIES.items():
                if abs(freq - ft8_freq) < 1000:  # Within 1 kHz
                    likely_mode = f"FT8 ({band})"
                    break

            if not likely_mode:
                for band, ft4_freq in self.FT4_FREQUENCIES.items():
                    if abs(freq - ft4_freq) < 1000:
                        likely_mode = f"FT4 ({band})"
                        break

            if not likely_mode:
                for band, js8_freq in self.JS8_FREQUENCIES.items():
                    if abs(freq - js8_freq) < 1000:
                        likely_mode = f"JS8Call ({band})"
                        break

            return {
                "frequency": freq,
                "mode": status.mode,
                "is_digital": is_digital,
                "likely_digital_mode": likely_mode,
                "power": status.power_output,
                "tx_active": status.tx_active,
                "s_meter": status.s_meter,
                "audio_device": self.get_audio_device(),
            }

        except Exception as e:
            logger.error(f"Digital status check failed: {e}")
            return {}
