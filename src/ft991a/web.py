#!/usr/bin/env python3
"""
FT-991A Web GUI Server
======================
FastAPI + WebSocket server for real-time control of Yaesu FT-991A ham radio.
"""

import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

import serial.tools.list_ports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .cat import FT991A, Band, Mode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("ft991a-web.log")],
)
logger = logging.getLogger(__name__)

# Try to import SoapySDR - gracefully handle if not available
try:
    import numpy as np
    import SoapySDR

    SOAPY_SDR_AVAILABLE = True
    logger.info("SoapySDR available - SDR support enabled")
except ImportError:
    SOAPY_SDR_AVAILABLE = False
    logger.warning("SoapySDR not available - SDR functionality disabled")

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


class SetupTestRequest(BaseModel):
    port: str
    baudrate: int


class SetupSaveRequest(BaseModel):
    port: str
    baudrate: int
    callsign: Optional[str] = None


class ScanRequest(BaseModel):
    start_freq: int  # Start frequency in Hz
    end_freq: int  # End frequency in Hz
    step: int  # Step size in Hz
    threshold: int  # S-meter threshold (0-255)


class MemoryRecallRequest(BaseModel):
    channel: int  # 1-99


class MemoryStoreRequest(BaseModel):
    channel: int  # 1-99


class MemoryClearRequest(BaseModel):
    channel: int  # 1-99


# ── Global State ─────────────────────────────────────────────


app = FastAPI(title="FT-991A Web GUI", version="0.2.0")
radio: Optional[FT991A] = None
radio_connected = False
tx_lockout = False  # Safety: prevents accidental PTT
websocket_clients: Set[WebSocket] = set()

# Scanner state
scan_active = False
scan_task: Optional[asyncio.Task] = None

# Configuration
radio_config = {"port": "/dev/ttyUSB0", "baudrate": 38400, "auto_reconnect": True}

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


class AudioConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.audio_process = None  # asyncio.subprocess.Process
        self.streaming_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

        # Start audio streaming if this is the first client
        if len(self.active_connections) == 1:
            await self.start_audio_stream()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Stop audio streaming if no more clients
        if len(self.active_connections) == 0:
            asyncio.ensure_future(self.stop_audio_stream())

    async def broadcast_audio(self, data: bytes):
        if not self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_bytes(data)
            except Exception as e:
                logger.warning(f"Audio WebSocket send failed: {e}")
                dead_connections.append(connection)

        for conn in dead_connections:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

    async def start_audio_stream(self):
        """Start audio capture from PCM2903B CODEC using async subprocess"""
        if self.audio_process or self.streaming_task:
            return

        try:
            # Try audio devices in order
            audio_devices = [
                "hw:CARD=CODEC",
                "hw:CARD=CODEC,DEV=0",
                "plughw:CARD=CODEC,DEV=0",
                "hw:2,0",
                "hw:1,0",
            ]

            device_found = None
            for device in audio_devices:
                try:
                    test = await asyncio.create_subprocess_exec(
                        "arecord",
                        "-D",
                        device,
                        "-f",
                        "S16_LE",
                        "-r",
                        "48000",
                        "-c",
                        "1",
                        "-t",
                        "raw",
                        "-d",
                        "1",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(test.wait(), timeout=3)
                    if test.returncode == 0:
                        device_found = device
                        logger.info(f"Audio device found: {device}")
                        break
                except (asyncio.TimeoutError, Exception):
                    try:
                        test.kill()
                    except:
                        pass
                    continue

            if not device_found:
                logger.error("No compatible audio capture device found")
                return

            # Start async audio capture
            self.audio_process = await asyncio.create_subprocess_exec(
                "arecord",
                "-D",
                device_found,
                "-f",
                "S16_LE",
                "-r",
                "48000",
                "-c",
                "1",
                "-t",
                "raw",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            self.streaming_task = asyncio.create_task(self._stream_audio())
            logger.info(f"Audio streaming started: {device_found}")

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            await self.stop_audio_stream()

    async def _stream_audio(self):
        """Non-blocking audio streaming to WebSocket clients"""
        chunk_size = 4096  # ~42ms at 48kHz mono 16-bit

        try:
            while self.audio_process and self.audio_process.returncode is None:
                data = await self.audio_process.stdout.read(chunk_size)
                if not data:
                    break
                await self.broadcast_audio(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
        finally:
            await self.stop_audio_stream()

    async def stop_audio_stream(self):
        """Stop audio capture and streaming"""
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
        self.streaming_task = None

        if self.audio_process:
            try:
                self.audio_process.terminate()
                await asyncio.wait_for(self.audio_process.wait(), timeout=2)
            except (asyncio.TimeoutError, Exception):
                try:
                    self.audio_process.kill()
                except:
                    pass
            self.audio_process = None

        logger.info("Audio streaming stopped")


class SDRConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.sdr_device = None
        self.streaming_task: Optional[asyncio.Task] = None
        self.bandwidth = 2000000  # Default 2 MHz
        self.fft_size = 1024  # Default FFT size
        self.frame_rate = 10  # Target ~10 fps

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

        # Start SDR streaming if this is the first client
        if len(self.active_connections) == 1:
            await self.start_sdr_stream()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Stop SDR streaming if no more clients
        if len(self.active_connections) == 0:
            asyncio.ensure_future(self.stop_sdr_stream())

    async def broadcast_sdr_data(self, data: dict):
        if not self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data))
            except Exception as e:
                logger.warning(f"SDR WebSocket send failed: {e}")
                dead_connections.append(connection)

        for conn in dead_connections:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

    async def start_sdr_stream(self):
        """Start SDR streaming from RSP2pro using SoapySDR"""
        if not SOAPY_SDR_AVAILABLE:
            logger.error("Cannot start SDR stream - SoapySDR not available")
            await self.broadcast_sdr_data({"type": "sdr_error", "message": "SoapySDR not available"})
            return

        if self.sdr_device or self.streaming_task:
            return

        try:
            # Initialize SDRplay RSP2pro
            logger.info("Initializing SDRplay RSP2pro...")

            # Create device handle
            args = dict(driver="sdrplay")
            self.sdr_device = SoapySDR.Device(args)

            # Configure device
            self.sdr_device.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.bandwidth)
            self.sdr_device.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, 14074000)  # Default to 20m FT8
            self.sdr_device.setGain(SoapySDR.SOAPY_SDR_RX, 0, "IFGR", 40)  # IF gain
            self.sdr_device.setGain(SoapySDR.SOAPY_SDR_RX, 0, "RFGR", 7)  # RF gain
            self.sdr_device.setAntenna(SoapySDR.SOAPY_SDR_RX, 0, "RX")

            # Setup stream
            rx_stream = self.sdr_device.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
            self.sdr_device.activateStream(rx_stream)

            # Start streaming task
            self.streaming_task = asyncio.create_task(self._stream_sdr_data(rx_stream))

            logger.info(f"SDR streaming started: {self.bandwidth/1e6:.1f} MHz bandwidth")

            # Notify clients
            await self.broadcast_sdr_data(
                {
                    "type": "sdr_info",
                    "bandwidth": self.bandwidth,
                    "fft_size": self.fft_size,
                    "sample_rate": self.bandwidth,
                    "center_freq": 14074000,
                }
            )

        except Exception as e:
            logger.error(f"Failed to start SDR stream: {e}")
            await self.stop_sdr_stream()
            await self.broadcast_sdr_data({"type": "sdr_error", "message": f"SDR initialization failed: {str(e)}"})

    async def _stream_sdr_data(self, rx_stream):
        """Stream IQ data and perform FFT analysis"""
        buffer_size = self.fft_size

        try:
            while self.sdr_device:
                # Read IQ samples
                buffer = np.array([0] * buffer_size, np.complex64)
                sr = self.sdr_device.readStream(rx_stream, [buffer], buffer_size)

                if sr.ret != buffer_size:
                    continue

                # Perform FFT
                fft_data = np.fft.fftshift(np.fft.fft(buffer))
                power_spectrum = 20 * np.log10(np.abs(fft_data) + 1e-10)  # Convert to dB

                # Get current radio frequency for centering
                center_freq = 14074000  # Default
                if radio_connected and radio:
                    try:
                        status = radio.get_status()
                        center_freq = status.frequency_a
                    except:
                        pass

                # Update SDR center frequency to match radio
                try:
                    current_sdr_freq = self.sdr_device.getFrequency(SoapySDR.SOAPY_SDR_RX, 0)
                    if abs(current_sdr_freq - center_freq) > 1000:  # More than 1 kHz difference
                        self.sdr_device.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, center_freq)
                except:
                    pass

                # Broadcast FFT data
                await self.broadcast_sdr_data(
                    {
                        "type": "sdr_fft",
                        "bins": power_spectrum.tolist(),
                        "center_freq": center_freq,
                        "bandwidth": self.bandwidth,
                        "timestamp": time.time(),
                    }
                )

                # Control frame rate
                await asyncio.sleep(1.0 / self.frame_rate)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"SDR streaming error: {e}")
            await self.broadcast_sdr_data({"type": "sdr_error", "message": f"Streaming error: {str(e)}"})
        finally:
            await self.stop_sdr_stream()

    async def stop_sdr_stream(self):
        """Stop SDR streaming and cleanup"""
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass
        self.streaming_task = None

        if self.sdr_device:
            try:
                # Close all streams
                self.sdr_device.closeStream()
                self.sdr_device.deactivateStream()
                self.sdr_device = None
            except:
                pass

        logger.info("SDR streaming stopped")

        # Notify clients
        await self.broadcast_sdr_data({"type": "sdr_status", "status": "stopped"})

    async def set_bandwidth(self, bandwidth_hz: int):
        """Change SDR bandwidth"""
        valid_bandwidths = [200000, 500000, 1000000, 2000000, 5000000, 10000000]
        if bandwidth_hz not in valid_bandwidths:
            raise ValueError(f"Invalid bandwidth. Must be one of: {valid_bandwidths}")

        self.bandwidth = bandwidth_hz

        # Restart stream with new bandwidth if active
        if self.sdr_device:
            await self.stop_sdr_stream()
            await self.start_sdr_stream()

    async def set_fft_size(self, fft_size: int):
        """Change FFT size"""
        valid_sizes = [256, 512, 1024, 2048]
        if fft_size not in valid_sizes:
            raise ValueError(f"Invalid FFT size. Must be one of: {valid_sizes}")

        self.fft_size = fft_size


