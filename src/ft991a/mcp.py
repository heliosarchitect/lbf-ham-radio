#!/usr/bin/env python3
"""
FT-991A MCP Server
==================
Model Context Protocol server for AI-controlled Yaesu FT-991A transceiver operations.

This server exposes the FT-991A CAT control functionality as MCP tools, allowing
AI assistants to control the radio remotely via the Model Context Protocol.

Transport: stdio (standard for MCP servers)
SDK: Official `mcp` Python package

Tools exposed:
- get_frequency: Get current VFO frequency
- set_frequency: Tune to specific frequency  
- get_mode: Get current operating mode
- set_mode: Change operating mode (LSB/USB/CW/FM/AM/FT8/etc)
- get_smeter: Read S-meter signal strength
- get_power: Get current TX power setting
- set_power: Set TX power (5-100W)
- ptt_on/ptt_off: Key/unkey transmitter
- get_status: Get complete radio status
- set_band: Switch to amateur band
- get_memories: List programmed memory channels
- recall_memory: Tune to memory channel
- toggle_tx_lock: Enable/disable TX lockout
"""

import asyncio
import json
import logging
import sys
from typing import Any, Optional

from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Resource, 
    Tool,
    TextContent,
    LoggingLevel,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
    CallToolResult
)

from .cat import FT991A, Mode, Band, RadioStatus

logger = logging.getLogger(__name__)

class FT991AMCPServer:
    """MCP server wrapper for FT-991A CAT control"""
    
    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 38400):
        self.port = port
        self.baud = baud
        self.radio: Optional[FT991A] = None
        
    async def connect_radio(self) -> bool:
        """Initialize radio connection"""
        try:
            self.radio = FT991A(port=self.port, baud=self.baud)
            if self.radio.connect():
                logger.info(f"Connected to FT-991A on {self.port}")
                return True
            else:
                logger.error("Failed to connect to FT-991A")
                return False
        except Exception as e:
            logger.error(f"Radio connection error: {e}")
            return False
    
    def ensure_connected(self) -> FT991A:
        """Ensure radio is connected, raise exception if not"""
        if not self.radio or not self.radio.is_connected:
            raise RuntimeError("Radio not connected. Use connect_radio() first.")
        return self.radio

# Global server instance
server_instance = FT991AMCPServer()

