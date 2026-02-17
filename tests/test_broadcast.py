#!/usr/bin/env python3
"""
Tests for FT-991A Broadcast Module
==================================
Unit tests for TTS-to-radio broadcast functionality.

Tests cover:
- TTS generation (mocked when pyttsx3/espeak unavailable)
- Audio device detection 
- Safety confirmation requirements
- Error handling
- File cleanup
"""

import pytest
import tempfile
import os
import wave
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Test imports - handle missing audio dependencies gracefully
try:
    from src.ft991a.broadcast import (
        Broadcaster, 
        BroadcastError, 
        AudioDeviceError, 
        TTSError,
        cleanup_temp_files
    )
    from src.ft991a.cat import FT991A
except ImportError as e:
    pytest.skip(f"Could not import broadcast module: {e}", allow_module_level=True)


class TestBroadcaster:
    """Test the Broadcaster class functionality."""
    
    @pytest.fixture
    def mock_radio(self):
        """Mock FT991A radio instance."""
        radio = Mock(spec=FT991A)
        radio.connect.return_value = True
        radio.disconnect.return_value = None
        return radio
    
    @pytest.fixture
    def temp_wav_file(self):
        """Create a temporary WAV file for testing."""
        # Create a simple mono WAV file
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Write minimal WAV content
        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(48000)
            # Write 1 second of silence
            silence = b'\x00\x00' * 48000
            wf.writeframes(silence)
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_broadcaster_initialization(self, mock_radio):
        """Test Broadcaster initialization."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'USB Audio CODEC', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            assert broadcaster.radio == mock_radio
            assert broadcaster.sample_rate == 48000
            assert broadcaster._audio_device_id == 0
    
    def test_audio_device_detection_pcm2903b(self, mock_radio):
        """Test PCM2903B device detection."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'PCM2903B Audio CODEC', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000},
                {'name': 'Built-in Audio', 'max_output_channels': 2, 'max_input_channels': 1, 'default_samplerate': 44100}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            assert broadcaster._audio_device_id == 0  # Should pick PCM2903B
    
    def test_audio_device_fallback(self, mock_radio):
        """Test fallback to default device when PCM2903B not found."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Built-in Audio', 'max_output_channels': 2, 'max_input_channels': 1, 'default_samplerate': 44100}
            ]
            mock_sd.query_devices.side_effect = lambda kind=None: {'name': 'Default Output', 'index': 0} if kind == 'output' else mock_sd.query_devices.return_value
            
            broadcaster = Broadcaster(mock_radio)
            assert broadcaster._audio_device_id == 0  # Should use default
    
    @patch('src.ft991a.broadcast.pyttsx3')
    def test_tts_pyttsx3_initialization(self, mock_pyttsx3, mock_radio):
        """Test TTS initialization with pyttsx3."""
        mock_engine = Mock()
        mock_pyttsx3.init.return_value = mock_engine
        
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            
            mock_pyttsx3.init.assert_called_once()
            mock_engine.setProperty.assert_any_call('rate', 150)
            mock_engine.setProperty.assert_any_call('volume', 0.9)
    
    @patch('src.ft991a.broadcast.pyttsx3', None)  # Simulate pyttsx3 not available
    def test_tts_espeak_fallback(self, mock_radio):
        """Test TTS fallback to espeak."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            assert broadcaster._tts_engine is None  # Should fall back to espeak
    
    @patch('src.ft991a.broadcast.pyttsx3')
    def test_text_to_audio_pyttsx3(self, mock_pyttsx3, mock_radio):
        """Test text-to-audio conversion using pyttsx3."""
        mock_engine = Mock()
        mock_pyttsx3.init.return_value = mock_engine
        
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            
            # Mock file creation
            with patch('tempfile.NamedTemporaryFile') as mock_temp, \
                 patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=1000):
                
                mock_temp.return_value.__enter__.return_value.name = '/tmp/test.wav'
                
                result = broadcaster.text_to_audio("Hello world")
                
                mock_engine.save_to_file.assert_called_once_with("Hello world", '/tmp/test.wav')
                mock_engine.runAndWait.assert_called_once()
                assert result == '/tmp/test.wav'
    
    @patch('src.ft991a.broadcast.pyttsx3', None)
    @patch('src.ft991a.broadcast.subprocess.run')
    def test_text_to_audio_espeak(self, mock_subprocess, mock_radio):
        """Test text-to-audio conversion using espeak."""
        mock_subprocess.return_value.returncode = 0
        
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            
            # Mock file creation
            with patch('tempfile.NamedTemporaryFile') as mock_temp, \
                 patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=1000):
                
                mock_temp.return_value.__enter__.return_value.name = '/tmp/test.wav'
                
                result = broadcaster.text_to_audio("Hello world")
                
                mock_subprocess.assert_called_once()
                args = mock_subprocess.call_args[0][0]
                assert 'espeak' in args
                assert 'Hello world' in args
                assert '/tmp/test.wav' in args
    
    def test_text_to_audio_empty_text(self, mock_radio):
        """Test text-to-audio with empty text raises error."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            
            with pytest.raises(TTSError, match="Empty text provided"):
                broadcaster.text_to_audio("")
    
    def test_play_to_radio_file_not_found(self, mock_radio):
        """Test play_to_radio with non-existent file."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            
            with pytest.raises(AudioDeviceError, match="WAV file not found"):
                broadcaster.play_to_radio("/nonexistent/file.wav")
    
    @patch('src.ft991a.broadcast.sd')
    @patch('src.ft991a.broadcast.np')
    def test_play_to_radio_success(self, mock_np, mock_sd, mock_radio, temp_wav_file):
        """Test successful audio playback to radio."""
        mock_sd.query_devices.return_value = [
            {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
        ]
        
        # Mock numpy operations
        mock_audio_data = Mock()
        mock_np.frombuffer.return_value = mock_audio_data
        mock_audio_data.astype.return_value = mock_audio_data
        mock_np.column_stack.return_value = mock_audio_data
        
        broadcaster = Broadcaster(mock_radio)
        
        result = broadcaster.play_to_radio(temp_wav_file)
        
        assert result is True
        mock_sd.play.assert_called_once()
    
    def test_broadcast_without_confirm(self, mock_radio):
        """Test broadcast raises error without confirmation."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            broadcaster = Broadcaster(mock_radio)
            
            with pytest.raises(ValueError, match="confirm=True is required"):
                broadcaster.broadcast("Hello world", confirm=False)
    
    @patch('src.ft991a.broadcast.sd')
    def test_broadcast_success(self, mock_sd, mock_radio):
        """Test successful broadcast operation."""
        mock_sd.query_devices.return_value = [
            {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
        ]
        
        broadcaster = Broadcaster(mock_radio)
        
        with patch.object(broadcaster, 'text_to_audio', return_value='/tmp/test.wav') as mock_tts, \
             patch.object(broadcaster, 'play_to_radio', return_value=True) as mock_play, \
             patch('os.unlink') as mock_unlink:
            
            result = broadcaster.broadcast("Hello world", confirm=True)
            
            assert result is True
            mock_tts.assert_called_once_with("Hello world", "default")
            mock_play.assert_called_once_with('/tmp/test.wav')
            mock_unlink.assert_called_once_with('/tmp/test.wav')
    
    @patch('src.ft991a.broadcast.sd')
    def test_record_from_radio_invalid_duration(self, mock_sd, mock_radio):
        """Test record with invalid duration."""
        mock_sd.query_devices.return_value = [
            {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
        ]
        
        broadcaster = Broadcaster(mock_radio)
        
        with pytest.raises(ValueError, match="Duration must be between 0 and 300"):
            broadcaster.record_from_radio(-1)
        
        with pytest.raises(ValueError, match="Duration must be between 0 and 300"):
            broadcaster.record_from_radio(500)
    
    @patch('src.ft991a.broadcast.sd')
    @patch('src.ft991a.broadcast.np')
    def test_record_from_radio_success(self, mock_np, mock_sd, mock_radio):
        """Test successful recording from radio."""
        mock_sd.query_devices.return_value = [
            {'name': 'Test Device', 'max_output_channels': 2, 'max_input_channels': 2, 'default_samplerate': 48000}
        ]
        
        # Mock recording data
        mock_recording = Mock()
        mock_sd.rec.return_value = mock_recording
        mock_recording_int16 = Mock()
        mock_recording_int16.tobytes.return_value = b'\x00' * 1000
        mock_recording.__mul__.return_value.astype.return_value = mock_recording_int16
        
        broadcaster = Broadcaster(mock_radio)
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp, \
             patch('wave.open') as mock_wave, \
             patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1000):
            
            mock_temp.return_value.__enter__.return_value.name = '/tmp/record.wav'
            mock_wf = Mock()
            mock_wave.return_value.__enter__.return_value = mock_wf
            
            result = broadcaster.record_from_radio(5.0)
            
            assert result == '/tmp/record.wav'
            mock_sd.rec.assert_called_once()
            mock_sd.wait.assert_called_once()
    
    def test_get_audio_devices(self, mock_radio):
        """Test audio device enumeration."""
        with patch('src.ft991a.broadcast.sd') as mock_sd:
            mock_sd.query_devices.return_value = [
                {
                    'name': 'PCM2903B Audio',
                    'max_input_channels': 2,
                    'max_output_channels': 2,
                    'default_samplerate': 48000
                },
                {
                    'name': 'Built-in Audio',
                    'max_input_channels': 1,
                    'max_output_channels': 2,
                    'default_samplerate': 44100
                }
            ]
            
            broadcaster = Broadcaster(mock_radio)
            devices = broadcaster.get_audio_devices()
            
            assert 'current_device' in devices
            assert 'devices' in devices
            assert len(devices['devices']) == 2
            assert devices['devices'][0]['name'] == 'PCM2903B Audio'


class TestCleanupFunctions:
    """Test utility functions."""
    
    def test_cleanup_temp_files(self):
        """Test cleanup of old temporary files."""
        with patch('pathlib.Path.glob') as mock_glob, \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('pathlib.Path.unlink') as mock_unlink, \
             patch('time.time', return_value=10000):  # Current time
            
            # Create mock old file
            old_file = Mock()
            mock_stat_result = Mock()
            mock_stat_result.st_mtime = 5000  # Old file (1+ hour ago)
            old_file.stat.return_value = mock_stat_result
            
            # Create mock new file  
            new_file = Mock()
            mock_stat_result2 = Mock()
            mock_stat_result2.st_mtime = 9500  # Recent file
            new_file.stat.return_value = mock_stat_result2
            
            mock_glob.return_value = [old_file, new_file]
            
            cleanup_temp_files()
            
            old_file.unlink.assert_called_once()
            new_file.unlink.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])