manager = ConnectionManager()
audio_manager = AudioConnectionManager()
sdr_manager = SDRConnectionManager()

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
            await manager.broadcast(
                {
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
                        "tx_lockout": tx_lockout,
                    },
                }
            )

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
                "tx_lockout": tx_lockout,
            },
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
    return {"modes": [mode.name for mode in Mode]}


@app.get("/api/bands")
async def get_bands():
    """Get available bands."""
    return {"bands": [band.name for band in Band]}


@app.get("/api/audio/devices")
async def get_audio_devices():
    """List available ALSA capture devices for audio setup."""
    try:
        # Get detailed device list
        result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            return {"success": False, "error": "arecord not available"}

        devices = []
        current_card = None

        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("card "):
                # Parse card line: "card 1: Device [USB Audio CODEC], device 0: USB Audio [USB Audio]"
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    card_info = parts[0]  # "card 1"
                    device_info = parts[1].strip()  # "Device [USB Audio CODEC]"

                    card_num = card_info.split()[1]
                    if "[" in device_info and "]" in device_info:
                        device_name = device_info.split("[")[1].split("]")[0]
                    else:
                        device_name = device_info

                    current_card = {"card_num": int(card_num), "name": device_name, "devices": []}

            elif line.startswith("  Subdevices:") and current_card:
                # Parse subdevice info
                subdevice_count = line.split(":")[1].strip().split("/")[0]
                current_card["subdevices"] = int(subdevice_count)

                # Create device entry
                device_entry = {
                    "card": current_card["card_num"],
                    "device": 0,  # Usually device 0 for audio
                    "name": current_card["name"],
                    "hw_name": f"hw:{current_card['card_num']},0",
                    "card_name": f"hw:CARD={current_card['name'].replace(' ', '').replace('-', '')[:8]}",
                    "is_usb_codec": "USB Audio CODEC" in current_card["name"] or "PCM2903B" in current_card["name"],
                    "subdevices": current_card.get("subdevices", 1),
                }
                devices.append(device_entry)
                current_card = None

        # Also get PCM device list for additional info
        pcm_result = subprocess.run(["arecord", "-L"], capture_output=True, text=True)
        pcm_info = pcm_result.stdout if pcm_result.returncode == 0 else ""

        return {"success": True, "devices": devices, "raw_output": result.stdout, "pcm_info": pcm_info}

    except Exception as e:
        return {"success": False, "error": str(e)}


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


