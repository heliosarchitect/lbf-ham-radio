#!/usr/bin/env python3
"""
FT-991A Broadcast Module
========================
TTS-to-radio broadcast capability using the PCM2903B CODEC for audio routing.

The PCM2903B USB audio device provides the bridge between computer audio
and the FT-991A's data port for digital audio input/output.

CRITICAL SAFETY NOTICE:
- All transmit functions require --confirm flag
- Licensed amateur radio operator must be physically present
- Transmissions must use proper callsign identification (KO4TUV)
- Operator is responsible for all RF emissions and compliance

Hardware Setup:
- PCM2903B CODEC connected to FT-991A ACC connector
- TX audio: Computer → PCM2903B → FT-991A ACC pin 13 (PKS)
- RX audio: FT-991A ACC pin 11 (PKD) → PCM2903B → Computer
"""

import logging
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional, Union

try:
    import pyttsx3

    TTS_ENGINE = "pyttsx3"
except ImportError:
    pyttsx3 = None
    TTS_ENGINE = "espeak"

try:
    import numpy as np
    import sounddevice as sd

    AUDIO_ENABLED = True
except ImportError:
    sd = None
    np = None
    AUDIO_ENABLED = False

from .cat import FT991A

logger = logging.getLogger(__name__)


class BroadcastError(Exception):
    """Base exception for broadcast operations."""


class AudioDeviceError(BroadcastError):
    """Audio device related errors."""


class TTSError(BroadcastError):
    """Text-to-speech related errors."""


