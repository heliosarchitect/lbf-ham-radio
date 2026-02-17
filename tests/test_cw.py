#!/usr/bin/env python3
"""
Tests for CW (Morse Code) Module
================================
Comprehensive testing of CW encoding, decoding, and keying functionality.
"""

import pytest
import time
from unittest.mock import Mock, patch, call
import sys
import os

# Add the src directory to the path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ft991a.cw import (
    text_to_morse, morse_to_text, CWTiming, CWKeyer, CWDecoder,
    MORSE_TABLE, REVERSE_MORSE_TABLE, 
    encode_text_to_morse, decode_morse_to_text
)


class TestMorseEncoding:
    """Test Morse code encoding functionality"""
    
    def test_basic_text_to_morse(self):
        """Test basic text to Morse conversion"""
        assert text_to_morse("A") == ".-"
        assert text_to_morse("B") == "-..."
        assert text_to_morse("SOS") == "... --- ..."
        
    def test_numbers_to_morse(self):
        """Test number encoding"""
        assert text_to_morse("0") == "-----"
        assert text_to_morse("5") == "....."
        assert text_to_morse("123") == ".---- ..--- ...--"
        
    def test_punctuation_to_morse(self):
        """Test punctuation encoding"""
        assert text_to_morse(".") == ".-.-.-"
        assert text_to_morse(",") == "--..--"
        assert text_to_morse("?") == "..--.."
        
    def test_prosigns_to_morse(self):
        """Test prosign encoding"""
        assert text_to_morse("<SK>") == "...-.-"
        assert text_to_morse("<KA>") == "-.-.-"
        assert text_to_morse("<SN>") == "...-."
        
    def test_word_separation(self):
        """Test proper word separation in Morse"""
        result = text_to_morse("HI THERE")
        assert " " in result  # Should contain spaces for word separation
        # Should have proper letter and word spacing
        expected = ".... ..  - .... . .-. ."
        assert result == expected
        
    def test_case_insensitive(self):
        """Test that encoding is case-insensitive"""
        assert text_to_morse("hello") == text_to_morse("HELLO")
        assert text_to_morse("World") == text_to_morse("WORLD")
        
    def test_empty_and_whitespace(self):
        """Test handling of empty strings and whitespace"""
        assert text_to_morse("") == ""
        assert text_to_morse("   ") == ""
        assert text_to_morse("A   B") == ".-  -..."  # Multiple spaces = single word gap
        
    def test_unknown_characters(self):
        """Test handling of unknown characters"""
        # Should skip unknown characters but continue processing
        result = text_to_morse("A#B")  # # is not in Morse table
        assert ".-" in result  # A should be encoded
        assert "-..." in result  # B should be encoded
        

class TestMorseDecoding:
    """Test Morse code decoding functionality"""
    
    def test_basic_morse_to_text(self):
        """Test basic Morse to text conversion"""
        assert morse_to_text(".-") == "A"
        assert morse_to_text("-...") == "B" 
        assert morse_to_text("... --- ...") == "SOS"
        
    def test_numbers_from_morse(self):
        """Test number decoding"""
        assert morse_to_text("-----") == "0"
        assert morse_to_text(".....") == "5"
        assert morse_to_text(".---- ..--- ...--") == "123"
        
    def test_word_separation_decoding(self):
        """Test word separation in decoding"""
        morse = ".... ..  - .... . .-. ."  # "HI THERE"
        assert morse_to_text(morse) == "HI THERE"
        
    def test_extra_spaces_handling(self):
        """Test handling of extra spaces in Morse input"""
        # Should handle multiple spaces gracefully
        morse = "....  ..   - .... . .-. ."  # Extra spaces
        result = morse_to_text(morse)
        assert "HI" in result and "THERE" in result
        
    def test_unknown_morse_codes(self):
        """Test handling of unknown Morse codes"""
        # Should skip unknown codes but continue processing  
        result = morse_to_text(".- ........ -...")  # Middle code is invalid
        assert "A" in result  # First should decode
        assert "B" in result  # Last should decode


