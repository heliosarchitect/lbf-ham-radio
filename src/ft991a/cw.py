#!/usr/bin/env python3
"""
CW (Morse Code) Module for FT-991A
==================================
Provides CW encoding/decoding and keying functionality for ham radio operations.

Features:
- Text to Morse code conversion 
- Morse code to text decoding
- CW keying via FT-991A TX commands
- Configurable WPM (5-40 WPM)
- Precise timing based on standard Morse timing
- Placeholder for future audio decoding

Timing Standards (per ARRL):
- Dit length = 1200 / WPM milliseconds
- Dah length = 3 × dit length  
- Inter-element gap = 1 × dit length
- Letter gap = 3 × dit length
- Word gap = 7 × dit length

WARNING: CW transmission requires a valid amateur radio license.
Always ensure a licensed operator is present and controlling the station.
"""

import time
import logging
import re
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# International Morse Code Table (ITU-R M.1677-1)
MORSE_TABLE = {
    # Letters
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',   'E': '.',
    'F': '..-.',  'G': '--.',   'H': '....',  'I': '..',    'J': '.---',
    'K': '-.-',   'L': '.-..',  'M': '--',    'N': '-.',    'O': '---',
    'P': '.--.',  'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',  'Y': '-.--',
    'Z': '--..',
    
    # Numbers  
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    
    # Common punctuation
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', 
    '!': '-.-.--', '/': '-..-.', '(': '-.--.', ')': '-.--.-',
    '&': '.-...', ':': '---...', ';': '-.-.-.', '=': '-...-',
    '+': '.-.-.', '-': '-....-', '_': '..--.-', '"': '.-..-.',
    '$': '...-..-', '@': '.--.-.',
    
    # Common prosigns (procedural signals) - only non-conflicting ones
    '<SK>': '...-.-', # End of contact (SK)  
    '<KA>': '-.-.-', # Attention (KA)
    '<SN>': '...-.',  # Understood (SN)
    
    # Special space character for word breaks
    ' ': ' ',
}

# Reverse lookup table for decoding
REVERSE_MORSE_TABLE = {code: char for char, code in MORSE_TABLE.items() if char != ' '}


@dataclass
class CWTiming:
    """CW timing parameters for a given WPM"""
    wpm: int
    dit_ms: float
    dah_ms: float
    element_gap_ms: float
    letter_gap_ms: float
    word_gap_ms: float
    
    @classmethod
    def from_wpm(cls, wpm: int) -> 'CWTiming':
        """Calculate timing parameters from WPM"""
        if not 5 <= wpm <= 40:
            raise ValueError("WPM must be between 5 and 40")
            
        # Standard formula: dit length in ms = 1200 / WPM
        dit_ms = 1200.0 / wpm
        
        return cls(
            wpm=wpm,
            dit_ms=dit_ms,
            dah_ms=dit_ms * 3,
            element_gap_ms=dit_ms,      # Gap between dots/dashes within letter
            letter_gap_ms=dit_ms * 3,   # Gap between letters  
            word_gap_ms=dit_ms * 7       # Gap between words
        )


def text_to_morse(text: str) -> str:
    """
    Convert text to Morse code.
    
    Args:
        text: Input text to encode
        
    Returns:
        String of dots, dashes, and spaces representing Morse code
        
    Example:
        >>> text_to_morse("HELLO WORLD")
        '.... . .-.. .-.. ---  .-- --- .-. .-.. -..'
    """
    text = text.upper().strip()
    if not text:
        return ""
    
    # Handle prosigns first (replace <XX> with special markers)
    import re
    prosign_pattern = r'<([A-Z]{2,3})>'
    for match in re.finditer(prosign_pattern, text):
        prosign = match.group(0)
        if prosign in MORSE_TABLE:
            # Replace with a unique placeholder that won't conflict
            text = text.replace(prosign, f'\x00{prosign}\x00')
    
    # Split into words first, then process each word
    words = re.split(r'\s+', text.strip())
    morse_words = []
    
    for word in words:
        morse_chars = []
        i = 0
        while i < len(word):
            if word[i] == '\x00':
                # Extract prosign 
                end = word.find('\x00', i + 1)
                prosign = word[i+1:end]
                if prosign in MORSE_TABLE:
                    morse_chars.append(MORSE_TABLE[prosign])
                i = end + 1
            elif word[i] in MORSE_TABLE:
                morse_chars.append(MORSE_TABLE[word[i]])
                i += 1
            else:
                logger.warning(f"Unknown character '{word[i]}' - skipping")
                i += 1
        
        if morse_chars:
            morse_words.append(' '.join(morse_chars))
    
    # Join words with double spaces (word gap)
    return '  '.join(morse_words)


