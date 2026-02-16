#!/usr/bin/env python3
"""
Yaesu FT-991A CAT Control Library
==================================
Full CAT (Computer Aided Transceiver) control over USB serial.
Protocol: ASCII commands terminated with ';'
Baud: 38400 (configurable, must match radio menu item 031)

Reference: FT-991A CAT Operation Reference Manual (Yaesu 1711-D)
"""

import serial
import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Mode(Enum):
    """Operating modes (MD command parameter)"""
    LSB = "1"
    USB = "2"
    CW = "3"
    FM = "4"
    AM = "5"
    RTTY_LSB = "6"
    CW_R = "7"
    DATA_LSB = "8"       # Digital modes (FT8, etc.)
    RTTY_USB = "9"
    DATA_FM = "A"
    FM_N = "B"
    DATA_USB = "C"       # Digital modes (FT8, etc.)
    AM_N = "D"
    C4FM = "E"


class Band(Enum):
    """Common amateur bands with typical frequencies (Hz)"""
    HF_160M = 1_800_000
    HF_80M = 3_500_000
    HF_60M = 5_330_500
    HF_40M = 7_000_000
    HF_30M = 10_100_000
    HF_20M = 14_000_000
    HF_17M = 18_068_000
    HF_15M = 21_000_000
    HF_12M = 24_890_000
    HF_10M = 28_000_000
    VHF_6M = 50_000_000
    VHF_2M = 144_000_000
    UHF_70CM = 420_000_000


@dataclass
class RadioStatus:
    """Current radio state"""
    frequency_a: int      # Hz
    frequency_b: int      # Hz
    mode: str
    tx_active: bool
    squelch_open: bool
    s_meter: int          # 0-255
    power_output: float   # Watts
    swr: float