@app.post("/api/tuner/on")
async def tuner_on():
    """Turn antenna tuner ON."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    try:
        radio.tuner_on()
        return {"success": True, "tuner": "on"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tuner/off")
async def tuner_off():
    """Turn antenna tuner OFF."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    try:
        radio.tuner_off()
        return {"success": True, "tuner": "off"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tuner/start")
async def tuner_start():
    """Start antenna auto-tune."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    try:
        radio.tuner_start()
        return {"success": True, "tuner": "tuning"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tuner/status")
async def tuner_status():
    """Get tuner status."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")
    try:
        status = radio.tuner_status()
        labels = {"0": "off", "1": "on", "2": "tuning"}
        return {"status": labels.get(status, "unknown"), "raw": status}
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
    return {"config": radio_config, "connected": radio_connected}


# ── Memory Management Endpoints ──────────────────────────────


@app.get("/api/memory/list")
async def get_memory_list():
    """Scan and list all memory channels (MR001; through MR099;)."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")

    try:
        logger.info("Starting memory channel scan (MR001-MR099)")
        channels = {}

        # Scan all 99 memory channels
        for ch in range(1, 100):
            channel_str = f"{ch:03d}"

            try:
                # Send MR command to read memory channel
                mr_command = f"MR{channel_str};"
                logger.debug(f"Sending CAT: {mr_command}")

                # Use raw serial for memory commands
                radio.serial.write(mr_command.encode())
                response = radio.serial.readline().decode().strip()

                logger.debug(f"MR{channel_str} response: {response}")

                # Parse MR response format
                if response.startswith(f"MR{channel_str}") and len(response) > 10:
                    # Parse memory data from response
                    # Format: MR001+14074000000100200000000000000000000000000;
                    #         MRccc+ffffffffmmm...other...

                    try:
                        # Extract frequency (positions 6-16, 11 digits)
                        freq_str = response[6:17]  # 11 digit frequency in Hz
                        frequency = int(freq_str) if freq_str.isdigit() else 0

                        # Extract mode (position 17-19, 3 digits)
                        mode_code = response[17:20] if len(response) > 19 else "000"
                        mode_map = {
                            "001": "LSB",
                            "002": "USB",
                            "003": "CW",
                            "004": "FM",
                            "005": "AM",
                            "006": "RTTY-LSB",
                            "007": "CW-R",
                            "008": "DATA-LSB",
                            "009": "RTTY-USB",
                            "010": "DATA-FM",
                            "011": "FM-N",
                            "012": "DATA-USB",
                            "013": "AM-N",
                            "014": "C4FM",
                        }
                        mode = mode_map.get(mode_code, "UNK")

                        # Store channel data if frequency is valid
                        if frequency > 0:
                            channels[channel_str] = {
                                "channel": channel_str,
                                "frequency": frequency,
                                "mode": mode,
                                "mode_code": mode_code,
                                "raw_response": response,
                                "label": "",  # TODO: Implement MT command for labels
                                "ctcss": "OFF",  # TODO: Parse CTCSS from response
                                "is_current": False,  # Will be updated if needed
                            }
                            logger.debug(f"Memory {channel_str}: {frequency} Hz, {mode}")

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse memory {channel_str} response: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Error reading memory {channel_str}: {e}")
                continue

        logger.info(f"Memory scan completed: {len(channels)} programmed channels found")

        return {"success": True, "channels": channels, "total_programmed": len(channels), "total_capacity": 99}

    except Exception as e:
        logger.error(f"Memory scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory scan failed: {str(e)}")


@app.post("/api/memory/recall")
async def recall_memory_channel(req: MemoryRecallRequest):
    """Recall memory channel to VFO-A (MC command)."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")

    if req.channel < 1 or req.channel > 99:
        raise HTTPException(status_code=400, detail="Channel must be between 1 and 99")

    try:
        channel_str = f"{req.channel:03d}"
        mc_command = f"MC{channel_str};"

        logger.info(f"Recalling memory channel {channel_str}")
        logger.debug(f"Sending CAT: {mc_command}")

        # Send MC command to recall memory
        radio.serial.write(mc_command.encode())

        # Give radio time to process
        await asyncio.sleep(0.1)

        # Verify by reading current frequency
        try:
            status = radio.get_status()
            logger.info(f"Memory {channel_str} recalled - VFO-A: {status.frequency_a} Hz")
        except:
            pass

        return {"success": True, "channel": channel_str, "message": f"Memory channel {channel_str} recalled to VFO-A"}

    except Exception as e:
        logger.error(f"Memory recall failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory recall failed: {str(e)}")


