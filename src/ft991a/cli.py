#!/usr/bin/env python3
"""
FT-991A Command Line Interface
==============================
Direct CAT command interface for Yaesu FT-991A transceiver control.

Entry points:
- ft991a-web: Launch the web GUI server
- ft991a-cli: Direct CAT commands from terminal
- ft991a-mcp: Launch MCP server (stdio transport)
"""

import argparse
import asyncio
import logging
import sys

import uvicorn

from .cat import FT991A, Mode
from .mcp import run_server

# Optional modules — imported at use-time to avoid hard dependency failures
try:
    from .cw import CWKeyer, morse_to_text, text_to_morse  # noqa: F401
except ImportError:
    text_to_morse = morse_to_text = CWKeyer = None  # type: ignore

try:
    from .broadcast import (  # noqa: F401
        AudioDeviceError,
        Broadcaster,
        BroadcastError,
        TTSError,
    )
except ImportError:
    Broadcaster = AudioDeviceError = BroadcastError = TTSError = None  # type: ignore

try:
    from .digital import DigitalModes  # noqa: F401
except ImportError:
    DigitalModes = None  # type: ignore

try:
    from .scanner import BandScanner  # noqa: F401
except ImportError:
    BandScanner = None  # type: ignore

try:
    from .aprs import APRSClient, EmergencyKit  # noqa: F401
except ImportError:
    APRSClient = EmergencyKit = None  # type: ignore
# from .aprs import APRSClient, EmergencyKit
# from .broadcast import Broadcaster, BroadcastError, AudioDeviceError, TTSError
# from .scanner import BandScanner


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )


