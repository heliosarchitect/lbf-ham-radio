"""
FT-991A Control Package
=======================
AI-controllable Yaesu FT-991A transceiver interface with web GUI, CLI, and MCP server.

This package provides:
- CAT (Computer Aided Transceiver) control library
- Web-based GUI with real-time WebSocket updates
- Command-line interface for direct control
- MCP (Model Context Protocol) server for AI integration

Components:
- ft991a.cat: Core CAT control library
- ft991a.web: FastAPI web server
- ft991a.mcp: MCP server for AI assistants
- ft991a.cli: Command-line interface

Entry points:
- ft991a-web: Launch web GUI server
- ft991a-cli: Direct CAT commands from terminal
- ft991a-mcp: Launch MCP server (stdio transport)
"""

__version__ = "0.8.1"
__author__ = "LBF / Matthew"
__email__ = "heliosarchitectlbf@gmail.com"
__license__ = "MIT"

# Import main classes for easy access
try:
    from .broadcast import AudioDeviceError, Broadcaster, BroadcastError, TTSError
    from .cat import FT991A, Band, Mode, RadioStatus
    from .scanner import ActivityResult, BandScanner, ScanResult

    __all__ = [
        "FT991A",
        "Mode",
        "Band",
        "RadioStatus",
        "BandScanner",
        "ScanResult",
        "ActivityResult",
        "Broadcaster",
        "BroadcastError",
        "AudioDeviceError",
        "TTSError",
        "__version__",
    ]
except ImportError as e:
    # Handle missing dependencies during development/testing
    __all__ = ["__version__"]