@app.post("/api/memory/store")
async def store_to_memory_channel(req: MemoryStoreRequest):
    """Store current VFO-A to memory channel (MW command)."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")

    if req.channel < 1 or req.channel > 99:
        raise HTTPException(status_code=400, detail="Channel must be between 1 and 99")

    try:
        channel_str = f"{req.channel:03d}"

        # Get current VFO-A status first
        status = radio.get_status()
        current_freq = status.frequency_a
        current_mode = status.mode

        logger.info(f"Storing VFO-A to memory {channel_str}: {current_freq} Hz, {current_mode}")

        # Send MW command to store current VFO-A to memory
        # MW command format: MW{ccc}; - stores current VFO-A to channel ccc
        mw_command = f"MW{channel_str};"
        logger.debug(f"Sending CAT: {mw_command}")

        radio.serial.write(mw_command.encode())

        # Give radio time to process
        await asyncio.sleep(0.2)

        return {
            "success": True,
            "channel": channel_str,
            "stored_frequency": current_freq,
            "stored_mode": current_mode,
            "message": f"VFO-A stored to memory channel {channel_str}",
        }

    except Exception as e:
        logger.error(f"Memory store failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory store failed: {str(e)}")


@app.post("/api/memory/clear")
async def clear_memory_channel(req: MemoryClearRequest):
    """Clear/delete a memory channel."""
    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")

    if req.channel < 1 or req.channel > 99:
        raise HTTPException(status_code=400, detail="Channel must be between 1 and 99")

    try:
        channel_str = f"{req.channel:03d}"

        logger.info(f"Clearing memory channel {channel_str}")

        # The FT-991A doesn't have a direct "clear memory" command
        # We need to store an invalid/empty frequency to clear it
        # Alternative: Use MW with a specific "empty" pattern

        # Method: Store a very low frequency (30 kHz) which effectively "clears" the channel
        # First set VFO to minimum frequency, then store, then restore VFO
        original_status = radio.get_status()
        original_freq = original_status.frequency_a

        # Set VFO-A to minimum frequency (30 kHz)
        radio.set_frequency_a(30000)
        await asyncio.sleep(0.1)

        # Store this "empty" frequency to memory
        mw_command = f"MW{channel_str};"
        radio.serial.write(mw_command.encode())
        await asyncio.sleep(0.2)

        # Restore original VFO-A frequency
        radio.set_frequency_a(original_freq)

        logger.info(f"Memory channel {channel_str} cleared (set to 30 kHz)")

        return {"success": True, "channel": channel_str, "message": f"Memory channel {channel_str} cleared"}

    except Exception as e:
        logger.error(f"Memory clear failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory clear failed: {str(e)}")


# ── Scanner Endpoints ────────────────────────────────────────


@app.post("/api/scan")
async def start_scan(req: ScanRequest):
    """Start frequency scanning."""
    global scan_active, scan_task

    if not radio_connected or not radio:
        raise HTTPException(status_code=503, detail="Radio not connected")

    if scan_active:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    # Validate parameters
    if req.start_freq >= req.end_freq:
        raise HTTPException(status_code=400, detail="Start frequency must be less than end frequency")

    if req.start_freq < 30000 or req.end_freq > 470000000:
        raise HTTPException(status_code=400, detail="Frequency range must be between 30 kHz and 470 MHz")

    if req.step < 100 or req.step > 1000000:
        raise HTTPException(status_code=400, detail="Step size must be between 100 Hz and 1 MHz")

    try:
        scan_active = True
        scan_task = asyncio.create_task(scan_frequency_range(req))

        logger.info(f"Started scan: {req.start_freq}-{req.end_freq} Hz, step {req.step} Hz, threshold {req.threshold}")

        return {
            "success": True,
            "message": "Scan started",
            "parameters": {
                "start_freq": req.start_freq,
                "end_freq": req.end_freq,
                "step": req.step,
                "threshold": req.threshold,
                "estimated_points": int((req.end_freq - req.start_freq) / req.step),
            },
        }

    except Exception as e:
        scan_active = False
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/stop")
async def stop_scan():
    """Stop current frequency scan."""
    global scan_active, scan_task

    if not scan_active:
        return {"success": True, "message": "No scan in progress"}

    scan_active = False

    if scan_task:
        scan_task.cancel()
        try:
            await scan_task
        except asyncio.CancelledError:
            pass
        scan_task = None

    # Broadcast scan stopped
    await manager.broadcast({"type": "scan_complete", "message": "Scan stopped by user"})

    logger.info("Scan stopped by user request")
    return {"success": True, "message": "Scan stopped"}


async def scan_frequency_range(req: ScanRequest):
    """Background task to perform the frequency scan."""
    global scan_active

    try:
        current_freq = req.start_freq
        scan_count = 0
        active_count = 0
        start_time = time.time()

        while scan_active and current_freq <= req.end_freq:
            try:
                # Set radio frequency
                radio.set_frequency_a(current_freq)

                # Wait for radio to settle (200ms as specified)
                await asyncio.sleep(0.2)

                # Read S-meter
                status = radio.get_status()
                s_meter = status.s_meter
                mode = status.mode

                scan_count += 1

                # Check if signal is above threshold
                is_active = s_meter >= req.threshold
                if is_active:
                    active_count += 1

                # Broadcast progress
                await manager.broadcast(
                    {
                        "type": "scan_progress",
                        "frequency": current_freq,
                        "s_meter": s_meter,
                        "mode": mode,
                        "is_active": is_active,
                        "scan_count": scan_count,
                        "active_count": active_count,
                        "progress": ((current_freq - req.start_freq) / (req.end_freq - req.start_freq)) * 100,
                    }
                )

                # Move to next frequency
                current_freq += req.step

                # Small delay to prevent overwhelming the radio
                await asyncio.sleep(0.05)

            except Exception as e:
                logger.error(f"Error during scan at {current_freq} Hz: {e}")
                # Continue scan despite individual frequency errors
                current_freq += req.step
                continue

        # Scan completed successfully
        if scan_active:  # Only if not cancelled
            elapsed_time = time.time() - start_time

            await manager.broadcast(
                {
                    "type": "scan_complete",
                    "message": f"Scan completed: {scan_count} frequencies, {active_count} active signals",
                    "summary": {
                        "total_frequencies": scan_count,
                        "active_signals": active_count,
                        "elapsed_time": round(elapsed_time, 1),
                        "scan_rate": round(scan_count / elapsed_time, 1) if elapsed_time > 0 else 0,
                    },
                }
            )

            logger.info(f"Scan completed: {scan_count} frequencies in {elapsed_time:.1f}s, {active_count} active")

    except asyncio.CancelledError:
        logger.info("Scan cancelled")
        raise
    except Exception as e:
        logger.error(f"Scan error: {e}")
        await manager.broadcast({"type": "scan_error", "message": str(e)})
    finally:
        scan_active = False


# ── Setup Wizard Endpoints ───────────────────────────────────


@app.get("/api/setup/ports")
async def get_setup_ports():
    """List available serial ports for setup wizard."""
    try:
        ports = []
        for port in serial.tools.list_ports.comports():
            port_info = {
                "device": port.device,
                "description": port.description or "Unknown device",
                "manufacturer": port.manufacturer or "Unknown",
                "vid": port.vid,
                "pid": port.pid,
            }
            # Add helpful info for common devices
            if "CP210" in port.description or "Silicon Labs" in (port.manufacturer or ""):
                port_info["likely_ft991a"] = True
                port_info["description"] += " (CP2105 - likely FT-991A)"
            else:
                port_info["likely_ft991a"] = False

            ports.append(port_info)

        return {"success": True, "ports": ports}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/setup/test")
async def test_setup_connection(req: SetupTestRequest):
    """Test a port+baud combination for setup wizard."""
    test_radio = None
    try:
        # Create temporary radio connection
        test_radio = FT991A(req.port, req.baudrate)

        # Attempt connection
        if test_radio.connect():
            # Test basic CAT command
            status = test_radio.get_status()

            # Get radio identification if possible
            radio_info = {
                "model": "FT-991A",  # We know this from the CAT implementation
                "frequency_a": status.frequency_a,
                "mode": status.mode,
                "connected": True,
            }

            test_radio.disconnect()
            return {"success": True, "connected": True, "radio_info": radio_info}
        else:
            if test_radio:
                test_radio.disconnect()
            return {"success": False, "connected": False, "error": "No response from radio"}

    except Exception as e:
        if test_radio:
            try:
                test_radio.disconnect()
            except:
                pass
        return {"success": False, "connected": False, "error": str(e)}


@app.post("/api/setup/save")
async def save_setup_config(req: SetupSaveRequest):
    """Save setup wizard configuration."""
    global radio_config

    try:
        # Disconnect current radio if connected
        if radio_connected:
            await disconnect_radio()

        # Update configuration
        radio_config["port"] = req.port
        radio_config["baudrate"] = req.baudrate

        # Store callsign in config if provided
        if req.callsign:
            radio_config["callsign"] = req.callsign.upper()

        # Attempt connection
        await connect_radio()

        return {"success": True, "connected": radio_connected, "config": radio_config}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ── WebSocket Endpoint ───────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await manager.connect(websocket)
    try:
        # Send initial status
        if radio_connected and radio:
            status = radio.get_status()
            await websocket.send_text(
                json.dumps(
                    {
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
                            "tx_lockout": tx_lockout,
                        },
                    }
                )
            )

        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    """WebSocket for audio streaming from PCM2903B CODEC."""
    await audio_manager.connect(websocket)
    try:
        # Send initial audio info
        await websocket.send_text(
            json.dumps(
                {"type": "audio_info", "format": "S16_LE", "sample_rate": 48000, "channels": 1, "chunk_size": 4096}
            )
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                message = await websocket.receive_text()
                # Handle client control messages if needed
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                # Client disconnected or sent binary data
                break

    except WebSocketDisconnect:
        audio_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Audio WebSocket error: {e}")
        audio_manager.disconnect(websocket)


@app.websocket("/ws/sdr")
async def sdr_websocket_endpoint(websocket: WebSocket):
    """WebSocket for SDR streaming from RSP2pro."""
    await sdr_manager.connect(websocket)
    try:
        # Send initial SDR info
        await websocket.send_text(
            json.dumps(
                {
                    "type": "sdr_info",
                    "driver": "sdrplay",
                    "device": "RSP2pro",
                    "serial": "1717050C11",
                    "available": SOAPY_SDR_AVAILABLE,
                    "bandwidth": sdr_manager.bandwidth,
                    "fft_size": sdr_manager.fft_size,
                }
            )
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)

                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif data.get("type") == "set_bandwidth":
                    try:
                        await sdr_manager.set_bandwidth(data.get("bandwidth", 2000000))
                        await websocket.send_text(
                            json.dumps({"type": "bandwidth_changed", "bandwidth": sdr_manager.bandwidth})
                        )
                    except ValueError as e:
                        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
                elif data.get("type") == "set_fft_size":
                    try:
                        await sdr_manager.set_fft_size(data.get("fft_size", 1024))
                        await websocket.send_text(
                            json.dumps({"type": "fft_size_changed", "fft_size": sdr_manager.fft_size})
                        )
                    except ValueError as e:
                        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))

            except Exception as e:
                logger.error(f"SDR WebSocket message error: {e}")
                break

    except WebSocketDisconnect:
        sdr_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"SDR WebSocket error: {e}")
        sdr_manager.disconnect(websocket)


# ── SDR API Endpoints ────────────────────────────────────────


@app.get("/api/sdr/status")
async def get_sdr_status():
    """Get SDR device status and capabilities."""
    return {
        "available": SOAPY_SDR_AVAILABLE,
        "active_connections": len(sdr_manager.active_connections) if sdr_manager else 0,
        "streaming": sdr_manager.sdr_device is not None if sdr_manager else False,
        "bandwidth": sdr_manager.bandwidth if sdr_manager else 2000000,
        "fft_size": sdr_manager.fft_size if sdr_manager else 1024,
        "supported_bandwidths": [200000, 500000, 1000000, 2000000, 5000000, 10000000],
        "supported_fft_sizes": [256, 512, 1024, 2048],
    }


@app.post("/api/sdr/bandwidth")
async def set_sdr_bandwidth(data: dict):
    """Set SDR bandwidth."""
    if not SOAPY_SDR_AVAILABLE:
        raise HTTPException(status_code=503, detail="SoapySDR not available")

    try:
        bandwidth = data.get("bandwidth")
        if not bandwidth:
            raise HTTPException(status_code=400, detail="Bandwidth parameter required")

        await sdr_manager.set_bandwidth(int(bandwidth))
        return {"success": True, "bandwidth": sdr_manager.bandwidth}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sdr/fft_size")
async def set_sdr_fft_size(data: dict):
    """Set SDR FFT size."""
    if not SOAPY_SDR_AVAILABLE:
        raise HTTPException(status_code=503, detail="SoapySDR not available")

    try:
        fft_size = data.get("fft_size")
        if not fft_size:
            raise HTTPException(status_code=400, detail="FFT size parameter required")

        await sdr_manager.set_fft_size(int(fft_size))
        return {"success": True, "fft_size": sdr_manager.fft_size}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Startup/Shutdown ─────────────────────────────────────────


@app.on_event("startup")
async def startup_event():
    """Initialize radio connection on startup."""
    logger.info("FT-991A Web GUI starting up...")
    if radio_config.get("auto_reconnect", True):
        await connect_radio()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown - ensure PTT is off and audio/SDR stopped."""
    logger.info("FT-991A Web GUI shutting down...")

    # Stop audio streaming
    await audio_manager.stop_audio_stream()

    # Stop SDR streaming
    await sdr_manager.stop_sdr_stream()

    # Stop any active scan
    global scan_active, scan_task
    if scan_active and scan_task:
        scan_active = False
        scan_task.cancel()
        try:
            await scan_task
        except asyncio.CancelledError:
            pass

    # Disconnect radio safely
    if radio_connected and radio:
        try:
            radio.ptt_off()  # Safety
            radio.disconnect()
        except:
            pass


# ── Main Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    # Parse command line args
    import argparse

    import uvicorn

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

    uvicorn.run("server:app", host=args.host, port=args.port, log_level=args.log_level.lower(), reload=False)