class TestRoundTrip:
    """Test encoding/decoding round-trip functionality"""
    
    @pytest.mark.parametrize("text", [
        "HELLO WORLD",
        "CQ CQ CQ DE W1ABC",
        "THE QUICK BROWN FOX 123",
        "SOS",
        "TEST MESSAGE",
        "ABC 123 XYZ"
    ])
    def test_roundtrip_conversion(self, text):
        """Test that text->Morse->text round-trip preserves content"""
        morse = text_to_morse(text)
        decoded = morse_to_text(morse)
        assert decoded == text
        
    def test_roundtrip_with_punctuation(self):
        """Test round-trip with punctuation"""
        text = "HELLO, WORLD!"
        morse = text_to_morse(text)
        decoded = morse_to_text(morse)
        assert decoded == text
        
    def test_roundtrip_with_prosigns(self):
        """Test round-trip with prosigns"""
        text = "TEST <SK> END <KA>"
        morse = text_to_morse(text)
        decoded = morse_to_text(morse)
        assert decoded == text


class TestCWTiming:
    """Test CW timing calculations"""
    
    def test_timing_calculation(self):
        """Test timing calculation from WPM"""
        timing_20 = CWTiming.from_wpm(20)
        assert timing_20.wpm == 20
        assert timing_20.dit_ms == 60.0  # 1200/20 = 60ms
        assert timing_20.dah_ms == 180.0  # 3 * dit
        assert timing_20.element_gap_ms == 60.0  # 1 * dit
        assert timing_20.letter_gap_ms == 180.0  # 3 * dit  
        assert timing_20.word_gap_ms == 420.0  # 7 * dit
        
    def test_different_wpm_values(self):
        """Test timing for different WPM values"""
        timing_5 = CWTiming.from_wpm(5)
        assert timing_5.dit_ms == 240.0  # 1200/5 = 240ms
        
        timing_40 = CWTiming.from_wpm(40) 
        assert timing_40.dit_ms == 30.0  # 1200/40 = 30ms
        
    def test_wpm_validation(self):
        """Test WPM range validation"""
        with pytest.raises(ValueError, match="WPM must be between 5 and 40"):
            CWTiming.from_wpm(4)
            
        with pytest.raises(ValueError, match="WPM must be between 5 and 40"):
            CWTiming.from_wpm(41)
            
        # Valid range should work
        CWTiming.from_wpm(5)   # Min
        CWTiming.from_wpm(40)  # Max
        CWTiming.from_wpm(20)  # Middle


class TestCWKeyer:
    """Test CW keyer functionality"""
    
    def setup_method(self):
        """Set up mock radio for each test"""
        self.mock_radio = Mock()
        self.mock_radio.ptt_on.return_value = True
        self.mock_radio.ptt_off.return_value = True
        
    def test_keyer_initialization(self):
        """Test keyer initialization"""
        keyer = CWKeyer(self.mock_radio, wpm=15)
        assert keyer.timing.wpm == 15
        assert keyer.radio == self.mock_radio
        assert not keyer._is_keying
        
    def test_wpm_setting(self):
        """Test WPM setting"""
        keyer = CWKeyer(self.mock_radio, wpm=20)
        keyer.set_wpm(25)
        assert keyer.timing.wpm == 25
        assert keyer.timing.dit_ms == 48.0  # 1200/25
        
    def test_key_operations(self):
        """Test basic keying operations"""
        keyer = CWKeyer(self.mock_radio, wpm=20)
        
        # Test key down
        keyer._key_down()
        assert keyer._is_keying
        self.mock_radio.ptt_on.assert_called_once()
        
        # Test key up
        keyer._key_up()
        assert not keyer._is_keying
        self.mock_radio.ptt_off.assert_called_once()
        
    @patch('time.sleep')
    def test_dit_timing(self, mock_sleep):
        """Test dit transmission timing"""
        keyer = CWKeyer(self.mock_radio, wpm=20)  # 60ms dit
        keyer._send_dit()
        
        # Should call sleep with dit duration in seconds
        mock_sleep.assert_called_once_with(0.060)  # 60ms = 0.060s
        self.mock_radio.ptt_on.assert_called_once()
        self.mock_radio.ptt_off.assert_called_once()
        
    @patch('time.sleep')
    def test_dah_timing(self, mock_sleep):
        """Test dah transmission timing"""
        keyer = CWKeyer(self.mock_radio, wpm=20)  # 180ms dah
        keyer._send_dah()
        
        # Should call sleep with dah duration in seconds
        mock_sleep.assert_called_once_with(0.180)  # 180ms = 0.180s
        self.mock_radio.ptt_on.assert_called_once()
        self.mock_radio.ptt_off.assert_called_once()
        
    @patch('time.sleep')
    def test_morse_code_transmission(self, mock_sleep):
        """Test transmission of simple Morse code"""
        keyer = CWKeyer(self.mock_radio, wpm=20)
        
        # Send "A" = ".-" (dit dah)
        keyer.send_morse_code(".-")
        
        # Should have multiple sleep calls for timing
        assert mock_sleep.call_count >= 2  # At least dit and dah timing
        # Should have keyed on/off for each element
        assert self.mock_radio.ptt_on.call_count >= 2
        assert self.mock_radio.ptt_off.call_count >= 2
        
    @patch('time.sleep') 
    def test_text_transmission(self, mock_sleep):
        """Test transmission of text (automatic Morse conversion)"""
        keyer = CWKeyer(self.mock_radio, wpm=20)
        
        # Send "SOS" - should convert to Morse and transmit
        keyer.send_text("SOS")
        
        # Should have keyed the radio multiple times
        assert self.mock_radio.ptt_on.call_count > 0
        assert self.mock_radio.ptt_off.call_count > 0
        
    def test_emergency_stop(self):
        """Test emergency stop functionality"""
        keyer = CWKeyer(self.mock_radio, wpm=20)
        
        # Simulate keying state
        keyer._is_keying = True
        
        # Emergency stop should unkey
        keyer.emergency_stop()
        assert not keyer._is_keying
        self.mock_radio.ptt_off.assert_called()
        
    @patch('time.sleep')
    def test_exception_handling(self, mock_sleep):
        """Test that exceptions during keying result in unkeyed state"""
        keyer = CWKeyer(self.mock_radio, wpm=20)
        
        # Make sleep raise an exception
        mock_sleep.side_effect = Exception("Test exception")
        
        with pytest.raises(Exception, match="Test exception"):
            keyer.send_morse_code(".-")
            
        # Should still unkey the radio
        self.mock_radio.ptt_off.assert_called()


