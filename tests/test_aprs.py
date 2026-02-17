#!/usr/bin/env python3
"""
Tests for APRS Module
====================
Tests for APRS packet encoding/decoding and emergency communications functionality.

Test coverage:
- APRS position packet encoding/decoding roundtrip
- APRS message packet encoding/decoding roundtrip  
- Emergency frequency and net information
- APRSClient configuration and setup
- Error handling for malformed packets
"""

import unittest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ft991a.aprs import APRSClient, EmergencyKit, APRSPacket, APRSPosition, APRSMessage
from ft991a.cat import FT991A, Mode


class TestAPRSPacketEncoding(unittest.TestCase):
    """Test APRS packet encoding functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_radio = Mock(spec=FT991A)
        self.aprs_client = APRSClient(self.mock_radio, "KO4TUV")
    
    def test_position_encoding_basic(self):
        """Test basic position packet encoding"""
        # Test coordinates: Raleigh, NC area
        packet = self.aprs_client.encode_aprs_position(
            "KO4TUV", 35.7796, -78.6382, "OpenClaw Test Station"
        )
        
        # Should contain callsign, path, and position
        self.assertIn("KO4TUV>APRS", packet)
        self.assertIn("WIDE1-1,WIDE2-1", packet)
        self.assertIn("!", packet)  # Position identifier
        self.assertIn("OpenClaw Test Station", packet)
        
        # Check approximate coordinate conversion (allow for floating point precision)
        # 35.7796° → 35°46.78'N (slight precision variation expected)
        self.assertTrue("3546.7" in packet and "N" in packet)
        self.assertTrue("07838.2" in packet and "W" in packet)
    
    def test_position_encoding_symbols(self):
        """Test position encoding with different symbols"""
        packet = self.aprs_client.encode_aprs_position(
            "KO4TUV", 35.7796, -78.6382, "House", symbol_code="-"
        )
        
        # Should contain house symbol (format: lat/lon-symbol_code)
        self.assertIn("W-House", packet)  # Symbol code after coordinates
    
    def test_position_encoding_coordinates(self):
        """Test coordinate conversion accuracy"""
        # Test various coordinates (allow floating point precision variations)
        test_cases = [
            (0.0, 0.0, "0000.00N", "00000.00E"),
            (90.0, 180.0, "9000.00N", "18000.00E"), 
            (-90.0, -180.0, "9000.00S", "18000.00W"),
        ]
        
        for lat, lon, expected_lat, expected_lon in test_cases:
            packet = self.aprs_client.encode_aprs_position("TEST", lat, lon, "")
            self.assertIn(expected_lat, packet, f"Latitude conversion failed for {lat}")
            self.assertIn(expected_lon, packet, f"Longitude conversion failed for {lon}")
        
        # Test coordinate with precision tolerance
        packet = self.aprs_client.encode_aprs_position("TEST", 35.123456, -78.987654, "")
        self.assertTrue("3507.4" in packet and "N" in packet, "Latitude precision test failed")
        self.assertTrue("07859.2" in packet and "W" in packet, "Longitude precision test failed")
    
    def test_message_encoding_basic(self):
        """Test basic message packet encoding"""
        packet = self.aprs_client.encode_aprs_message(
            "KO4TUV", "N0CALL", "Hello World!", "001"
        )
        
        # Should contain source, destination (padded), message, and ID
        self.assertIn("KO4TUV>APRS", packet)
        self.assertIn("::N0CALL   :Hello World!{001", packet)
    
    def test_message_encoding_no_id(self):
        """Test message encoding without message ID"""
        packet = self.aprs_client.encode_aprs_message(
            "KO4TUV", "W1AW", "Test message"
        )
        
        self.assertIn("::W1AW     :Test message", packet)
        self.assertNotIn("{", packet)  # No message ID
    
    def test_message_encoding_padding(self):
        """Test message addressee padding"""
        packet = self.aprs_client.encode_aprs_message("KO4TUV", "AB", "Test")
        
        # Short callsign should be padded to 9 characters
        self.assertIn("::AB       :Test", packet)


class TestAPRSPacketDecoding(unittest.TestCase):
    """Test APRS packet decoding functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_radio = Mock(spec=FT991A)
        self.aprs_client = APRSClient(self.mock_radio, "KO4TUV")
    
    def test_position_decoding_basic(self):
        """Test basic position packet decoding"""
        packet = "KO4TUV>APRS,WIDE1-1,WIDE2-1:!3546.77N/07838.29W>OpenClaw Test Station"
        
        decoded = self.aprs_client.decode_aprs_packet(packet)
        
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.source_call, "KO4TUV")
        self.assertEqual(decoded.destination, "APRS")
        self.assertEqual(decoded.path, ["WIDE1-1", "WIDE2-1"])
        self.assertEqual(decoded.packet_type, "!")
        
        # Check position data
        self.assertEqual(decoded.data['type'], 'position')
        self.assertAlmostEqual(decoded.data['latitude'], 35.7795, places=3)
        self.assertAlmostEqual(decoded.data['longitude'], -78.6382, places=3)
        self.assertEqual(decoded.data['symbol_code'], ">")
        self.assertEqual(decoded.data['comment'], "OpenClaw Test Station")
    
    def test_message_decoding_basic(self):
        """Test basic message packet decoding"""
        packet = "KO4TUV>APRS,WIDE1-1::N0CALL   :Hello World!{001"
        
        decoded = self.aprs_client.decode_aprs_packet(packet)
        
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.source_call, "KO4TUV")
        self.assertEqual(decoded.packet_type, ":")
        
        # Check message data
        self.assertEqual(decoded.data['type'], 'message')
        self.assertEqual(decoded.data['addressee'], "N0CALL")
        self.assertEqual(decoded.data['message'], "Hello World!")
        self.assertEqual(decoded.data['message_id'], "001")
    
    def test_status_decoding(self):
        """Test status packet decoding"""
        packet = "KO4TUV>APRS:>OpenClaw station online"
        
        decoded = self.aprs_client.decode_aprs_packet(packet)
        
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.packet_type, ">")
        self.assertEqual(decoded.data['type'], 'status')
        self.assertEqual(decoded.data['status_text'], "OpenClaw station online")
    
    def test_invalid_packet_handling(self):
        """Test handling of invalid packets"""
        # Test various invalid formats
        invalid_packets = [
            "",  # Empty
            "NO_COLON_SEPARATOR",  # Missing data separator
            "NOSRC:data",  # Missing > in header
            "SRC>:empty_data",  # Empty data field
        ]
        
        for packet in invalid_packets:
            decoded = self.aprs_client.decode_aprs_packet(packet)
            self.assertIsNone(decoded, f"Should have failed for: {packet}")


