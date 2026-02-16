#!/usr/bin/env python3
"""
FT-991A Web GUI Server
======================
FastAPI + WebSocket server for real-time control of Yaesu FT-991A ham radio.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .cat import FT991A, Mode, Band, RadioStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ft991a-web.log")
    ]
)
logger = logging.getLogger(__name__)

# ── Data Models ──────────────────────────────────────────────

class FrequencyRequest(BaseModel):
    frequency: int  # Hz

class ModeRequest(BaseModel):
    mode: str  # Mode name (LSB, USB, etc.)

class PowerRequest(BaseModel):
    power: int  # Watts (5-100)

class BandRequest(BaseModel):
    band: str  # Band name (160M, 80M, etc.)

class PTTRequest(BaseModel):
    enable: bool

class ConfigRequest(BaseModel):
    port: str = "/dev/ttyUSB0"
    baudrate: int = 38400

# ── Global State ─────────────────────────────────────────────

app = FastAPI(title="FT-991A Web GUI", version="0.2.0")
radio: Optional[FT991A] = None
radio_connected = False
tx_lockout = False  # Safety: prevents accidental PTT
websocket_clients: Set[WebSocket] = set()

# Configuration
radio_config = {
    "port": "/dev/ttyUSB0",
    "baudrate": 38400,
    "auto_reconnect": True
}

# ── WebSocket Manager ────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        websocket_clients.add(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        websocket_clients.discard(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"WebSocket send failed: {e}")
                dead_connections.append(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)

manager = ConnectionManager()

# ── Radio Control Functions ──────────────────────────────────

async def connect_radio():
    """Connect to the radio and start monitoring."""
    global radio, radio_connected
    
    try:
        radio = FT991A(radio_config["port"], radio_config["baudrate"])
        radio_connected = radio.connect()
        
        if radio_connected:
            logger.info(f"Connected to FT-991A on {radio_config['port']}")
            await manager.broadcast({"type": "connection", "status": "connected"})
            
            # Start monitoring task
            asyncio.create_task(monitor_radio())
        else:
            logger.error("Failed to connect to radio")
            await manager.broadcast({"type": "connection", "status": "failed"})
            
    except Exception as e:
        logger.error(f"Radio connection error: {e}")
        radio_connected = False
        await manager.broadcast({"type": "connection", "status": "error", "message": str(e)})

async def disconnect_radio():
    """Disconnect from the radio."""
    global radio, radio_connected
    
    if radio:
        try:
            # Safety: ensure PTT is off
            radio.ptt_off()
        except:
            pass
        radio.disconnect()
        radio = None
        radio_connected = False
        logger.info("Disconnected from radio")
        await manager.broadcast({"type": "connection", "status": "disconnected"})

async def monitor_radio():
    """Background task to monitor radio status and broadcast updates."""
    global radio, radio_connected
    
    while radio_connected and radio:
        try:
            # Get comprehensive status
            status = radio.get_status()
            
            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "status",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "frequency_a": status.frequency_a,
                    "frequency_b": status.frequency_b,
                    "mode": status.mode,
                    "tx_active": status.tx_active,
                    "squelch_open": status.squelch_open,
                    "s_meter": status.s_meter,
                    "power_output": status.power_output,
                    "swr": status.swr,
                    "tx_lockout": tx_lockout
                }
            })
            
            # Sleep before next poll
            await asyncio.sleep(0.5)  # 2 Hz update rate
            
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            radio_connected = False
            await manager.broadcast({"type": "connection", "status": "lost", "message": str(e)})
            break

# ── Static Files ─────────────────────────────────────────────

# Create static directory if it doesn't exist
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Web Routes ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_root():
    """Serve the main HTML interface."""
    try:
        return FileResponse(str(static_dir / "index.html"))
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
        <body>
        <h1>FT-991A Web GUI</h1>
        <p>Frontend not found. Please ensure the static files are properly packaged.</p>
        </body>
        </html>
        """)