def morse_to_text(morse: str) -> str:
    """
    Convert Morse code to text.
    
    Args:
        morse: Morse code string with dots, dashes, and spaces
        
    Returns:
        Decoded text string
        
    Example:
        >>> morse_to_text(".... . .-.. .-.. ---  .-- --- .-.. -..")
        'HELLO WORLD'
    """
    import re
    
    # Handle both normal spacing (2 spaces between words) and extra spacing gracefully
    # Strategy: Use 2+ consecutive spaces as word boundaries, but be smart about grouping
    
    # Split by 2+ spaces to get potential words
    words = re.split(r'  +', morse.strip())
    decoded_words = []
    
    for word in words:
        # Clean up the word and split by single spaces
        clean_word = re.sub(r'\s+', ' ', word.strip())
        if not clean_word:
            continue
            
        letters = clean_word.split(' ')
        decoded_letters = []
        
        for letter in letters:
            if letter in REVERSE_MORSE_TABLE:
                decoded_letters.append(REVERSE_MORSE_TABLE[letter])
            elif letter:  # Skip empty strings
                logger.warning(f"Unknown Morse code '{letter}' - skipping")
        
        if decoded_letters:
            decoded_words.append(''.join(decoded_letters))
    
    return ' '.join(decoded_words)


class CWKeyer:
    """
    CW keyer using FT-991A TX commands for precise timing.
    
    Handles automatic CW transmission with proper Morse code timing.
    Uses the radio's TX1/TX0 CAT commands for keying.
    """
    
    def __init__(self, radio_instance, wpm: int = 20):
        """
        Initialize CW keyer.
        
        Args:
            radio_instance: Connected FT991A instance
            wpm: Words per minute (5-40)
        """
        self.radio = radio_instance
        self.timing = CWTiming.from_wpm(wpm)
        self._is_keying = False
        
    def set_wpm(self, wpm: int):
        """Set transmission speed in WPM"""
        self.timing = CWTiming.from_wpm(wpm)
        logger.info(f"CW speed set to {wpm} WPM (dit={self.timing.dit_ms:.1f}ms)")
        
    def _key_down(self):
        """Key the transmitter (start tone)"""
        if not self._is_keying:
            self.radio.ptt_on()  # TX1 command
            self._is_keying = True
            
    def _key_up(self):
        """Unkey the transmitter (stop tone)"""
        if self._is_keying:
            self.radio.ptt_off()  # TX0 command  
            self._is_keying = False
            
    def _send_dit(self):
        """Send a dit (dot)"""
        self._key_down()
        time.sleep(self.timing.dit_ms / 1000.0)
        self._key_up()
        
    def _send_dah(self):
        """Send a dah (dash)"""
        self._key_down() 
        time.sleep(self.timing.dah_ms / 1000.0)
        self._key_up()
        
    def _element_gap(self):
        """Inter-element gap (between dots/dashes within a letter)"""
        time.sleep(self.timing.element_gap_ms / 1000.0)
        
    def _letter_gap(self):
        """Inter-letter gap"""
        time.sleep(self.timing.letter_gap_ms / 1000.0)
        
    def _word_gap(self):
        """Inter-word gap (additional, total gap = letter_gap + word_gap)"""
        time.sleep(self.timing.word_gap_ms / 1000.0 - self.timing.letter_gap_ms / 1000.0)
        
    def send_morse_code(self, morse: str):
        """
        Send Morse code string using radio keying.
        
        Args:
            morse: Morse code string (dots, dashes, spaces)
            
        Example:
            keyer.send_morse_code(".... .  .-- --- .-. .-.. -..")  # "HE WORLD"
        """
        logger.info(f"Keying CW at {self.timing.wpm} WPM: {morse}")
        
        try:
            # Split into words (double space separated)
            words = re.split(r'  +', morse.strip())
            
            for word_idx, word in enumerate(words):
                if word_idx > 0:
                    self._word_gap()  # Gap between words
                    
                # Split word into letters (single space separated) 
                letters = word.split(' ')
                
                for letter_idx, letter in enumerate(letters):
                    if letter_idx > 0:
                        self._letter_gap()  # Gap between letters
                        
                    # Send each element (dot/dash) in the letter
                    for element_idx, element in enumerate(letter):
                        if element_idx > 0:
                            self._element_gap()  # Gap between elements
                            
                        if element == '.':
                            self._send_dit()
                        elif element == '-':
                            self._send_dah()
                        else:
                            logger.warning(f"Unknown Morse element '{element}' - skipping")
                            
        except Exception as e:
            logger.error(f"Error during CW keying: {e}")
            # Ensure we unkey if something goes wrong
            self._key_up()
            raise
        finally:
            # Always ensure we end in receive mode
            self._key_up()
            
    def send_text(self, text: str):
        """
        Convert text to Morse and send via radio.
        
        Args:
            text: Text message to send in CW
        """
        morse = text_to_morse(text)
        if morse.strip():
            self.send_morse_code(morse)
        else:
            logger.warning("No valid Morse code generated from text")
            
    def emergency_stop(self):
        """Emergency stop - immediately unkey transmitter"""
        logger.warning("CW EMERGENCY STOP - unkeying transmitter")
        self._key_up()