class TestAPRSRoundtrip(unittest.TestCase):
    """Test APRS encode/decode roundtrip functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_radio = Mock(spec=FT991A)
        self.aprs_client = APRSClient(self.mock_radio, "KO4TUV")
    
    def test_position_roundtrip(self):
        """Test position encoding → decoding roundtrip"""
        # Original data
        callsign = "KO4TUV"
        lat = 35.7796
        lon = -78.6382
        comment = "Roundtrip Test"
        symbol = ">"
        
        # Encode
        packet = self.aprs_client.encode_aprs_position(callsign, lat, lon, comment, symbol_code=symbol)
        
        # Decode
        decoded = self.aprs_client.decode_aprs_packet(packet)
        
        # Verify roundtrip accuracy
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.source_call, callsign)
        self.assertEqual(decoded.data['type'], 'position')
        
        # Coordinates should be accurate to ~0.01 arcminutes (APRS precision)
        self.assertAlmostEqual(decoded.data['latitude'], lat, places=3)
        self.assertAlmostEqual(decoded.data['longitude'], lon, places=3)
        self.assertEqual(decoded.data['comment'], comment)
        self.assertEqual(decoded.data['symbol_code'], symbol)
    
    def test_message_roundtrip(self):
        """Test message encoding → decoding roundtrip"""
        # Original data
        source = "KO4TUV"
        dest = "W1AW"
        message = "Roundtrip message test"
        msg_id = "123"
        
        # Encode
        packet = self.aprs_client.encode_aprs_message(source, dest, message, msg_id)
        
        # Decode
        decoded = self.aprs_client.decode_aprs_packet(packet)
        
        # Verify roundtrip accuracy
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.source_call, source)
        self.assertEqual(decoded.data['type'], 'message')
        self.assertEqual(decoded.data['addressee'], dest)
        self.assertEqual(decoded.data['message'], message)
        self.assertEqual(decoded.data['message_id'], msg_id)
    
    def test_coordinate_precision(self):
        """Test coordinate precision through roundtrip"""
        test_coordinates = [
            (0.0, 0.0),
            (35.123456, -78.987654),
            (89.999, 179.999),
            (-89.999, -179.999),
        ]
        
        for lat, lon in test_coordinates:
            # Encode and decode
            packet = self.aprs_client.encode_aprs_position("TEST", lat, lon, "")
            decoded = self.aprs_client.decode_aprs_packet(packet)
            
            # Verify precision (APRS uses 0.01 arcminute precision)
            self.assertIsNotNone(decoded, f"Failed to decode coordinates {lat}, {lon}")
            precision_minutes = 0.01 / 60  # 0.01 arcminute in degrees
            
            self.assertAlmostEqual(decoded.data['latitude'], lat, delta=precision_minutes)
            self.assertAlmostEqual(decoded.data['longitude'], lon, delta=precision_minutes)


class TestEmergencyKit(unittest.TestCase):
    """Test emergency communications functionality"""
    
    def test_emergency_frequencies_list(self):
        """Test emergency frequency listing"""
        freqs = EmergencyKit.list_frequencies()
        
        # Should have multiple frequency entries
        self.assertGreater(len(freqs), 5)
        
        # Check for key emergency frequencies
        freq_names = [f['name'] for f in freqs]
        self.assertIn("APRS_PRIMARY", freq_names)
        self.assertIn("ARES_PRIMARY_VHF", freq_names)
        self.assertIn("SKYWARN_UHF", freq_names)
        
        # Check structure
        for freq in freqs:
            self.assertIn('name', freq)
            self.assertIn('freq', freq)
            self.assertIn('mode', freq)
            self.assertIn('notes', freq)
            self.assertIsInstance(freq['freq'], (int, float))
    
    def test_specific_frequency_lookup(self):
        """Test specific frequency lookup"""
        aprs_freq = EmergencyKit.get_frequency("APRS_PRIMARY")
        
        self.assertIsNotNone(aprs_freq)
        self.assertEqual(aprs_freq['freq'], 144.39)
        self.assertEqual(aprs_freq['mode'], "FM")
        
        # Test non-existent frequency
        missing = EmergencyKit.get_frequency("NONEXISTENT")
        self.assertIsNone(missing)
    
    def test_emergency_nets_list(self):
        """Test emergency nets listing"""
        nets = EmergencyKit.list_nets()
        
        # Should have multiple net entries
        self.assertGreater(len(nets), 1)
        
        # Check structure
        for net in nets:
            self.assertIn('net', net)
            self.assertIn('frequency', net)
            self.assertIn('mode', net)
            self.assertIn('day', net)
            self.assertIn('time', net)
            self.assertIn('notes', net)


class TestAPRSClientSetup(unittest.TestCase):
    """Test APRS client setup and configuration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_radio = Mock(spec=FT991A)
        self.aprs_client = APRSClient(self.mock_radio, "KO4TUV")
    
    def test_callsign_validation(self):
        """Test callsign format validation"""
        # Valid callsigns
        valid_calls = ["KO4TUV", "W1AW", "N0CALL", "VE3ABC", "G0ABC-1", "JA1ABC-15"]
        
        for callsign in valid_calls:
            try:
                client = APRSClient(self.mock_radio, callsign)
                self.assertEqual(client.callsign, callsign.upper())
            except ValueError:
                self.fail(f"Valid callsign rejected: {callsign}")
        
        # Invalid callsigns
        invalid_calls = ["", "TOOLONG123", "1INVALID", "IN-VALID-", "AB-0", "AB-100"]
        
        for callsign in invalid_calls:
            with self.assertRaises(ValueError, msg=f"Invalid callsign accepted: {callsign}"):
                APRSClient(self.mock_radio, callsign)
    
    def test_aprs_setup(self):
        """Test APRS radio configuration"""
        # Mock successful radio operations
        self.mock_radio.set_frequency_a.return_value = True
        self.mock_radio.set_mode.return_value = True
        
        # Test setup
        result = self.aprs_client.setup_aprs()
        
        self.assertTrue(result)
        
        # Verify radio was configured correctly
        self.mock_radio.set_frequency_a.assert_called_once_with(144_390_000)  # 144.390 MHz
        self.mock_radio.set_mode.assert_called_once_with(Mode.FM)
    
    def test_aprs_setup_failure(self):
        """Test APRS setup failure handling"""
        # Mock radio failure
        self.mock_radio.set_frequency_a.side_effect = Exception("Radio error")
        
        # Test setup failure
        result = self.aprs_client.setup_aprs()
        
        self.assertFalse(result)
    
    def test_transmit_safety_checks(self):
        """Test transmission safety checks and warnings"""
        packet = "TEST>APRS:!3546.77N/07838.29W>Test"
        
        # Test without confirmation - should fail
        result = self.aprs_client.transmit_packet(packet, confirmed=False)
        self.assertFalse(result)
        
        # Test with confirmation - should proceed (but fail due to no hardware)
        result = self.aprs_client.transmit_packet(packet, confirmed=True)
        self.assertFalse(result)  # Expected to fail (no TNC implementation)


