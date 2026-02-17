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
from pathlib import Path

from .cat import FT991A, Mode, Band
from .mcp import run_server


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )


def web_server_main():
    """Entry point for ft991a-web command"""
    parser = argparse.ArgumentParser(description="FT-991A Web GUI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--radio-port", default="/dev/ttyUSB0", help="Radio serial port")
    parser.add_argument("--radio-baud", type=int, default=38400, help="Radio baud rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    # Import and run the web server
    from .web import app
    
    print(f"Starting FT-991A Web GUI on http://{args.host}:{args.port}")
    print(f"Radio: {args.radio_port} @ {args.radio_baud} baud")
    
    uvicorn.run(
        "ft991a.web:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info" if not args.verbose else "debug"
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
    mode_set_parser.add_argument("mode", choices=[m.name for m in Mode], help="Operating mode")
    
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
    band_parser.add_argument("band", choices=["160M", "80M", "60M", "40M", "30M", "20M", "17M", "15M", "12M", "10M"], help="Amateur band")
    
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
                "160M": 1800000, "80M": 3500000, "60M": 5330500,
                "40M": 7000000, "30M": 10100000, "20M": 14000000,
                "17M": 18068000, "15M": 21000000, "12M": 24890000,
                "10M": 28000000
            }
            
            freq = band_freqs[args.band]
            if radio.set_frequency(freq):
                print(f"Set band to {args.band} ({freq:,} Hz)")
            else:
                print(f"Failed to set band {args.band}")
                return 1
        
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