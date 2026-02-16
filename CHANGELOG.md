# Changelog

All notable changes to the FT-991A Control Package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-02-16

### 🏗️ **Major Restructure** - PyPI Package + MCP Server

This release represents a complete restructuring of the project as a proper PyPI-publishable package with AI integration via MCP server.

### Added
- **📦 PyPI Package Structure**: Complete `src/ft991a/` package layout
- **🤖 MCP Server**: Full Model Context Protocol server implementation (`ft991a.mcp`)
  - 14 MCP tools for AI control: frequency, mode, power, PTT, S-meter, band switching
  - stdio transport for standard AI assistant integration  
  - Comprehensive tool descriptions for AI understanding
  - Safety features and error handling
- **🖥️ CLI Interface**: New command-line entry points (`ft991a.cli`)
  - `ft991a-web`: Launch web GUI server
  - `ft991a-cli`: Direct CAT commands from terminal
  - `ft991a-mcp`: Launch MCP server for AI integration
- **📋 Modern Python Packaging**:
  - `pyproject.toml` with PEP 621 metadata
  - `setup.cfg` fallback for older tools
  - Console script entry points
  - Optional dependencies (`[dev]`, `[audio]`)
- **🧪 Unit Tests**: Comprehensive test suite with mocked serial interface
  - 20+ test cases covering all CAT functionality
  - No hardware required for testing
  - Coverage reporting and CI-ready
- **📚 Complete Documentation**: 
  - Updated README.md for PyPI
  - MCP Registry submission file (`mcp-registry.json`)
  - API reference and troubleshooting guide
  - Safety warnings and best practices
- **🔒 Enhanced Safety Features**:
  - TX lockout toggle
  - Frequency range validation
  - Power limit enforcement
  - PTT safety confirmations

### Changed
- **📂 File Structure**: Migrated to standard `src/` layout
  - `ft991a.py` → `src/ft991a/cat.py` 
  - `server.py` → `src/ft991a/web.py`
  - `static/` → `src/ft991a/static/`
- **📦 Import Structure**: Package-relative imports
  - `from ft991a import FT991A` (public API)
  - Internal: `from .cat import FT991A`
- **🏷️ Version Management**: Centralized in `__init__.py`
- **📖 Documentation**: Complete rewrite for PyPI audience

### Technical Details
- **Dependencies**: Added `mcp>=1.0.0` for AI integration
- **Python Support**: 3.9+ (matches MCP SDK requirements)
- **Entry Points**: Three console scripts via `pyproject.toml`
- **Package Data**: Static files included in wheel
- **Testing**: pytest + mock serial interface
- **Code Quality**: black, isort, mypy, flake8 configurations

### Migration Guide
```bash
# Old usage
python3 server.py
python3 ft991a.py  # Direct library usage

# New usage  
pip install ft991a-control
ft991a-web          # Web GUI
ft991a-cli status   # CLI commands
ft991a-mcp          # MCP server for AI

# Python imports unchanged
from ft991a import FT991A, Mode, Band
```

### AI Integration
The new MCP server enables direct AI assistant control:
- **Claude/GPT**: "Set the radio to 20 meter FT8 frequency"
- **Automated**: Frequency scanning, mode switching, power control
- **Safety**: Built-in TX lockout and validation

---

## [0.2.0] - 2026-02-16

### Added
- **🌐 Web GUI**: Full-featured FastAPI web interface
- **🔗 WebSocket Updates**: Real-time status monitoring  
- **📡 Complete CAT Library**: All FT-991A CAT commands implemented
- **🎛️ Web Controls**: Frequency, mode, power, PTT, band switching
- **📊 S-meter Visualization**: Real-time signal strength display
- **⚙️ systemd Integration**: Service files for daemon mode

### Features
- Browser-based control panel
- Mobile/tablet responsive design  
- REST API endpoints
- Background status polling
- Memory channel support
- Band plan integration

---

## [0.1.0] - 2026-02-16

### Added
- **📡 Basic CAT Control**: Initial Yaesu FT-991A CAT protocol implementation
- **🔌 Serial Interface**: USB serial communication (38400 baud)
- **🎯 Core Commands**: Frequency, mode, power control
- **📋 Documentation**: Initial research and setup guides

### Features
- Direct serial CAT communication
- Basic frequency and mode control
- Power setting capabilities
- S-meter reading
- PTT control

---

## Development Roadmap

### [0.4.0] - Planned
- **🎵 Audio Integration**: sounddevice optional dependency
- **📻 Digital Mode Helper**: FT8/PSK31 frequency/mode presets
- **🔄 Memory Management**: Full memory channel CRUD
- **📱 Mobile App**: React Native companion app
- **🏠 Home Assistant**: HASS integration

### [0.5.0] - Future
- **📊 Contest Features**: Band/mode tracking, QSO logging
- **🌐 Remote Access**: Secure internet control
- **🔌 Plugin System**: Third-party extensions
- **📈 Analytics**: Usage statistics and reporting

---

## Support

- **📖 Documentation**: [README.md](README.md)
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/heliosarchitect/lbf-ham-radio/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/heliosarchitect/lbf-ham-radio/discussions)
- **📧 Contact**: heliosarchitectlbf@gmail.com

## License

MIT License - see [LICENSE](LICENSE) file.

---
*73! 📡*