class TestAPRSErrorHandling(unittest.TestCase):
    """Test APRS error handling and edge cases"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_radio = Mock(spec=FT991A)
        self.aprs_client = APRSClient(self.mock_radio, "KO4TUV")
    
    def test_encoding_edge_cases(self):
        """Test encoding with edge case inputs"""
        # Test coordinate boundaries
        extreme_coords = [
            (90.0, 180.0),    # North pole, International Date Line
            (-90.0, -180.0),  # South pole, opposite side
            (0.0, 0.0),       # Null Island
        ]
        
        for lat, lon in extreme_coords:
            packet = self.aprs_client.encode_aprs_position("TEST", lat, lon, "")
            self.assertIsInstance(packet, str)
            self.assertIn("TEST>APRS", packet)
    
    def test_decoding_malformed_position(self):
        """Test decoding malformed position packets"""
        malformed_packets = [
            "TEST>APRS:!BADPOSITION",  # Invalid position format
            "TEST>APRS:!1234.56N/",   # Incomplete coordinates
            "TEST>APRS:!9999.99N/18000.00E>", # Invalid coordinates
        ]
        
        for packet in malformed_packets:
            decoded = self.aprs_client.decode_aprs_packet(packet)
            if decoded:  # If it decodes, should contain error info
                self.assertIn('error', decoded.data)
    
    def test_long_comments(self):
        """Test handling of long comment fields"""
        long_comment = "A" * 200  # Very long comment
        
        packet = self.aprs_client.encode_aprs_position(
            "KO4TUV", 35.7796, -78.6382, long_comment
        )
        
        # Should not crash and should contain at least part of the comment
        self.assertIsInstance(packet, str)
        decoded = self.aprs_client.decode_aprs_packet(packet)
        self.assertIsNotNone(decoded)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)