class Broadcaster:
    """
    TTS-to-radio broadcast capability for the FT-991A.

    Provides text-to-speech conversion and audio routing to the radio's
    data port via the PCM2903B USB audio CODEC.

    Usage:
        radio = FT991A('/dev/ttyUSB0')
        radio.connect()

        broadcaster = Broadcaster(radio)

        # Convert text to audio file
        wav_path = broadcaster.text_to_audio("Hello world", voice="default")

        # Play audio to radio (requires confirm=True for TX)
        broadcaster.play_to_radio(wav_path)

        # Full pipeline with safety check
        broadcaster.broadcast("CQ CQ de KO4TUV", confirm=True)
    """

    def __init__(
        self, radio: FT991A, sample_rate: int = 48000, device_name: Optional[str] = None
    ):
        """
        Initialize broadcaster.

        Args:
            radio: Connected FT991A instance
            sample_rate: Audio sample rate (48kHz default for PCM2903B)
            device_name: Specific audio device name (auto-detect PCM2903B if None)
        """
        self.radio = radio
        self.sample_rate = sample_rate
        self.device_name = device_name
        self._audio_device_id = None
        self._tts_engine = None

        # Find PCM2903B audio device
        self._find_audio_device()

        # Initialize TTS engine
        self._init_tts()

    def _find_audio_device(self):
        """Find the PCM2903B USB audio device."""
        if not AUDIO_ENABLED:
            logger.warning(
                "Audio libraries not available. Install with: pip install 'ft991a-control[audio]'"
            )
            return

        try:
            devices = sd.query_devices()

            # Look for PCM2903B device
            for idx, device in enumerate(devices):
                if (
                    self.device_name
                    and self.device_name.lower() in device["name"].lower()
                ) or (
                    "PCM2903" in device["name"] or "USB Audio CODEC" in device["name"]
                ):
                    if device["max_output_channels"] > 0:  # Can output audio
                        self._audio_device_id = idx
                        logger.info(f"Found audio device: {device['name']} (ID: {idx})")
                        return

            # Fallback to default output device
            default_device = sd.query_devices(kind="output")
            self._audio_device_id = default_device["index"]
            logger.warning(
                f"PCM2903B not found, using default: {default_device['name']}"
            )

        except Exception as e:
            logger.error(f"Audio device detection failed: {e}")
            raise AudioDeviceError(f"Could not find suitable audio device: {e}")

    def _init_tts(self):
        """Initialize the TTS engine."""
        if TTS_ENGINE == "pyttsx3" and pyttsx3:
            try:
                self._tts_engine = pyttsx3.init()
                # Configure for clear speech
                self._tts_engine.setProperty("rate", 150)  # Slightly slower for clarity
                self._tts_engine.setProperty("volume", 0.9)
                logger.info("TTS initialized: pyttsx3")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3: {e}")
                self._tts_engine = None
        else:
            logger.info("TTS fallback: espeak (system dependency)")

    def text_to_audio(self, text: str, voice: str = "default") -> str:
        """
        Convert text to WAV audio file.

        Args:
            text: Text to convert to speech
            voice: Voice to use (implementation dependent)

        Returns:
            Path to generated WAV file

        Raises:
            TTSError: If TTS conversion fails
        """
        if not text.strip():
            raise TTSError("Empty text provided")

        # Create temporary WAV file
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = temp_wav.name
        temp_wav.close()

        try:
            if self._tts_engine and TTS_ENGINE == "pyttsx3":
                # Use pyttsx3 engine
                self._tts_engine.save_to_file(text, wav_path)
                self._tts_engine.runAndWait()

            else:
                # Fallback to espeak system command
                cmd = [
                    "espeak",
                    "-s",
                    "150",  # Speed (words per minute)
                    "-v",
                    voice if voice != "default" else "en",
                    "-w",
                    wav_path,  # Write to file
                    text,
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise TTSError(f"espeak failed: {result.stderr}")

            # Verify the file was created
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                raise TTSError("TTS did not generate audio file")

            logger.info(
                f"Generated TTS audio: {wav_path} ({os.path.getsize(wav_path)} bytes)"
            )
            return wav_path

        except Exception as e:
            # Clean up on failure
            if os.path.exists(wav_path):
                os.unlink(wav_path)
            raise TTSError(f"TTS generation failed: {e}")

    def play_to_radio(self, wav_path: Union[str, Path]) -> bool:
        """
        Route WAV audio to the radio via PCM2903B.

        Args:
            wav_path: Path to WAV file to play

        Returns:
            True if playback succeeded

        Raises:
            AudioDeviceError: If audio playback fails
        """
        wav_path = Path(wav_path)
        if not wav_path.exists():
            raise AudioDeviceError(f"WAV file not found: {wav_path}")

        if not AUDIO_ENABLED:
            raise AudioDeviceError("Audio libraries not available")

        if self._audio_device_id is None:
            raise AudioDeviceError("No audio device configured")

        try:
            # Read WAV file
            with wave.open(str(wav_path), "rb") as wf:
                sample_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

                # Convert to numpy array
                if wf.getsampwidth() == 2:  # 16-bit
                    audio_data = np.frombuffer(frames, dtype=np.int16)
                else:
                    raise AudioDeviceError("Unsupported sample width")

                # Convert to float32 for sounddevice
                audio_data = audio_data.astype(np.float32) / 32768.0

                # Handle mono/stereo
                if wf.getnchannels() == 1:
                    # Mono - duplicate to stereo for PCM2903B
                    audio_data = np.column_stack((audio_data, audio_data))
                elif wf.getnchannels() == 2:
                    audio_data = audio_data.reshape((-1, 2))
                else:
                    raise AudioDeviceError("Unsupported channel count")

            # Play audio to the specified device
            logger.info(
                f"Playing audio to device {self._audio_device_id}: {wav_path.name}"
            )
            sd.play(
                audio_data,
                samplerate=sample_rate,
                device=self._audio_device_id,
                blocking=True,
            )

            logger.info("Audio playback completed")
            return True

        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
            raise AudioDeviceError(f"Playback failed: {e}")

    def broadcast(
        self, text: str, confirm: bool = False, voice: str = "default"
    ) -> bool:
        """
        Complete TTS-to-radio broadcast pipeline.

        SAFETY: This function can result in RF transmission. The confirm flag
        is mandatory to acknowledge that a licensed operator is present.

        Args:
            text: Message text to broadcast
            confirm: MANDATORY safety confirmation (must be True)
            voice: TTS voice selection

        Returns:
            True if broadcast succeeded

        Raises:
            ValueError: If confirm is not True
            BroadcastError: If any step fails
        """
        if not confirm:
            raise ValueError(
                "confirm=True is required for broadcast operations. "
                "This acknowledges that a licensed amateur radio operator "
                "is physically present and controlling the station."
            )

        # Safety warnings
        logger.warning("🚨 RADIO TRANSMISSION COMMENCING")
        logger.warning("🚨 Licensed operator KO4TUV must be physically present")
        logger.warning(
            "🚨 Operator is responsible for proper identification and compliance"
        )

        try:
            # Step 1: Convert text to audio
            logger.info("Converting text to speech...")
            wav_path = self.text_to_audio(text, voice)

            # Step 2: Route audio to radio
            logger.info("Routing audio to radio...")
            self.play_to_radio(wav_path)

            # Cleanup
            os.unlink(wav_path)

            logger.info("✅ Broadcast completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Broadcast failed: {e}")
            raise BroadcastError(f"Broadcast failed: {e}")

    def record_from_radio(
        self, duration_seconds: float, output_path: Optional[str] = None
    ) -> str:
        """
        Record audio FROM the radio via PCM2903B.

        Captures receive audio for future speech-to-text processing.

        Args:
            duration_seconds: Recording duration
            output_path: Output WAV file path (temp file if None)

        Returns:
            Path to recorded WAV file

        Raises:
            AudioDeviceError: If recording fails
        """
        if not AUDIO_ENABLED:
            raise AudioDeviceError("Audio libraries not available")

        if self._audio_device_id is None:
            raise AudioDeviceError("No audio device configured")

        if duration_seconds <= 0 or duration_seconds > 300:  # 5 minute max
            raise ValueError("Duration must be between 0 and 300 seconds")

        # Create output file
        if output_path is None:
            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_path = temp_wav.name
            temp_wav.close()
        else:
            output_path = str(Path(output_path))

        try:
            logger.info(f"Recording from radio for {duration_seconds} seconds...")

            # Record audio
            recording = sd.rec(
                int(duration_seconds * self.sample_rate),
                samplerate=self.sample_rate,
                channels=2,  # Stereo from PCM2903B
                device=self._audio_device_id,
                dtype=np.float32,
            )
            sd.wait()  # Wait for recording to complete

            # Convert to 16-bit integers for WAV
            recording_int16 = (recording * 32767).astype(np.int16)

            # Write WAV file
            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(2)  # Stereo
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(recording_int16.tobytes())

            logger.info(
                f"Recording saved: {output_path} ({os.path.getsize(output_path)} bytes)"
            )
            return output_path

        except Exception as e:
            logger.error(f"Recording failed: {e}")
            if os.path.exists(output_path):
                os.unlink(output_path)
            raise AudioDeviceError(f"Recording failed: {e}")

    def get_audio_devices(self) -> dict:
        """
        Get list of available audio devices.

        Returns:
            Dictionary with device information
        """
        if not AUDIO_ENABLED:
            return {"error": "Audio libraries not available"}

        try:
            devices = sd.query_devices()
            result = {"current_device": self._audio_device_id, "devices": []}

            for idx, device in enumerate(devices):
                result["devices"].append(
                    {
                        "id": idx,
                        "name": device["name"],
                        "max_input_channels": device["max_input_channels"],
                        "max_output_channels": device["max_output_channels"],
                        "default_samplerate": device["default_samplerate"],
                    }
                )

            return result

        except Exception as e:
            return {"error": f"Failed to query devices: {e}"}


def cleanup_temp_files():
    """Clean up temporary audio files older than 1 hour."""
    temp_dir = Path(tempfile.gettempdir())
    cutoff_time = time.time() - 3600  # 1 hour ago

    for wav_file in temp_dir.glob("tmp*.wav"):
        try:
            if wav_file.stat().st_mtime < cutoff_time:
                wav_file.unlink()
                logger.debug(f"Cleaned up old temp file: {wav_file}")
        except Exception as e:
            logger.debug(f"Could not clean up {wav_file}: {e}")