# ── API Endpoints ────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Get current radio status."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        status = radio.get_status()
        return {
            "connected": True,
            "status": {
                "frequency_a": status.frequency_a,
                "frequency_b": status.frequency_b,
                "mode": status.mode,
                "tx_active": status.tx_active,
                "squelch_open": status.squelch_open,
                "s_meter": status.s_meter,
                "power_output": status.power_output,
                "swr": status.swr,
                "tx_lockout": tx_lockout
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/frequency/a")
async def set_frequency_a(req: FrequencyRequest):
    """Set VFO-A frequency."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        radio.set_frequency_a(req.frequency)
        return {"success": True, "frequency": req.frequency}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/frequency/b")
async def set_frequency_b(req: FrequencyRequest):
    """Set VFO-B frequency."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        radio.set_frequency_b(req.frequency)
        return {"success": True, "frequency": req.frequency}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mode")
async def set_mode(req: ModeRequest):
    """Set operating mode."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        # Convert mode name to enum
        mode = Mode[req.mode]
        radio.set_mode(mode)
        return {"success": True, "mode": req.mode}
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/power")
async def set_power(req: PowerRequest):
    """Set TX power level."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        radio.set_power_level(req.power)
        return {"success": True, "power": req.power}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/band")
async def set_band(req: BandRequest):
    """Set band (changes frequency)."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        # Convert band name to enum
        band_name = f"HF_{req.band}" if not req.band.startswith(("VHF_", "UHF_")) else req.band
        band = Band[band_name]
        radio.set_band(band)
        return {"success": True, "band": req.band, "frequency": band.value}
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid band: {req.band}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ptt")
async def set_ptt(req: PTTRequest):
    """Control PTT (Push-To-Talk)."""
    global tx_lockout
    
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    if tx_lockout:
        raise HTTPException(status_code=423, detail="TX lockout enabled")
    
    try:
        if req.enable:
            radio.ptt_on()
            logger.warning("PTT ON via web interface")
        else:
            radio.ptt_off()
            logger.info("PTT OFF via web interface")
        
        return {"success": True, "ptt": req.enable}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lockout")
async def toggle_tx_lockout():
    """Toggle TX lockout safety feature."""
    global tx_lockout
    
    tx_lockout = not tx_lockout
    logger.info(f"TX lockout {'enabled' if tx_lockout else 'disabled'}")
    
    # If enabling lockout, ensure PTT is off
    if tx_lockout and radio_connected and radio:
        try:
            radio.ptt_off()
        except:
            pass
    
    return {"success": True, "lockout": tx_lockout}

@app.get("/api/modes")
async def get_modes():
    """Get available operating modes."""
    return {
        "modes": [mode.name for mode in Mode]
    }

@app.get("/api/bands")
async def get_bands():
    """Get available bands."""
    return {
        "bands": [band.name for band in Band]
    }

@app.post("/api/vfo/swap")
async def swap_vfo():
    """Swap VFO-A and VFO-B."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        radio.swap_vfo()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vfo/a-to-b")
async def vfo_a_to_b():
    """Copy VFO-A to VFO-B."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    
    try:
        radio.vfo_a_to_b()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def update_config(req: ConfigRequest):
    """Update radio connection configuration."""
    global radio_config
    
    # Disconnect current radio
    if radio_connected:
        await disconnect_radio()
    
    # Update config
    radio_config["port"] = req.port
    radio_config["baudrate"] = req.baudrate
    
    # Attempt reconnection
    await connect_radio()
    
    return {"success": True, "config": radio_config}

@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    return {
        "config": radio_config,
        "connected": radio_connected
    }

# ── WebSocket Endpoint ───────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await manager.connect(websocket)
    try:
        # Send initial status
        if radio_connected and radio:
            status = radio.get_status()
            await websocket.send_text(json.dumps({
                "type": "status",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "frequency_a": status.frequency_a,
                    "frequency_b": status.frequency_b,
                    "mode": status.mode,
                    "tx_active": status.tx_active,
                    "squelch_open": status.squelch_open,
                    "s_meter": status.s_meter,
                    "power_output": status.power_output,
                    "swr": status.swr,
                    "tx_lockout": tx_lockout
                }
            }))
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# ── Startup/Shutdown ─────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize radio connection on startup."""
    logger.info("FT-991A Web GUI starting up...")
    if radio_config.get("auto_reconnect", True):
        await connect_radio()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown - ensure PTT is off."""
    logger.info("FT-991A Web GUI shutting down...")
    if radio_connected and radio:
        try:
            radio.ptt_off()  # Safety
            radio.disconnect()
        except:
            pass

# ── Main Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    # Parse command line args
    import argparse
    parser = argparse.ArgumentParser(description="FT-991A Web GUI Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8991, help="Port to bind to")
    parser.add_argument("--radio-port", default="/dev/ttyUSB0", help="Radio serial port")
    parser.add_argument("--baud", type=int, default=38400, help="Radio baud rate")
    parser.add_argument("--no-auto-connect", action="store_true", help="Don't auto-connect to radio")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()
    
    # Update config from args
    radio_config["port"] = args.radio_port
    radio_config["baudrate"] = args.baud
    radio_config["auto_reconnect"] = not args.no_auto_connect
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info(f"Starting FT-991A Web GUI on {args.host}:{args.port}")
    logger.info(f"Radio config: {args.radio_port} @ {args.baud} baud")
    
    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        reload=False
    )