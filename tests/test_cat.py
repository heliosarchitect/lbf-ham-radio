#!/usr/bin/env python3
"""
Unit tests for FT-991A CAT control library
==========================================
Tests the CAT protocol implementation with mocked serial interface.
No physical radio hardware required - uses mock objects to simulate responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ft991a.cat import FT991A, Mode, Band, RadioStatus


class TestFT991A:
    """Test cases for FT-991A CAT control"""
    
    @pytest.fixture
    def mock_serial(self):
        """Create a mock serial connection"""
        with patch('ft991a.cat.serial.Serial') as mock_serial_class:
            mock_connection = Mock()
            mock_serial_class.return_value = mock_connection
            
            # Setup default mock behaviors
            mock_connection.is_open = True
            mock_connection.write.return_value = None
            mock_connection.read_until.return_value = b'OK;\n'
            
            yield mock_connection
    
    @pytest.fixture 
    def radio(self, mock_serial):
        """Create FT991A instance with mocked serial"""
        radio = FT991A(port="/dev/mock", baud=38400)
        radio.serial = mock_serial
        radio.is_connected = True
        return radio
    
    def test_initialization(self):
        """Test radio initialization"""
        radio = FT991A(port="/dev/ttyUSB0", baud=38400)
        assert radio.port == "/dev/ttyUSB0"
        assert radio.baud == 38400
        assert not radio.is_connected
    
    def test_connect_success(self, mock_serial):
        """Test successful radio connection"""
        with patch('ft991a.cat.serial.Serial') as mock_serial_class:
            mock_serial_class.return_value = mock_serial
            mock_serial.is_open = True
            mock_serial.read_until.return_value = b'FT991A;\n'  # ID response
            
            radio = FT991A(port="/dev/mock", baud=38400)
            result = radio.connect()
            
            assert result is True
            assert radio.is_connected is True
            mock_serial_class.assert_called_once_with("/dev/mock", 38400, timeout=1)
    
    def test_connect_failure(self):
        """Test connection failure handling"""
        with patch('ft991a.cat.serial.Serial') as mock_serial_class:
            mock_serial_class.side_effect = Exception("Port not found")
            
            radio = FT991A(port="/dev/nonexistent", baud=38400)
            result = radio.connect()
            
            assert result is False
            assert radio.is_connected is False
    
    def test_send_command(self, radio, mock_serial):
        """Test basic command sending"""
        mock_serial.read_until.return_value = b'14074000;\n'
        
        response = radio._send_command("FA")
        
        assert response == "14074000"
        mock_serial.write.assert_called_with(b'FA;\n')
        mock_serial.read_until.assert_called_with(b';\n')
    
    def test_get_frequency(self, radio, mock_serial):
        """Test frequency retrieval"""
        mock_serial.read_until.return_value = b'14074000;\n'
        
        freq = radio.get_frequency()
        
        assert freq == 14074000
        mock_serial.write.assert_called_with(b'FA;\n')
    
    def test_set_frequency(self, radio, mock_serial):
        """Test frequency setting"""
        mock_serial.read_until.return_value = b';\n'
        
        result = radio.set_frequency(14074000)
        
        assert result is True
        mock_serial.write.assert_called_with(b'FA014074000;\n')
    
    def test_set_frequency_invalid(self, radio):
        """Test invalid frequency rejection"""
        # Too low
        result = radio.set_frequency(10000)  # 10kHz
        assert result is False
        
        # Too high  
        result = radio.set_frequency(100000000)  # 100MHz
        assert result is False
    
    def test_get_mode(self, radio, mock_serial):
        """Test mode retrieval"""
        mock_serial.read_until.return_value = b'2;\n'  # USB
        
        mode = radio.get_mode()
        
        assert mode == Mode.USB
        mock_serial.write.assert_called_with(b'MD0;\n')
    
    def test_set_mode(self, radio, mock_serial):
        """Test mode setting"""
        mock_serial.read_until.return_value = b';\n'
        
        result = radio.set_mode(Mode.USB)
        
        assert result is True
        mock_serial.write.assert_called_with(b'MD02;\n')
    
    def test_get_tx_power(self, radio, mock_serial):
        """Test TX power retrieval"""
        mock_serial.read_until.return_value = b'050;\n'  # 50W
        
        power = radio.get_tx_power()
        
        assert power == 50
        mock_serial.write.assert_called_with(b'PC;\n')
    
    def test_set_tx_power(self, radio, mock_serial):
        """Test TX power setting"""
        mock_serial.read_until.return_value = b';\n'
        
        result = radio.set_tx_power(75)
        
        assert result is True
        mock_serial.write.assert_called_with(b'PC075;\n')
    
    def test_set_tx_power_invalid(self, radio):
        """Test invalid power rejection"""
        # Too low
        result = radio.set_tx_power(1)
        assert result is False
        
        # Too high
        result = radio.set_tx_power(150)
        assert result is False
    
    def test_get_smeter(self, radio, mock_serial):
        """Test S-meter reading"""
        mock_serial.read_until.return_value = b'120;\n'  # S9+10dB
        
        smeter = radio.get_smeter()
        
        assert "S9+10dB" in smeter
        mock_serial.write.assert_called_with(b'SM0;\n')
    
    def test_ptt_on(self, radio, mock_serial):
        """Test PTT keying"""
        mock_serial.read_until.return_value = b';\n'
        
        result = radio.ptt_on()
        
        assert result is True
        mock_serial.write.assert_called_with(b'TX1;\n')
    
    def test_ptt_off(self, radio, mock_serial):
        """Test PTT unkeying"""
        mock_serial.read_until.return_value = b';\n'
        
        result = radio.ptt_off()
        
        assert result is True
        mock_serial.write.assert_called_with(b'TX0;\n')
    
    def test_get_status(self, radio, mock_serial):
        """Test complete status retrieval"""
        # Mock multiple command responses
        responses = [
            b'14074000;\n',  # FA (frequency)
            b'2;\n',         # MD0 (mode)  
            b'120;\n',       # SM0 (smeter)
            b'075;\n',       # PC (power)
            b'0;\n'          # TX (tx state)
        ]
        mock_serial.read_until.side_effect = responses
        
        status = radio.get_status()
        
        assert status is not None
        assert status.frequency == 14074000
        assert status.mode == Mode.USB
        assert "S9+10dB" in status.smeter
        assert status.tx_power == 75
        assert status.tx_on is False
    
    def test_disconnect(self, radio, mock_serial):
        """Test radio disconnection"""
        radio.disconnect()
        
        assert radio.is_connected is False
        mock_serial.close.assert_called_once()
    
    def test_command_timeout(self, radio, mock_serial):
        """Test command timeout handling"""
        mock_serial.read_until.side_effect = Exception("Timeout")
        
        response = radio._send_command("FA")
        
        assert response is None
    
    def test_mode_enum_values(self):
        """Test Mode enum values match FT-991A specification"""
        assert Mode.LSB.value == "1"
        assert Mode.USB.value == "2" 
        assert Mode.CW.value == "3"
        assert Mode.FM.value == "4"
        assert Mode.AM.value == "5"
        assert Mode.DATA_USB.value == "C"  # For FT8/digital
    
    def test_band_enum_values(self):
        """Test Band enum frequencies"""
        assert Band.HF_20M.value == 14_000_000  # 20 meters
        assert Band.HF_40M.value == 7_000_000   # 40 meters
        assert Band.HF_80M.value == 3_500_000   # 80 meters


class TestRadioStatus:
    """Test RadioStatus dataclass"""
    
    def test_radio_status_creation(self):
        """Test RadioStatus object creation"""
        status = RadioStatus(
            frequency=14074000,
            mode=Mode.DATA_USB,
            smeter="S9+5dB",
            tx_power=50,
            tx_on=False
        )
        
        assert status.frequency == 14074000
        assert status.mode == Mode.DATA_USB
        assert status.smeter == "S9+5dB"
        assert status.tx_power == 50
        assert status.tx_on is False


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])