class TestCWDecoder:
    """Test CW decoder (placeholder functionality)"""
    
    def test_decoder_initialization(self):
        """Test decoder initialization"""
        decoder = CWDecoder(sample_rate=8000, tone_freq=600)
        assert decoder.sample_rate == 8000
        assert decoder.tone_freq == 600
        assert not decoder._enabled
        
    def test_listening_control(self):
        """Test start/stop listening"""
        decoder = CWDecoder()
        
        decoder.start_listening()
        assert decoder._enabled
        
        decoder.stop_listening()
        assert not decoder._enabled
        
    def test_audio_buffer_processing(self):
        """Test audio buffer processing (placeholder)"""
        decoder = CWDecoder()
        
        # Should return None for placeholder implementation
        result = decoder.decode_audio_buffer([0.1, 0.2, 0.3, 0.4])
        assert result is None
        
    def test_decoder_stats(self):
        """Test decoder statistics"""
        decoder = CWDecoder(sample_rate=12000, tone_freq=800)
        stats = decoder.get_decoder_stats()
        
        assert stats['sample_rate'] == 12000
        assert stats['tone_freq'] == 800
        assert stats['enabled'] == False
        assert 'status' in stats


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_convenience_encoding(self):
        """Test convenience encoding function"""
        result = encode_text_to_morse("TEST")
        expected = text_to_morse("TEST")
        assert result == expected
        
    def test_convenience_decoding(self):
        """Test convenience decoding function"""
        morse = "- . ... -"
        result = decode_morse_to_text(morse)
        expected = morse_to_text(morse)
        assert result == expected


class TestMorseTable:
    """Test Morse code table completeness and consistency"""
    
    def test_table_completeness(self):
        """Test that Morse table contains expected characters"""
        # Check letters
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert letter in MORSE_TABLE
            
        # Check numbers
        for number in "0123456789":
            assert number in MORSE_TABLE
            
        # Check common punctuation
        common_punct = ".,?'!/()"
        for punct in common_punct:
            assert punct in MORSE_TABLE
            
    def test_reverse_table_consistency(self):
        """Test that reverse table is consistent with forward table"""
        for char, morse in MORSE_TABLE.items():
            if char != ' ':  # Skip space character
                assert morse in REVERSE_MORSE_TABLE
                assert REVERSE_MORSE_TABLE[morse] == char
                
    def test_no_duplicate_morse_codes(self):
        """Test that no two characters have the same Morse code"""
        morse_codes = []
        for char, morse in MORSE_TABLE.items():
            if char != ' ':  # Skip space character
                assert morse not in morse_codes, f"Duplicate Morse code: {morse}"
                morse_codes.append(morse)


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])