# MCP Server Configuration
@stdio_server()
async def main():
    """Main MCP server entry point"""
    
    # Tool definitions with proper descriptions for AI understanding
    TOOLS = [
        Tool(
            name="get_frequency",
            description="Get the current VFO-A frequency in Hz. Returns the frequency the radio is currently tuned to.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="set_frequency", 
            description="Tune the radio to a specific frequency in Hz. Valid range: 30kHz - 56MHz for FT-991A.",
            inputSchema={
                "type": "object",
                "properties": {
                    "freq_hz": {
                        "type": "integer",
                        "description": "Frequency in Hz (e.g., 14074000 for 20m FT8)",
                        "minimum": 30000,
                        "maximum": 56000000
                    }
                },
                "required": ["freq_hz"]
            }
        ),
        Tool(
            name="get_mode",
            description="Get the current operating mode (LSB, USB, CW, FM, AM, DATA-USB for FT8, etc.)",
            inputSchema={
                "type": "object", 
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="set_mode",
            description="Change the operating mode. Common modes: LSB, USB, CW, FM, AM, DATA_USB (for FT8/digital), DATA_LSB",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Operating mode name",
                        "enum": ["LSB", "USB", "CW", "FM", "AM", "RTTY_LSB", "CW_R", "DATA_LSB", "RTTY_USB", "DATA_FM", "FM_N", "DATA_USB", "AM_N", "C4FM"]
                    }
                },
                "required": ["mode"]
            }
        ),
        Tool(
            name="get_smeter", 
            description="Read the S-meter signal strength. Returns S-units (1-9) plus dB over S9 if applicable.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_power",
            description="Get the current TX power setting in watts.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="set_power",
            description="Set the TX power output in watts (5-100W for FT-991A).",
            inputSchema={
                "type": "object",
                "properties": {
                    "watts": {
                        "type": "integer", 
                        "description": "TX power in watts",
                        "minimum": 5,
                        "maximum": 100
                    }
                },
                "required": ["watts"]
            }
        ),
        Tool(
            name="ptt_on",
            description="Key the transmitter (start transmitting). Use with extreme caution - verify antenna is connected.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="ptt_off", 
            description="Unkey the transmitter (stop transmitting, return to receive mode).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_status",
            description="Get complete radio status including frequency, mode, S-meter, TX/RX state, power, etc.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="set_band",
            description="Switch to a specific amateur radio band using common band names.",
            inputSchema={
                "type": "object",
                "properties": {
                    "band": {
                        "type": "string",
                        "description": "Amateur band name", 
                        "enum": ["160M", "80M", "60M", "40M", "30M", "20M", "17M", "15M", "12M", "10M", "6M", "2M", "70CM"]
                    }
                },
                "required": ["band"]
            }
        ),
        Tool(
            name="get_memories",
            description="List all programmed memory channels with their frequencies and modes.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="recall_memory",
            description="Tune to a specific memory channel. Memory channels 1-99 are user programmable.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "integer",
                        "description": "Memory channel number (1-99)",
                        "minimum": 1,
                        "maximum": 99
                    }
                },
                "required": ["channel"]
            }
        ),
        Tool(
            name="toggle_tx_lock",
            description="Toggle TX lockout to prevent accidental transmission. Safety feature.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]
    
    @stdio_server.list_tools()
    async def list_tools() -> ListToolsResult:
        """List available MCP tools"""
        return ListToolsResult(tools=TOOLS)
    
    @stdio_server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """Handle tool calls"""
        try:
            # Ensure radio connection
            radio = server_instance.ensure_connected()
            
            if name == "get_frequency":
                freq = radio.get_frequency()
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Current frequency: {freq:,} Hz")]
                )
            
            elif name == "set_frequency":
                freq_hz = arguments.get("freq_hz")
                success = radio.set_frequency(freq_hz)
                status = "success" if success else "failed"
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Set frequency to {freq_hz:,} Hz: {status}")]
                )
            
            elif name == "get_mode":
                mode = radio.get_mode()
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Current mode: {mode.name if mode else 'Unknown'}")]
                )
            
            elif name == "set_mode":
                mode_name = arguments.get("mode")
                # Convert string to Mode enum
                mode = Mode[mode_name]
                success = radio.set_mode(mode)
                status = "success" if success else "failed"
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Set mode to {mode_name}: {status}")]
                )
            
            elif name == "get_smeter":
                smeter = radio.get_smeter()
                return CallToolResult(
                    content=[TextContent(type="text", text=f"S-meter reading: {smeter}")]
                )
            
            elif name == "get_power":
                power = radio.get_tx_power()
                return CallToolResult(
                    content=[TextContent(type="text", text=f"TX power: {power}W")]
                )
            
            elif name == "set_power":
                watts = arguments.get("watts")
                success = radio.set_tx_power(watts)
                status = "success" if success else "failed" 
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Set TX power to {watts}W: {status}")]
                )
            
            elif name == "ptt_on":
                success = radio.ptt_on()
                status = "success" if success else "failed"
                return CallToolResult(
                    content=[TextContent(type="text", text=f"PTT on (transmitting): {status}")]
                )
            
            elif name == "ptt_off":
                success = radio.ptt_off()
                status = "success" if success else "failed"
                return CallToolResult(
                    content=[TextContent(type="text", text=f"PTT off (receiving): {status}")]
                )
            
            elif name == "get_status":
                status = radio.get_status()
                if status:
                    status_text = f"""Radio Status:
Frequency: {status.frequency:,} Hz
Mode: {status.mode.name if status.mode else 'Unknown'}
S-meter: {status.smeter}
TX Power: {status.tx_power}W
TX State: {'Transmitting' if status.tx_on else 'Receiving'}
"""
                else:
                    status_text = "Failed to get radio status"
                
                return CallToolResult(
                    content=[TextContent(type="text", text=status_text)]
                )
            
            elif name == "set_band":
                band_name = arguments.get("band")
                # Convert to Band enum and get frequency
                band_freq_map = {
                    "160M": 1800000, "80M": 3500000, "60M": 5330500,
                    "40M": 7000000, "30M": 10100000, "20M": 14000000,
                    "17M": 18068000, "15M": 21000000, "12M": 24890000,
                    "10M": 28000000, "6M": 50000000, "2M": 144000000,
                    "70CM": 420000000
                }
                
                if band_name in band_freq_map:
                    freq = band_freq_map[band_name]
                    success = radio.set_frequency(freq)
                    status = "success" if success else "failed"
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Set band to {band_name} ({freq:,} Hz): {status}")]
                    )
                else:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Unknown band: {band_name}")]
                    )
            
            elif name == "get_memories":
                # This would need to be implemented in the CAT library
                return CallToolResult(
                    content=[TextContent(type="text", text="Memory channel listing not yet implemented in CAT library")]
                )
            
            elif name == "recall_memory":
                channel = arguments.get("channel")
                # This would need to be implemented in the CAT library
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Memory recall for channel {channel} not yet implemented in CAT library")]
                )
            
            elif name == "toggle_tx_lock":
                # This would need to be implemented in the CAT library
                return CallToolResult(
                    content=[TextContent(type="text", text="TX lock toggle not yet implemented in CAT library")]
                )
            
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")]
                )
        
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")]
            )

async def run_server():
    """Run the MCP server"""
    # Try to connect to radio on startup
    if not await server_instance.connect_radio():
        logger.warning("Failed to connect to radio on startup - tools will fail until connection is established")
    
    # Run the stdio server
    await main()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)]  # MCP uses stderr for logs, stdout for protocol
    )
    
    # Run server
    asyncio.run(run_server())