class FT991A:
    """
    Yaesu FT-991A CAT control interface.
    
    Usage:
        radio = FT991A('/dev/ttyUSB0')
        radio.connect()
        
        # Read current frequency
        freq = radio.get_frequency_a()
        print(f"VFO-A: {freq / 1e6:.6f} MHz")
        
        # Tune to 14.074 MHz (FT8)
        radio.set_frequency_a(14_074_000)
        radio.set_mode(Mode.DATA_USB)
        
        # Monitor S-meter
        level = radio.get_s_meter()
        
        radio.disconnect()
    """

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 38400, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        self._last_cmd_time = 0.0
        self._min_cmd_interval = 0.05  # 50ms between commands

    # ── Connection ──────────────────────────────────────────────

    def connect(self) -> bool:
        """Open serial connection to radio."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=self.timeout,
                rtscts=False,
                dsrdtr=False,
            )
            # Verify connection by reading frequency
            freq = self.get_frequency_a()
            if freq > 0:
                logger.info(f"Connected to FT-991A on {self.port} — VFO-A: {freq/1e6:.6f} MHz")
                return True
            else:
                logger.error("Connected but no response from radio")
                return False
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Disconnected from FT-991A")

    # ── Low-level CAT I/O ──────────────────────────────────────

    def _send(self, command: str) -> str:
        """Send a CAT command and return the response."""
        if not self.serial or not self.serial.is_open:
            raise ConnectionError("Not connected to radio")

        # Rate limiting
        elapsed = time.time() - self._last_cmd_time
        if elapsed < self._min_cmd_interval:
            time.sleep(self._min_cmd_interval - elapsed)

        # Ensure command ends with terminator
        if not command.endswith(';'):
            command += ';'

        logger.debug(f"TX: {command}")
        self.serial.write(command.encode('ascii'))
        self.serial.flush()
        self._last_cmd_time = time.time()

        # Read response (terminated by ';')
        response = b''
        while True:
            byte = self.serial.read(1)
            if not byte:
                break  # Timeout
            response += byte
            if byte == b';':
                break

        decoded = response.decode('ascii', errors='replace')
        logger.debug(f"RX: {decoded}")
        return decoded

    def _set(self, command: str):
        """Send a set command (no response expected)."""
        self._send(command)

    def _read(self, command: str) -> str:
        """Send a read command and return the answer."""
        return self._send(command)

    # ── Frequency Control ──────────────────────────────────────

    def get_frequency_a(self) -> int:
        """Get VFO-A frequency in Hz."""
        resp = self._read("FA;")
        if resp.startswith("FA") and resp.endswith(";"):
            try:
                return int(resp[2:-1])
            except ValueError:
                return 0
        return 0

    def set_frequency_a(self, freq_hz: int):
        """Set VFO-A frequency in Hz. Range: 30 kHz - 470 MHz."""
        self._set(f"FA{freq_hz:09d};")

    def get_frequency_b(self) -> int:
        """Get VFO-B frequency in Hz."""
        resp = self._read("FB;")
        if resp.startswith("FB") and resp.endswith(";"):
            try:
                return int(resp[2:-1])
            except ValueError:
                return 0
        return 0

    def set_frequency_b(self, freq_hz: int):
        """Set VFO-B frequency in Hz."""
        self._set(f"FB{freq_hz:09d};")

    # ── Mode Control ───────────────────────────────────────────

    def get_mode(self) -> str:
        """Get current operating mode."""
        resp = self._read("MD0;")
        if resp.startswith("MD0") and resp.endswith(";"):
            code = resp[3:-1]
            for mode in Mode:
                if mode.value == code:
                    return mode.name
            return f"UNKNOWN({code})"
        return "UNKNOWN"

    def set_mode(self, mode: Mode):
        """Set operating mode."""
        self._set(f"MD0{mode.value};")

    # ── Transmit Control ───────────────────────────────────────

    def ptt_on(self):
        """Key the transmitter (PTT on). CAUTION: Transmits RF!"""
        logger.warning("PTT ON — transmitting!")
        self._set("TX1;")

    def ptt_off(self):
        """Unkey the transmitter (PTT off)."""
        self._set("TX0;")

    def is_transmitting(self) -> bool:
        """Check if radio is currently transmitting."""
        resp = self._read("TX;")
        if resp.startswith("TX") and resp.endswith(";"):
            return resp[2:-1] != "0"
        return False

    # ── Meter Reading ──────────────────────────────────────────

    def get_s_meter(self) -> int:
        """Read S-meter value (0-255)."""
        resp = self._read("SM0;")
        if resp.startswith("SM0") and resp.endswith(";"):
            try:
                return int(resp[3:-1])
            except ValueError:
                return 0
        return 0

    def get_power_meter(self) -> int:
        """Read power output meter (0-255)."""
        resp = self._read("RM1;")
        if resp.startswith("RM1") and resp.endswith(";"):
            try:
                return int(resp[3:-1])
            except ValueError:
                return 0
        return 0

    def get_swr_meter(self) -> int:
        """Read SWR meter (0-255)."""
        resp = self._read("RM2;")
        if resp.startswith("RM2") and resp.endswith(";"):
            try:
                return int(resp[3:-1])
            except ValueError:
                return 0
        return 0

    # ── Power & RF ─────────────────────────────────────────────

    def get_power_level(self) -> int:
        """Get RF power output setting (0-100 watts)."""
        resp = self._read("PC;")
        if resp.startswith("PC") and resp.endswith(";"):
            try:
                return int(resp[2:-1])
            except ValueError:
                return 0
        return 0

    def set_power_level(self, watts: int):
        """Set RF power output (5-100 watts HF, 5-50 watts VHF/UHF)."""
        watts = max(5, min(100, watts))
        self._set(f"PC{watts:03d};")

    # ── VFO & Memory ──────────────────────────────────────────

    def swap_vfo(self):
        """Swap VFO-A and VFO-B."""
        self._set("SV;")

    def vfo_a_to_b(self):
        """Copy VFO-A to VFO-B."""
        self._set("AB;")

    # ── Band Selection ────────────────────────────────────────

    def set_band(self, band: Band):
        """Tune to a band's base frequency."""
        self.set_frequency_a(band.value)

    # ── Squelch ───────────────────────────────────────────────

    def get_squelch_status(self) -> bool:
        """Check if squelch is open (signal present)."""
        # Use IF command to check receiver status
        resp = self._read("IF;")
        if len(resp) >= 28:
            # Byte 23 is squelch status: 0=closed, 1=open
            try:
                return resp[23] == '1'
            except (IndexError, ValueError):
                return False
        return False

    # ── Information ───────────────────────────────────────────

    def get_info(self) -> str:
        """Get full IF (Information) response — comprehensive radio state."""
        return self._read("IF;")

    def get_id(self) -> str:
        """Get radio model identification."""
        resp = self._read("ID;")
        return resp

    # ── Convenience ───────────────────────────────────────────

    def tune_ft8(self, band_mhz: float = 14.074):
        """Quick tune to FT8 frequency on a given band."""
        freq_hz = int(band_mhz * 1_000_000)
        self.set_frequency_a(freq_hz)
        self.set_mode(Mode.DATA_USB)
        logger.info(f"Tuned to FT8 on {band_mhz:.3f} MHz")

    def tune_fm_repeater(self, freq_mhz: float, offset_mhz: float = 0.6):
        """Tune to FM repeater with offset."""
        freq_hz = int(freq_mhz * 1_000_000)
        self.set_frequency_a(freq_hz)
        self.set_mode(Mode.FM)
        # Set repeater offset on VFO-B
        offset_hz = int((freq_mhz - offset_mhz) * 1_000_000)
        self.set_frequency_b(offset_hz)
        logger.info(f"Tuned to repeater {freq_mhz:.4f} MHz, offset -{offset_mhz} MHz")

    def get_status(self) -> RadioStatus:
        """Get comprehensive radio status."""
        return RadioStatus(
            frequency_a=self.get_frequency_a(),
            frequency_b=self.get_frequency_b(),
            mode=self.get_mode(),
            tx_active=self.is_transmitting(),
            squelch_open=self.get_squelch_status(),
            s_meter=self.get_s_meter(),
            power_output=self.get_power_level(),
            swr=self.get_swr_meter(),
        )

    # ── Context Manager ───────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        # Safety: ensure PTT is off
        try:
            self.ptt_off()
        except Exception:
            pass
        self.disconnect()


