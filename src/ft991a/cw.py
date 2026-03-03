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

import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# International Morse Code Table (ITU-R M.1677-1)
MORSE_TABLE = {
    # Letters
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    # Numbers
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    # Common punctuation
    ".": ".-.-.-",
    ",": "--..--",
    "?": "..--..",
    "'": ".----.",
    "!": "-.-.--",
    "/": "-..-.",
    "(": "-.--.",
    ")": "-.--.-",
    "&": ".-...",
    ":": "---...",
    ";": "-.-.-.",
    "=": "-...-",
    "+": ".-.-.",
    "-": "-....-",
    "_": "..--.-",
    '"': ".-..-.",
    "$": "...-..-",
    "@": ".--.-.",
    # Common prosigns (procedural signals) - only non-conflicting ones
    "<SK>": "...-.-",  # End of contact (SK)
    "<KA>": "-.-.-",  # Attention (KA)
    "<SN>": "...-.",  # Understood (SN)
    # Special space character for word breaks
    " ": " ",
}

# Reverse lookup table for decoding
REVERSE_MORSE_TABLE = {code: char for char, code in MORSE_TABLE.items() if char != " "}


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
    def from_wpm(cls, wpm: int) -> "CWTiming":
        """Calculate timing parameters from WPM"""
        if not 5 <= wpm <= 40:
            raise ValueError("WPM must be between 5 and 40")

        # Standard formula: dit length in ms = 1200 / WPM
        dit_ms = 1200.0 / wpm

        return cls(
            wpm=wpm,
            dit_ms=dit_ms,
            dah_ms=dit_ms * 3,
            element_gap_ms=dit_ms,  # Gap between dots/dashes within letter
            letter_gap_ms=dit_ms * 3,  # Gap between letters
            word_gap_ms=dit_ms * 7,  # Gap between words
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

    prosign_pattern = r"<([A-Z]{2,3})>"
    for match in re.finditer(prosign_pattern, text):
        prosign = match.group(0)
        if prosign in MORSE_TABLE:
            # Replace with a unique placeholder that won't conflict
            text = text.replace(prosign, f"\x00{prosign}\x00")

    # Split into words first, then process each word
    words = re.split(r"\s+", text.strip())
    morse_words = []

    for word in words:
        morse_chars = []
        i = 0
        while i < len(word):
            if word[i] == "\x00":
                # Extract prosign
                end = word.find("\x00", i + 1)
                prosign = word[i + 1 : end]
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
            morse_words.append(" ".join(morse_chars))

    # Join words with double spaces (word gap)
    return "  ".join(morse_words)


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
    words = re.split(r"  +", morse.strip())
    decoded_words = []

    for word in words:
        # Clean up the word and split by single spaces
        clean_word = re.sub(r"\s+", " ", word.strip())
        if not clean_word:
            continue

        letters = clean_word.split(" ")
        decoded_letters = []

        for letter in letters:
            if letter in REVERSE_MORSE_TABLE:
                decoded_letters.append(REVERSE_MORSE_TABLE[letter])
            elif letter:  # Skip empty strings
                logger.warning(f"Unknown Morse code '{letter}' - skipping")

        if decoded_letters:
            decoded_words.append("".join(decoded_letters))

    return " ".join(decoded_words)


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
        time.sleep(
            self.timing.word_gap_ms / 1000.0 - self.timing.letter_gap_ms / 1000.0
        )

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
            words = re.split(r"  +", morse.strip())

            for word_idx, word in enumerate(words):
                if word_idx > 0:
                    self._word_gap()  # Gap between words

                # Split word into letters (single space separated)
                letters = word.split(" ")

                for letter_idx, letter in enumerate(letters):
                    if letter_idx > 0:
                        self._letter_gap()  # Gap between letters

                    # Send each element (dot/dash) in the letter
                    for element_idx, element in enumerate(letter):
                        if element_idx > 0:
                            self._element_gap()  # Gap between elements

                        if element == ".":
                            self._send_dit()
                        elif element == "-":
                            self._send_dah()
                        else:
                            logger.warning(
                                f"Unknown Morse element '{element}' - skipping"
                            )

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
    """CW decoder using Goertzel tone detection + adaptive timing analysis."""

    def __init__(self, sample_rate: int = 8000, tone_freq: int = 600, wpm_hint: int = 20):
        self.sample_rate = sample_rate
        self.tone_freq = tone_freq
        self.wpm_hint = wpm_hint
        self._enabled = False
        self._last_result: Dict = {}
        self._frame_ms = 10
        logger.info("CWDecoder initialized (goertzel/adaptive mode)")

    def start_listening(self):
        self._enabled = True

    def stop_listening(self):
        self._enabled = False

    def _goertzel_power(self, frame: List[float], target_freq: float) -> float:
        import math

        n = len(frame)
        if n == 0:
            return 0.0
        k = int(0.5 + ((n * target_freq) / self.sample_rate))
        omega = (2.0 * math.pi * k) / n
        coeff = 2.0 * math.cos(omega)
        s_prev = 0.0
        s_prev2 = 0.0
        for x in frame:
            s = x + coeff * s_prev - s_prev2
            s_prev2 = s_prev
            s_prev = s
        power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2
        return max(0.0, power)

    def decode_audio_buffer(self, audio_data: List[float]) -> Optional[str]:
        import math
        import statistics

        if not audio_data or len(audio_data) < int(self.sample_rate * 0.2):
            return None

        frame_len = max(8, int(self.sample_rate * (self._frame_ms / 1000.0)))
        frames = [audio_data[i : i + frame_len] for i in range(0, len(audio_data) - frame_len, frame_len)]
        if len(frames) < 5:
            return None

        # Detect tone energy with slight frequency robustness (target +-20Hz)
        powers = []
        for fr in frames:
            p0 = self._goertzel_power(fr, self.tone_freq)
            p1 = self._goertzel_power(fr, self.tone_freq - 20)
            p2 = self._goertzel_power(fr, self.tone_freq + 20)
            powers.append(max(p0, p1, p2))

        med = statistics.median(powers)
        abs_dev = [abs(p - med) for p in powers]
        mad = statistics.median(abs_dev) if abs_dev else 0.0
        thresh = med + max(1e-9, 3.0 * mad)
        tone_mask = [p > thresh for p in powers]

        # Run-length encode tone/silence
        runs = []
        cur = tone_mask[0]
        length = 1
        for b in tone_mask[1:]:
            if b == cur:
                length += 1
            else:
                runs.append((cur, length))
                cur = b
                length = 1
        runs.append((cur, length))

        tone_units_ms = [r[1] * self._frame_ms for r in runs if r[0]]
        if not tone_units_ms:
            return None

        tone_sorted = sorted(tone_units_ms)
        short_n = max(1, len(tone_sorted) // 3)
        dit_ms = sum(tone_sorted[:short_n]) / short_n
        dit_ms = max(20.0, min(220.0, dit_ms))

        morse_parts = []
        current_symbol = []
        timing_scores = []

        for is_tone, run_len in runs:
            dur_ms = run_len * self._frame_ms
            units = dur_ms / dit_ms
            if is_tone:
                sym = '-' if units >= 2.2 else '.'
                current_symbol.append(sym)
                timing_scores.append(max(0.0, 1.0 - abs((3.0 if sym == '-' else 1.0) - units) / 3.0))
            else:
                if units <= 1.8:
                    # intra-character gap
                    continue
                if current_symbol:
                    morse_parts.append(''.join(current_symbol))
                    current_symbol = []
                if units >= 4.5:
                    morse_parts.append(' / ')

        if current_symbol:
            morse_parts.append(''.join(current_symbol))

        # Normalize spacing
        morse = []
        for tok in morse_parts:
            if tok == ' / ':
                if morse and morse[-1] != '/':
                    morse.append('/')
            elif tok:
                morse.append(tok)
        if not morse:
            return None

        morse_str = ' '.join(morse).replace('/ ', '/').replace(' /', '/').replace('/', '  ')
        text = morse_to_text(morse_str)

        snr_proxy = (max(powers) / (med + 1e-9)) if med > 0 else 0.0
        timing_conf = sum(timing_scores) / len(timing_scores) if timing_scores else 0.0
        conf = max(0.0, min(1.0, 0.5 * min(1.0, snr_proxy / 8.0) + 0.5 * timing_conf))

        self._last_result = {
            "morse": morse_str,
            "text": text,
            "confidence": round(conf, 3),
            "dit_ms": round(dit_ms, 1),
            "tone_freq": self.tone_freq,
            "snr_proxy": round(snr_proxy, 3),
        }
        return morse_str

    def decode_with_metadata(self, audio_data: List[float]) -> Dict:
        morse = self.decode_audio_buffer(audio_data)
        if not morse:
            return {"ok": False, "reason": "no_cw_detected"}
        return {"ok": True, **self._last_result}

    def get_decoder_stats(self) -> Dict:
        return {
            "enabled": self._enabled,
            "sample_rate": self.sample_rate,
            "tone_freq": self.tone_freq,
            "frame_ms": self._frame_ms,
            "last_result": self._last_result,
        }


class CWFrequencyLocator:
    """Find and track CW-like narrowband peaks from wideband FFT frames."""

    def __init__(self):
        self._tracks: Dict[int, float] = {}

    def scan_fft(self, bins: List[float], center_freq: float, bandwidth: float, top_n: int = 8) -> List[Dict]:
        if not bins or bandwidth <= 0:
            return []

        n = len(bins)
        if n < 8:
            return []

        # Local maxima above adaptive threshold
        sorted_bins = sorted(bins)
        noise_floor = sorted_bins[max(0, int(0.65 * n) - 1)]
        peak_thresh = noise_floor + 8.0
        cands = []
        for i in range(2, n - 2):
            v = bins[i]
            if v < peak_thresh:
                continue
            if v > bins[i - 1] and v > bins[i + 1]:
                # narrowness proxy: peak over local shoulders
                shoulders = (bins[i - 2] + bins[i - 1] + bins[i + 1] + bins[i + 2]) / 4.0
                sharpness = v - shoulders
                if sharpness < 2.0:
                    continue
                frac = (i / (n - 1)) - 0.5
                freq = center_freq + frac * bandwidth
                prev = self._tracks.get(i, freq)
                drift = freq - prev
                self._tracks[i] = freq
                conf = max(0.0, min(1.0, ((v - noise_floor) / 22.0) * (sharpness / 8.0)))
                cands.append({
                    "bin": i,
                    "freq_hz": int(round(freq)),
                    "power_db": round(v, 2),
                    "sharpness": round(sharpness, 2),
                    "drift_hz": round(drift, 1),
                    "confidence": round(conf, 3),
                })

        cands.sort(key=lambda x: (x["confidence"], x["power_db"]), reverse=True)
        return cands[:top_n]


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
    print("\n20 WPM Timing:")
    print(f"  Dit: {timing_20wpm.dit_ms:.1f}ms")
    print(f"  Dah: {timing_20wpm.dah_ms:.1f}ms")
    print(f"  Letter gap: {timing_20wpm.letter_gap_ms:.1f}ms")