class CWDecoder:
    """
    CW decoder for audio input analysis.
    
    TODO: This is a placeholder for future audio decoding functionality.
    Will implement Goertzel algorithm for tone detection when audio input is available.
    """
    
    def __init__(self, sample_rate: int = 8000, tone_freq: int = 600):
        """
        Initialize CW decoder.
        
        Args:
            sample_rate: Audio sample rate (Hz) 
            tone_freq: CW tone frequency to detect (Hz)
        """
        self.sample_rate = sample_rate
        self.tone_freq = tone_freq
        self._enabled = False
        
        logger.info("CWDecoder initialized (PLACEHOLDER - not yet implemented)")
        
    def start_listening(self):
        """Start listening for CW audio input"""
        logger.info("CW decoder listening started (PLACEHOLDER)")
        # TODO: Implement Goertzel algorithm for tone detection
        # TODO: Add audio input handling (sounddevice, pyaudio, etc.)
        # TODO: Implement dit/dah timing analysis
        # TODO: Add noise filtering and AGC
        self._enabled = True
        
    def stop_listening(self):
        """Stop listening for CW audio input"""
        logger.info("CW decoder listening stopped")
        self._enabled = False
        
    def decode_audio_buffer(self, audio_data: List[float]) -> Optional[str]:
        """
        Decode CW from audio buffer.
        
        Args:
            audio_data: Audio samples as floats
            
        Returns:
            Decoded Morse code string, or None if no valid CW detected
            
        TODO: Implement Goertzel algorithm for tone detection:
        1. Apply Goertzel algorithm to detect tone_freq
        2. Use threshold to determine key-down/key-up
        3. Analyze timing to distinguish dits from dahs
        4. Build Morse code string from timing analysis
        5. Return decoded Morse (can be fed to morse_to_text())
        """
        logger.debug(f"Processing {len(audio_data)} audio samples (PLACEHOLDER)")
        return None  # TODO: Implement actual decoding
        
    def get_decoder_stats(self) -> Dict:
        """Get decoder statistics and status"""
        return {
            'enabled': self._enabled,
            'sample_rate': self.sample_rate,
            'tone_freq': self.tone_freq,
            'status': 'placeholder_not_implemented'
        }


# Convenience functions for command-line usage

def encode_text_to_morse(text: str) -> str:
    """Convenience function: text to Morse"""
    return text_to_morse(text)

def decode_morse_to_text(morse: str) -> str:
    """Convenience function: Morse to text"""  
    return morse_to_text(morse)

def create_keyer(radio_instance, wpm: int = 20) -> CWKeyer:
    """Convenience function: create CW keyer"""
    return CWKeyer(radio_instance, wpm)

def create_decoder(sample_rate: int = 8000, tone_freq: int = 600) -> CWDecoder:
    """Convenience function: create CW decoder"""
    return CWDecoder(sample_rate, tone_freq)


if __name__ == "__main__":
    # Basic testing
    print("CW Module Test")
    print("=" * 40)
    
    # Test encoding
    test_text = "HELLO WORLD CQ"
    morse = text_to_morse(test_text)
    print(f"Text: {test_text}")
    print(f"Morse: {morse}")
    
    # Test decoding  
    decoded = morse_to_text(morse)
    print(f"Decoded: {decoded}")
    print(f"Roundtrip OK: {decoded == test_text}")
    
    # Test timing calculation
    timing_20wpm = CWTiming.from_wpm(20)
    print(f"\n20 WPM Timing:")
    print(f"  Dit: {timing_20wpm.dit_ms:.1f}ms")
    print(f"  Dah: {timing_20wpm.dah_ms:.1f}ms") 
    print(f"  Letter gap: {timing_20wpm.letter_gap_ms:.1f}ms")