def web_server_main():
    """Entry point for ft991a-web command"""
    parser = argparse.ArgumentParser(description="FT-991A Web GUI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument(
        "--radio-port", default="/dev/ttyUSB0", help="Radio serial port"
    )
    parser.add_argument("--radio-baud", type=int, default=38400, help="Radio baud rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Import and configure the web server
    from .web import radio_config

    # Pass CLI args to web module config
    radio_config["port"] = args.radio_port
    radio_config["baudrate"] = args.radio_baud

    print(f"Starting FT-991A Web GUI on http://{args.host}:{args.port}")
    print(f"Radio: {args.radio_port} @ {args.radio_baud} baud")

    uvicorn.run(
        "ft991a.web:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info" if not args.verbose else "debug",
    )


def cli_main():
    """Entry point for ft991a-cli command"""
    parser = argparse.ArgumentParser(description="FT-991A CAT Control CLI")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=38400, help="Baud rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # Command subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get radio status")

    # Frequency commands
    freq_parser = subparsers.add_parser("freq", help="Frequency control")
    freq_subparsers = freq_parser.add_subparsers(dest="freq_action")
    freq_subparsers.add_parser("get", help="Get current frequency")
    freq_set_parser = freq_subparsers.add_parser("set", help="Set frequency")
    freq_set_parser.add_argument("frequency", type=int, help="Frequency in Hz")

    # Mode commands
    mode_parser = subparsers.add_parser("mode", help="Mode control")
    mode_subparsers = mode_parser.add_subparsers(dest="mode_action")
    mode_subparsers.add_parser("get", help="Get current mode")
    mode_set_parser = mode_subparsers.add_parser("set", help="Set mode")
    mode_set_parser.add_argument(
        "mode", choices=[m.name for m in Mode], help="Operating mode"
    )

    # Power commands
    power_parser = subparsers.add_parser("power", help="Power control")
    power_subparsers = power_parser.add_subparsers(dest="power_action")
    power_subparsers.add_parser("get", help="Get current power")
    power_set_parser = power_subparsers.add_parser("set", help="Set power")
    power_set_parser.add_argument("watts", type=int, help="Power in watts (5-100)")

    # PTT commands
    ptt_parser = subparsers.add_parser("ptt", help="PTT control")
    ptt_subparsers = ptt_parser.add_subparsers(dest="ptt_action")
    ptt_subparsers.add_parser("on", help="Key transmitter")
    ptt_subparsers.add_parser("off", help="Unkey transmitter")

    # S-meter command
    smeter_parser = subparsers.add_parser("smeter", help="Get S-meter reading")

    # Band command
    band_parser = subparsers.add_parser("band", help="Band control")
    band_parser.add_argument(
        "band",
        choices=["160M", "80M", "60M", "40M", "30M", "20M", "17M", "15M", "12M", "10M"],
        help="Amateur band",
    )

    # CW commands
    cw_parser = subparsers.add_parser("cw", help="CW (Morse code) operations")
    cw_subparsers = cw_parser.add_subparsers(dest="cw_action", help="CW operations")

    # CW encode
    cw_encode_parser = cw_subparsers.add_parser(
        "encode", help="Convert text to Morse code"
    )
    cw_encode_parser.add_argument("message", help="Text message to encode")

    # CW decode
    cw_decode_parser = cw_subparsers.add_parser(
        "decode", help="Convert Morse code to text"
    )
    cw_decode_parser.add_argument("morse", help="Morse code to decode (dots/dashes)")

    # CW send (requires confirmation)
    cw_send_parser = cw_subparsers.add_parser(
        "send", help="Key CW message via radio (REQUIRES LICENSE)"
    )
    cw_send_parser.add_argument("message", help="Text message to send in CW")
    cw_send_parser.add_argument(
        "--wpm", type=int, default=20, help="Words per minute (5-40, default: 20)"
    )
    cw_send_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required confirmation flag (acknowledges licensed operator present)",
    )

    # CW listen (placeholder)
    cw_listen_parser = cw_subparsers.add_parser(
        "listen", help="Listen for CW signals (placeholder)"
    )

    # Broadcast commands (TTS-to-radio)
    broadcast_parser = subparsers.add_parser(
        "broadcast", help="TTS-to-radio broadcast operations (REQUIRES LICENSE)"
    )
    broadcast_subparsers = broadcast_parser.add_subparsers(
        dest="broadcast_action", help="Broadcast operations"
    )

    # Broadcast say
    broadcast_say_parser = broadcast_subparsers.add_parser(
        "say", help="Broadcast text message via TTS (REQUIRES LICENSE)"
    )
    broadcast_say_parser.add_argument("message", help="Text message to broadcast")
    broadcast_say_parser.add_argument(
        "--voice", default="default", help="TTS voice selection"
    )
    broadcast_say_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required confirmation flag (acknowledges licensed operator KO4TUV present)",
    )

    # Broadcast record
    broadcast_record_parser = broadcast_subparsers.add_parser(
        "record", help="Record audio from radio"
    )
    broadcast_record_parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Recording duration in seconds (1-300)",
    )
    broadcast_record_parser.add_argument(
        "--output", help="Output WAV file path (default: temp file)"
    )

    # Broadcast devices
    broadcast_devices_parser = broadcast_subparsers.add_parser(
        "devices", help="List available audio devices"
    )

    # Broadcast test
    broadcast_test_parser = broadcast_subparsers.add_parser(
        "test", help="Test TTS without transmitting"
    )
    broadcast_test_parser.add_argument("message", help="Text message to test")
    broadcast_test_parser.add_argument(
        "--voice", default="default", help="TTS voice selection"
    )

    # Digital modes commands
    digital_parser = subparsers.add_parser(
        "digital", help="Digital mode operations (FT8, FT4, JS8Call)"
    )
    digital_subparsers = digital_parser.add_subparsers(
        dest="digital_action", help="Digital mode operations"
    )

    # Digital setup commands
    digital_ft8_parser = digital_subparsers.add_parser(
        "setup-ft8", help="Configure radio for FT8"
    )
    digital_ft8_parser.add_argument("--freq", type=int, help="Specific frequency in Hz")
    digital_ft8_parser.add_argument(
        "--band",
        choices=[
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
            "6m",
        ],
        help="Amateur band (default: 20m)",
    )

    digital_ft4_parser = digital_subparsers.add_parser(
        "setup-ft4", help="Configure radio for FT4"
    )
    digital_ft4_parser.add_argument("--freq", type=int, help="Specific frequency in Hz")
    digital_ft4_parser.add_argument(
        "--band",
        choices=[
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
            "6m",
        ],
        help="Amateur band (default: 20m)",
    )

    digital_js8_parser = digital_subparsers.add_parser(
        "setup-js8", help="Configure radio for JS8Call"
    )
    digital_js8_parser.add_argument("--freq", type=int, help="Specific frequency in Hz")
    digital_js8_parser.add_argument(
        "--band",
        choices=[
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
            "6m",
        ],
        help="Amateur band (default: 20m)",
    )

    # Digital audio check
    digital_audio_parser = digital_subparsers.add_parser(
        "audio-check", help="Detect and verify PCM2903B audio device"
    )

    # Digital status
    digital_status_parser = digital_subparsers.add_parser(
        "status", help="Show digital mode status"
    )

    # Digital WSJT-X config
    digital_config_parser = digital_subparsers.add_parser(
        "wsjtx-config", help="Generate WSJT-X configuration"
    )
    digital_config_parser.add_argument(
        "--callsign", default="KO4TUV", help="Amateur radio callsign"
    )
    digital_config_parser.add_argument(
        "--grid", default="GRID", help="Maidenhead grid square"
    )

    # Scanner commands
    scan_parser = subparsers.add_parser("scan", help="Band scanning operations")
    scan_subparsers = scan_parser.add_subparsers(
        dest="scan_action", help="Scanner operations"
    )

    # Scan band
    scan_band_parser = scan_subparsers.add_parser("band", help="Scan frequency band")
    scan_band_parser.add_argument(
        "--start", type=int, required=True, help="Start frequency in Hz"
    )
    scan_band_parser.add_argument(
        "--end", type=int, required=True, help="End frequency in Hz"
    )
    scan_band_parser.add_argument(
        "--step", type=int, required=True, help="Step size in Hz"
    )
    scan_band_parser.add_argument(
        "--dwell", type=int, default=150, help="Dwell time per frequency in ms"
    )

    # Scan activity
    scan_activity_parser = scan_subparsers.add_parser(
        "activity", help="Find active frequencies"
    )
    scan_activity_parser.add_argument(
        "--threshold", type=int, default=50, help="S-meter threshold (0-255)"
    )

    # Scan fine
    scan_fine_parser = scan_subparsers.add_parser(
        "fine", help="Fine scan around frequency"
    )
    scan_fine_parser.add_argument(
        "--freq", type=int, required=True, help="Center frequency in Hz"
    )
    scan_fine_parser.add_argument(
        "--width", type=int, default=20000, help="Scan width in Hz"
    )
    scan_fine_parser.add_argument(
        "--step", type=int, default=1000, help="Step size in Hz"
    )

    # Scan HF
    scan_hf_parser = scan_subparsers.add_parser("hf", help="Scan all HF amateur bands")

    # APRS commands
    aprs_parser = subparsers.add_parser(
        "aprs", help="APRS (Automatic Packet Reporting System) operations"
    )
    aprs_subparsers = aprs_parser.add_subparsers(
        dest="aprs_action", help="APRS operations"
    )

    # APRS setup
    aprs_setup_parser = aprs_subparsers.add_parser(
        "setup", help="Configure radio for APRS (144.390 MHz FM)"
    )

    # APRS beacon
    aprs_beacon_parser = aprs_subparsers.add_parser(
        "beacon", help="Send APRS position beacon (REQUIRES LICENSE)"
    )
    aprs_beacon_parser.add_argument(
        "--lat", type=float, required=True, help="Latitude in decimal degrees"
    )
    aprs_beacon_parser.add_argument(
        "--lon", type=float, required=True, help="Longitude in decimal degrees"
    )
    aprs_beacon_parser.add_argument(
        "--comment", default="", help="Optional comment text"
    )
    aprs_beacon_parser.add_argument(
        "--symbol", default=">", help="APRS symbol code (default: > for car)"
    )
    aprs_beacon_parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required confirmation flag (acknowledges licensed operator KO4TUV present)",
    )

    # APRS decode
    aprs_decode_parser = aprs_subparsers.add_parser("decode", help="Decode APRS packet")
    aprs_decode_parser.add_argument("packet", help="Raw APRS packet string to decode")

    # APRS emergency frequencies
    aprs_emergency_parser = aprs_subparsers.add_parser(
        "emergency-freqs", help="List emergency communications frequencies"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(args.verbose)

    # Connect to radio
    try:
        radio = FT991A(port=args.port, baudrate=args.baud)
        if not radio.connect():
            print(f"Error: Could not connect to radio on {args.port}")
            return 1
    except Exception as e:
        print(f"Error connecting to radio: {e}")
        return 1

    try:
        # Handle commands
        if args.command == "status":
            status = radio.get_status()
            if status:
                print(f"Frequency: {status.frequency_a:,} Hz")
                print(f"Mode: {status.mode}")
                print(f"S-meter: {status.s_meter}")
                print(f"TX Power: {status.power_output}W")
                print(f"State: {'TX' if status.tx_active else 'RX'}")
            else:
                print("Failed to get status")
                return 1

        elif args.command == "freq":
            if args.freq_action == "get":
                freq = radio.get_frequency_a()
                print(f"{freq:,} Hz")
            elif args.freq_action == "set":
                if radio.set_frequency_a(args.frequency):
                    print(f"Set frequency to {args.frequency:,} Hz")
                else:
                    print("Failed to set frequency")
                    return 1

        elif args.command == "mode":
            if args.mode_action == "get":
                mode = radio.get_mode()
                print(mode.name if mode else "Unknown")
            elif args.mode_action == "set":
                mode = Mode[args.mode]
                if radio.set_mode(mode):
                    print(f"Set mode to {args.mode}")
                else:
                    print("Failed to set mode")
                    return 1

        elif args.command == "power":
            if args.power_action == "get":
                power = radio.get_tx_power()
                print(f"{power}W")
            elif args.power_action == "set":
                if radio.set_tx_power(args.watts):
                    print(f"Set power to {args.watts}W")
                else:
                    print("Failed to set power")
                    return 1

        elif args.command == "ptt":
            if args.ptt_action == "on":
                if radio.ptt_on():
                    print("PTT ON (transmitting)")
                else:
                    print("Failed to key PTT")
                    return 1
            elif args.ptt_action == "off":
                if radio.ptt_off():
                    print("PTT OFF (receiving)")
                else:
                    print("Failed to unkey PTT")
                    return 1

        elif args.command == "smeter":
            smeter = radio.get_s_meter()
            print(f"S-meter: {smeter}")

        elif args.command == "band":
            # Band frequency mapping
            band_freqs = {
                "160M": 1800000,
                "80M": 3500000,
                "60M": 5330500,
                "40M": 7000000,
                "30M": 10100000,
                "20M": 14000000,
                "17M": 18068000,
                "15M": 21000000,
                "12M": 24890000,
                "10M": 28000000,
            }

            freq = band_freqs[args.band]
            if radio.set_frequency(freq):
                print(f"Set band to {args.band} ({freq:,} Hz)")
            else:
                print(f"Failed to set band {args.band}")
                return 1

        elif args.command == "cw":
            if args.cw_action == "encode":
                morse = text_to_morse(args.message)
                print(morse)

            elif args.cw_action == "decode":
                text = morse_to_text(args.morse)
                print(text)

            elif args.cw_action == "send":
                # Safety checks and warnings
                print("⚠️  WARNING: CW TRANSMISSION REQUIRES AMATEUR RADIO LICENSE")
                print(
                    "⚠️  WARNING: Ensure licensed operator is present and controlling station"
                )
                print(
                    "⚠️  WARNING: This will transmit RF energy - check antenna and power settings"
                )
                print()

                if not args.confirm:
                    print("ERROR: --confirm flag required for CW transmission")
                    print("This acknowledges that a licensed operator is present.")
                    return 1

                if not (5 <= args.wpm <= 40):
                    print("ERROR: WPM must be between 5 and 40")
                    return 1

                # Convert to Morse and display what will be sent
                morse = text_to_morse(args.message)
                if not morse.strip():
                    print("ERROR: No valid Morse code generated from message")
                    return 1

                print(f"Message: {args.message}")
                print(f"Morse:   {morse}")
                print(f"Speed:   {args.wpm} WPM")
                print()

                try:
                    # Create keyer and send
                    keyer = CWKeyer(radio, args.wpm)
                    print("🔴 TRANSMITTING CW...")
                    keyer.send_text(args.message)
                    print("✅ CW transmission complete")

                except KeyboardInterrupt:
                    print("\n⚠️  Transmission interrupted - ensuring radio is unkeyed")
                    try:
                        keyer = CWKeyer(radio, args.wpm)
                        keyer.emergency_stop()
                    except:
                        pass
                    return 1
                except Exception as e:
                    print(f"ERROR during CW transmission: {e}")
                    try:
                        keyer = CWKeyer(radio, args.wpm)
                        keyer.emergency_stop()
                    except:
                        pass
                    return 1

            elif args.cw_action == "listen":
                print("CW decoder not yet implemented")
                print(
                    "This feature will provide audio-based CW decoding in a future release."
                )
                print("Planned features:")
                print("  - Real-time audio analysis using Goertzel algorithm")
                print("  - Automatic dit/dah timing detection")
                print("  - Noise filtering and signal conditioning")
                print("  - Support for various CW tones and speeds")

        elif args.command == "broadcast":
            try:
                broadcaster = Broadcaster(radio)
            except (AudioDeviceError, Exception) as e:
                print(f"ERROR: Failed to initialize broadcaster: {e}")
                print(
                    "Make sure audio dependencies are installed: pip install 'ft991a-control[audio]'"
                )
                return 1

            if args.broadcast_action == "say":
                # Safety checks and warnings
                print("⚠️  WARNING: TTS BROADCAST REQUIRES AMATEUR RADIO LICENSE")
                print(
                    "⚠️  WARNING: Licensed operator KO4TUV must be physically present"
                )
                print("⚠️  WARNING: This will generate audio that may be transmitted")
                print("⚠️  WARNING: Ensure proper mode, frequency, and power settings")
                print()

                if not args.confirm:
                    print("ERROR: --confirm flag required for broadcast operations")
                    print("This acknowledges that licensed operator KO4TUV is present.")
                    return 1

                print(f"Message: {args.message}")
                print(f"Voice:   {args.voice}")
                print()

                try:
                    print("🔴 BROADCASTING TTS...")
                    broadcaster.broadcast(args.message, confirm=True, voice=args.voice)
                    print("✅ TTS broadcast complete")

                except KeyboardInterrupt:
                    print("\n⚠️  Broadcast interrupted")
                    return 1
                except (BroadcastError, TTSError, AudioDeviceError) as e:
                    print(f"ERROR during broadcast: {e}")
                    return 1

            elif args.broadcast_action == "record":
                if not (1 <= args.duration <= 300):
                    print("ERROR: Duration must be between 1 and 300 seconds")
                    return 1

                try:
                    print(f"🎤 Recording from radio for {args.duration} seconds...")
                    wav_path = broadcaster.record_from_radio(args.duration, args.output)
                    print(f"✅ Recording saved: {wav_path}")

                except KeyboardInterrupt:
                    print("\n⚠️  Recording interrupted")
                    return 1
                except AudioDeviceError as e:
                    print(f"ERROR during recording: {e}")
                    return 1

            elif args.broadcast_action == "devices":
                devices = broadcaster.get_audio_devices()
                if "error" in devices:
                    print(f"ERROR: {devices['error']}")
                    return 1

                print("Available Audio Devices:")
                print("=" * 50)
                for device in devices["devices"]:
                    current = (
                        " (CURRENT)"
                        if device["id"] == devices["current_device"]
                        else ""
                    )
                    print(f"ID {device['id']}: {device['name']}{current}")
                    print(f"  Input channels: {device['max_input_channels']}")
                    print(f"  Output channels: {device['max_output_channels']}")
                    print(f"  Sample rate: {device['default_samplerate']} Hz")
                    print()

            elif args.broadcast_action == "test":
                print(f"Testing TTS for: {args.message}")
                print(f"Voice: {args.voice}")
                print()

                try:
                    print("🔊 Generating TTS audio...")
                    wav_path = broadcaster.text_to_audio(args.message, voice=args.voice)
                    print(f"✅ TTS audio generated: {wav_path}")
                    print("Note: This is a test - no audio was played to radio")

                    # Clean up temp file
                    import os

                    os.unlink(wav_path)

                except TTSError as e:
                    print(f"ERROR during TTS test: {e}")
                    return 1

        elif args.command == "digital":
            try:
                digital = DigitalModes(radio)
            except Exception as e:
                print(f"ERROR: Failed to initialize digital modes: {e}")
                return 1

            if args.digital_action == "setup-ft8":
                print("Configuring FT-991A for FT8...")
                if digital.setup_ft8(frequency=args.freq, band=args.band):
                    print("✅ FT8 configuration complete")

                    # Show current settings
                    status = radio.get_status()
                    if status:
                        print(f"Frequency: {status.frequency_a/1e6:.3f} MHz")
                        print(f"Mode: {status.mode}")
                        print(f"Power: {status.power_output}W")

                    print("\nNext steps:")
                    print("1. Launch WSJT-X software")
                    print("2. Select FT8 mode in WSJT-X")
                    print("3. Configure WSJT-X CAT and audio settings")
                    print(
                        "4. Use 'ft991a-cli digital wsjtx-config' to generate config file"
                    )
                else:
                    print("❌ FT8 configuration failed")
                    return 1

            elif args.digital_action == "setup-ft4":
                print("Configuring FT-991A for FT4...")
                if digital.setup_ft4(frequency=args.freq, band=args.band):
                    print("✅ FT4 configuration complete")

                    # Show current settings
                    status = radio.get_status()
                    if status:
                        print(f"Frequency: {status.frequency_a/1e6:.3f} MHz")
                        print(f"Mode: {status.mode}")
                        print(f"Power: {status.power_output}W")

                    print("\nNext steps:")
                    print("1. Launch WSJT-X software")
                    print("2. Select FT4 mode in WSJT-X")
                    print("3. Configure WSJT-X CAT and audio settings")
                    print(
                        "4. Use 'ft991a-cli digital wsjtx-config' to generate config file"
                    )
                else:
                    print("❌ FT4 configuration failed")
                    return 1

            elif args.digital_action == "setup-js8":
                print("Configuring FT-991A for JS8Call...")
                if digital.setup_js8call(frequency=args.freq, band=args.band):
                    print("✅ JS8Call configuration complete")

                    # Show current settings
                    status = radio.get_status()
                    if status:
                        print(f"Frequency: {status.frequency_a/1e6:.3f} MHz")
                        print(f"Mode: {status.mode}")
                        print(f"Power: {status.power_output}W")

                    print("\nNext steps:")
                    print("1. Launch JS8Call software")
                    print("2. Configure JS8Call CAT and audio settings")
                    print("3. Set your callsign and grid square in JS8Call")
                else:
                    print("❌ JS8Call configuration failed")
                    return 1

            elif args.digital_action == "audio-check":
                print("Detecting PCM2903B USB audio CODEC...")
                device = digital.get_audio_device()
                if device:
                    print("✅ USB audio device found:")
                    print(f"  Name: {device['name']}")
                    print(f"  ALSA device: {device['alsa_name']}")
                    if "pulse_name" in device:
                        print(f"  PulseAudio: {device['pulse_name']}")
                    print(f"  Card: {device['card']}, Device: {device['device']}")
                    print("\nThis device should work with WSJT-X and JS8Call.")
                else:
                    print("❌ No PCM2903B or compatible USB audio device found")
                    print("\nTroubleshooting:")
                    print("1. Ensure PCM2903B is connected via USB")
                    print("2. Check that the device appears in 'lsusb' output")
                    print("3. Verify ALSA drivers are loaded")
                    print("4. Try 'arecord -l' to list audio devices")
                    return 1

            elif args.digital_action == "status":
                print("Digital Mode Status:")
                print("=" * 40)

                status = digital.get_digital_status()
                if status:
                    print(f"Frequency: {status.get('frequency', 0)/1e6:.3f} MHz")
                    print(f"Mode: {status.get('mode', 'Unknown')}")
                    print(
                        f"Digital Mode: {'Yes' if status.get('is_digital') else 'No'}"
                    )
                    if status.get("likely_digital_mode"):
                        print(f"Likely Mode: {status['likely_digital_mode']}")
                    print(f"Power: {status.get('power', 0)}W")
                    print(f"TX Active: {'Yes' if status.get('tx_active') else 'No'}")
                    print(f"S-Meter: {status.get('s_meter', 0)}")

                    audio_device = status.get("audio_device")
                    if audio_device:
                        print(f"Audio Device: {audio_device['name']}")
                    else:
                        print("Audio Device: Not detected")
                else:
                    print("Unable to get radio status")
                    return 1

            elif args.digital_action == "wsjtx-config":
                print(f"Generating WSJT-X configuration for {args.callsign}...")
                config_path = digital.create_wsjtx_config(args.callsign, args.grid)
                if config_path:
                    print(f"✅ WSJT-X config created: {config_path}")
                    print("\nConfiguration details:")
                    print(f"  Callsign: {args.callsign}")
                    print(f"  Grid Square: {args.grid}")
                    print(f"  CAT Port: {radio.port} @ {radio.baudrate} baud")

                    audio_device = digital.get_audio_device()
                    if audio_device:
                        print(f"  Audio Device: {audio_device['alsa_name']}")
                    else:
                        print("  Audio Device: default (no PCM2903B detected)")

                    print("\nNext steps:")
                    print("1. Launch WSJT-X")
                    print("2. The configuration should be automatically loaded")
                    print("3. Test CAT control in WSJT-X settings")
                    print("4. Test audio levels with 'Test CAT' and 'Test PTT'")
                else:
                    print("❌ Failed to create WSJT-X configuration")
                    return 1

        elif args.command == "scan":
            scanner = BandScanner(radio)

            if args.scan_action == "band":
                print(
                    f"Scanning {args.start:,} - {args.end:,} Hz (step: {args.step:,} Hz)"
                )
                results = scanner.scan_band(args.start, args.end, args.step, args.dwell)

                if results:
                    chart = scanner.format_scan_results(results, "Band Scan Results")
                    print(chart)
                else:
                    print("No scan results")

            elif args.scan_action == "activity":
                print(
                    f"Searching for activity above S-meter threshold {args.threshold}"
                )
                active = scanner.find_activity(args.threshold)

                if active:
                    report = scanner.format_activity_results(
                        active, "Active Frequencies Found"
                    )
                    print(report)
                else:
                    print(f"No activity found above S-meter threshold {args.threshold}")

            elif args.scan_action == "fine":
                print(
                    f"Fine scanning around {args.freq/1e6:.3f} MHz (±{args.width/2000:.0f} kHz)"
                )
                results = scanner.fine_scan(args.freq, args.width, args.step)

                if results:
                    chart = scanner.format_scan_results(
                        results, f"Fine Scan: {args.freq/1e6:.3f} MHz"
                    )
                    print(chart)
                else:
                    print("No scan results")

            elif args.scan_action == "hf":
                print("Scanning all HF amateur bands (160m-10m)...")
                activity = scanner.scan_all_hf()

                if activity:
                    report = scanner.format_activity_results(
                        activity, "HF Band Activity"
                    )
                    print(report)
                else:
                    print("No HF activity detected")

        elif args.command == "aprs":
            aprs_client = APRSClient(radio, "KO4TUV")

            if args.aprs_action == "setup":
                print("Configuring radio for APRS operation...")
                print("⚠️  Setting 144.390 MHz FM mode for APRS")

                if aprs_client.setup_aprs():
                    print("✅ Radio configured for APRS")
                    print("📡 Ready for APRS operations on 144.390 MHz")
                    print("⚠️  TRANSMISSION REQUIRES LICENSED OPERATOR PRESENT")
                else:
                    print("❌ Failed to configure radio for APRS")
                    return 1

            elif args.aprs_action == "beacon":
                print("APRS Position Beacon")
                print("⚠️  WARNING: APRS TRANSMISSION REQUIRES AMATEUR RADIO LICENSE")
                print(
                    "⚠️  WARNING: Ensure licensed operator KO4TUV is present and controlling station"
                )
                print("⚠️  WARNING: This will transmit on 144.390 MHz APRS frequency")
                print()

                if not args.confirm:
                    print("❌ ERROR: --confirm flag required for APRS transmission")
                    print("This acknowledges that licensed operator KO4TUV is present.")
                    return 1

                # Validate coordinates
                if not (-90 <= args.lat <= 90):
                    print("❌ ERROR: Latitude must be between -90 and 90 degrees")
                    return 1
                if not (-180 <= args.lon <= 180):
                    print("❌ ERROR: Longitude must be between -180 and 180 degrees")
                    return 1

                try:
                    # Encode APRS position packet
                    packet = aprs_client.encode_aprs_position(
                        "KO4TUV",
                        args.lat,
                        args.lon,
                        args.comment,
                        symbol_code=args.symbol,
                    )

                    print(f"Position: {args.lat:.6f}°, {args.lon:.6f}°")
                    print(f"Comment: {args.comment}")
                    print(f"Symbol: {args.symbol}")
                    print(f"Packet: {packet}")
                    print()

                    # Attempt transmission (will show warning about hardware not implemented)
                    print("🔴 ATTEMPTING APRS TRANSMISSION...")
                    success = aprs_client.transmit_packet(packet, confirmed=True)

                    if success:
                        print("✅ APRS beacon transmitted successfully")
                    else:
                        print(
                            "❌ APRS transmission failed - hardware interface not implemented"
                        )
                        print(
                            "📋 Packet encoded and ready for external TNC/sound card interface"
                        )

                except Exception as e:
                    print(f"❌ ERROR encoding APRS packet: {e}")
                    return 1

            elif args.aprs_action == "decode":
                print(f"Decoding APRS packet: {args.packet}")
                print()

                try:
                    decoded = aprs_client.decode_aprs_packet(args.packet)

                    if decoded:
                        print("✅ APRS Packet Decoded Successfully")
                        print(f"Source: {decoded.source_call}")
                        print(f"Destination: {decoded.destination}")
                        print(f"Path: {' -> '.join(decoded.path)}")
                        print(f"Type: {decoded.packet_type}")
                        print()

                        if "type" in decoded.data:
                            if decoded.data["type"] == "position":
                                print("📍 POSITION REPORT:")
                                if "latitude" in decoded.data:
                                    print(
                                        f"  Latitude: {decoded.data['latitude']:.6f}°"
                                    )
                                if "longitude" in decoded.data:
                                    print(
                                        f"  Longitude: {decoded.data['longitude']:.6f}°"
                                    )
                                if (
                                    "comment" in decoded.data
                                    and decoded.data["comment"]
                                ):
                                    print(f"  Comment: {decoded.data['comment']}")
                                if "symbol_code" in decoded.data:
                                    print(f"  Symbol: {decoded.data['symbol_code']}")

                            elif decoded.data["type"] == "message":
                                print("💬 MESSAGE:")
                                if "addressee" in decoded.data:
                                    print(f"  To: {decoded.data['addressee']}")
                                if "message" in decoded.data:
                                    print(f"  Text: {decoded.data['message']}")
                                if "message_id" in decoded.data:
                                    print(f"  ID: {decoded.data['message_id']}")

                            elif decoded.data["type"] == "weather":
                                print("🌦️ WEATHER:")
                                print(
                                    f"  Data: {decoded.data.get('weather_data', 'N/A')}"
                                )

                            elif decoded.data["type"] == "status":
                                print("📢 STATUS:")
                                print(
                                    f"  Text: {decoded.data.get('status_text', 'N/A')}"
                                )

                        # Show raw data for debugging
                        print()
                        print("🔍 Raw Data:")
                        for key, value in decoded.data.items():
                            if key != "type":
                                print(f"  {key}: {value}")

                    else:
                        print("❌ Failed to decode APRS packet")
                        print(
                            "The packet may be malformed or use an unsupported format"
                        )
                        return 1

                except Exception as e:
                    print(f"❌ ERROR decoding APRS packet: {e}")
                    return 1

            elif args.aprs_action == "emergency-freqs":
                print("🚨 EMERGENCY COMMUNICATIONS FREQUENCIES")
                print("=" * 60)
                print()

                # Show emergency frequencies
                emergency_kit = EmergencyKit()
                freqs = emergency_kit.list_frequencies()

                print("📻 EMERGENCY FREQUENCIES:")
                print("-" * 60)
                for freq_info in freqs:
                    print(
                        f"  {freq_info['name']:<20} {freq_info['freq']:>8.3f} MHz  {freq_info['mode']:<8} {freq_info['notes']}"
                    )

                print()
                print("📅 EMERGENCY NETS & SCHEDULES:")
                print("-" * 60)
                nets = emergency_kit.list_nets()
                for net_info in nets:
                    print(
                        f"  {net_info['net']:<15} {net_info['frequency']:>8.3f} MHz  {net_info['day']:<15} {net_info['time']:<12}"
                    )
                    print(f"    {net_info['notes']}")
                    print()

                print("⚠️  IMPORTANT NOTES:")
                print("   - Licensed amateur radio operator required for transmission")
                print("   - Monitor frequencies before transmitting")
                print(
                    "   - Follow net control instructions during emergency operations"
                )
                print(
                    "   - Maritime/Aviation frequencies are RECEIVE ONLY unless appropriately licensed"
                )
                print("   - ARES: Amateur Radio Emergency Service")
                print("   - RACES: Radio Amateur Civil Emergency Service")
                print(
                    "   - SKYWARN: National Weather Service severe weather spotting program"
                )

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        if radio:
            radio.disconnect()


def mcp_server_main():
    """Entry point for ft991a-mcp command"""
    parser = argparse.ArgumentParser(description="FT-991A MCP Server")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Radio serial port")
    parser.add_argument("--baud", type=int, default=38400, help="Radio baud rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Set up the server instance with the specified port/baud
    from .mcp import server_instance

    server_instance.port = args.port
    server_instance.baud = args.baud

    # Run the MCP server
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nMCP server stopped", file=sys.stderr)
    except Exception as e:
        print(f"MCP server error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    # This allows testing the CLI directly
    sys.exit(cli_main())