# ── FT8 Common Frequencies ─────────────────────────────────────

FT8_FREQUENCIES = {
    "160m": 1_840_000,
    "80m": 3_573_000,
    "60m": 5_357_000,
    "40m": 7_074_000,
    "30m": 10_136_000,
    "20m": 14_074_000,
    "17m": 18_100_000,
    "15m": 21_074_000,
    "12m": 24_915_000,
    "10m": 28_074_000,
    "6m": 50_313_000,
    "2m": 144_174_000,
}


# ── CLI ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="FT-991A CAT Control")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=38400, help="Baud rate")
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "freq", "mode", "ft8", "bands", "raw"],
                        help="Command to execute")
    parser.add_argument("--set", help="Value to set (frequency in Hz, mode name, etc.)")
    parser.add_argument("--raw", help="Raw CAT command to send")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s: %(message)s")

    with FT991A(args.port, args.baud) as radio:
        if args.command == "status":
            status = radio.get_status()
            print(f"📻 FT-991A Status")
            print(f"  VFO-A: {status.frequency_a / 1e6:.6f} MHz")
            print(f"  VFO-B: {status.frequency_b / 1e6:.6f} MHz")
            print(f"  Mode:  {status.mode}")
            print(f"  TX:    {'🔴 ON' if status.tx_active else '⚪ OFF'}")
            print(f"  SQL:   {'🟢 Open' if status.squelch_open else '🔴 Closed'}")
            print(f"  S:     {status.s_meter}")
            print(f"  Power: {status.power_output}W")

        elif args.command == "freq":
            if args.set:
                freq = int(float(args.set) * 1_000_000) if '.' in args.set else int(args.set)
                radio.set_frequency_a(freq)
                print(f"Set VFO-A to {freq / 1e6:.6f} MHz")
            else:
                freq = radio.get_frequency_a()
                print(f"{freq / 1e6:.6f} MHz")

        elif args.command == "ft8":
            band = args.set or "20m"
            freq = FT8_FREQUENCIES.get(band, 14_074_000)
            radio.set_frequency_a(freq)
            radio.set_mode(Mode.DATA_USB)
            print(f"🎵 FT8 on {band}: {freq / 1e6:.6f} MHz (DATA-USB)")

        elif args.command == "bands":
            print("📡 FT8 Frequencies:")
            for band, freq in FT8_FREQUENCIES.items():
                print(f"  {band:>4s}: {freq / 1e6:.6f} MHz")

        elif args.command == "raw":
            if args.raw:
                resp = radio._send(args.raw)
                print(f"Response: {resp}")
            else:
                print("Use --raw 'FA;' to send raw CAT commands")


if __name__ == "__main__":
    main()
