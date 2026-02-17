#!/usr/bin/env python3
"""
FT-991A APRS Module
===================
Automatic Packet Reporting System (APRS) implementation for FT-991A.
Provides position beacons, message handling, and emergency communications.

Features:
- APRS position and message packet encoding/decoding
- Emergency frequency management (ARES, RACES, SKYWARN)
- Radio configuration for APRS operations (144.390 MHz FM)
- Licensed operator warnings and confirmation requirements

Callsign: KO4TUV (configured for this station)
"""

import re
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

from .cat import FT991A, Mode

logger = logging.getLogger(__name__)


class APRSPacketType(Enum):
    """APRS packet types based on data type identifier"""
    POSITION_NO_TIMESTAMP = "!"
    POSITION_WITH_TIMESTAMP = "/"
    MESSAGE = ":"
    WEATHER = "_"
    STATUS = ">"
    TELEMETRY = "T"


@dataclass
class APRSPosition:
    """APRS position data structure"""
    latitude: float
    longitude: float
    symbol_table: str = "/"  # Primary table
    symbol_code: str = ">"   # Car symbol
    comment: str = ""
    timestamp: Optional[str] = None


@dataclass
class APRSMessage:
    """APRS message data structure"""
    source: str
    destination: str
    message: str
    message_id: Optional[str] = None


@dataclass
class APRSPacket:
    """Decoded APRS packet structure"""
    source_call: str
    destination: str
    path: List[str]
    packet_type: str
    data: Dict[str, Any]
    raw_packet: str


class EmergencyKit:
    """
    Pre-programmed emergency communication frequencies and procedures.
    
    Covers ARES (Amateur Radio Emergency Service), RACES (Radio Amateur Civil
    Emergency Service), SKYWARN, and other emergency nets for disaster response.
    """
    
    # ARES/RACES Emergency Frequencies (MHz)
    EMERGENCY_FREQS = {
        # VHF Repeaters (2m band)
        "ARES_PRIMARY_VHF": {"freq": 146.52, "mode": "FM", "notes": "National Simplex Emergency"},
        "ARES_BACKUP_VHF": {"freq": 146.94, "mode": "FM", "notes": "Regional ARES Net"},
        "RACES_VHF": {"freq": 147.42, "mode": "FM", "notes": "Local RACES Net"},
        
        # UHF Repeaters (70cm band)
        "ARES_UHF": {"freq": 446.00, "mode": "FM", "notes": "ARES UHF Net"},
        "SKYWARN_UHF": {"freq": 442.15, "mode": "FM", "notes": "SKYWARN Weather Net"},
        
        # HF Emergency Frequencies
        "ARES_HF_40M": {"freq": 7.265, "mode": "LSB", "notes": "40m ARES Emergency Net"},
        "ARES_HF_80M": {"freq": 3.965, "mode": "LSB", "notes": "80m ARES Emergency Net"},
        "NTTN_HF": {"freq": 14.265, "mode": "USB", "notes": "National Traffic & Training Net"},
        
        # Digital Emergency
        "WINLINK_VHF": {"freq": 144.910, "mode": "DATA_FM", "notes": "VHF Winlink Gateway"},
        "FT8_EMERGENCY": {"freq": 7.074, "mode": "DATA_USB", "notes": "40m FT8 Emergency"},
        
        # APRS
        "APRS_PRIMARY": {"freq": 144.390, "mode": "FM", "notes": "North America APRS"},
        "APRS_ALTERNATE": {"freq": 144.350, "mode": "FM", "notes": "Alternate APRS"},
        
        # Maritime Emergency
        "MARINE_VHF_16": {"freq": 156.8, "mode": "FM", "notes": "Maritime Emergency (monitor only)"},
        
        # Aviation Emergency (receive only - no transmit without license)
        "AVIATION_121_5": {"freq": 121.5, "mode": "AM", "notes": "Aviation Emergency (RX only)"},
    }
    
    # Emergency Procedures and Net Times
    EMERGENCY_NETS = {
        "ARES_WEEKLY": {
            "frequency": 147.42,
            "mode": "FM",
            "day": "Sunday",
            "time": "19:00 local",
            "notes": "Weekly training net - check-ins welcome"
        },
        "SKYWARN": {
            "frequency": 442.15,
            "mode": "FM", 
            "day": "As needed",
            "time": "Severe weather activation",
            "notes": "Activated during severe weather watches/warnings"
        },
        "RACES_DRILL": {
            "frequency": 147.42,
            "mode": "FM",
            "day": "First Saturday",
            "time": "09:00 local",
            "notes": "Monthly emergency drill"
        }
    }
    
    @classmethod
    def list_frequencies(cls) -> List[Dict[str, Any]]:
        """Return list of all emergency frequencies"""
        return [
            {"name": name, **data}
            for name, data in cls.EMERGENCY_FREQS.items()
        ]
    
    @classmethod
    def get_frequency(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get specific emergency frequency by name"""
        return cls.EMERGENCY_FREQS.get(name)
    
    @classmethod
    def list_nets(cls) -> List[Dict[str, Any]]:
        """Return list of emergency nets and schedules"""
        return [
            {"net": name, **data}
            for name, data in cls.EMERGENCY_NETS.items()
        ]


class APRSClient:
    """
    APRS client for FT-991A transceiver.
    
    Handles APRS packet encoding/decoding and radio configuration for
    APRS operations on 144.390 MHz FM at 1200 baud.
    
    Usage:
        radio = FT991A('/dev/ttyUSB0')
        radio.connect()
        
        aprs = APRSClient(radio, callsign="KO4TUV")
        aprs.setup_aprs()
        
        # Send position beacon (requires --confirm)
        packet = aprs.encode_aprs_position("KO4TUV", 35.7796, -78.6382, "OpenClaw Station")
        # aprs.transmit_packet(packet)  # Only with operator confirmation
        
        radio.disconnect()
    """
    
    def __init__(self, radio: FT991A, callsign: str = "KO4TUV"):
        self.radio = radio
        self.callsign = callsign.upper()
        self.aprs_frequency = 144_390_000  # 144.390 MHz in Hz
        self.emergency_kit = EmergencyKit()
        
        # Validate callsign format
        if not re.match(r'^[A-Z0-9]{1,6}(-[1-9][0-9]?)?$', self.callsign):
            raise ValueError(f"Invalid callsign format: {self.callsign}")
    
    def setup_aprs(self) -> bool:
        """
        Configure radio for APRS operation.
        
        Sets:
        - Frequency: 144.390 MHz (North America APRS)
        - Mode: FM 
        - Bandwidth: Wide (for 1200 baud packet)
        - Power: Appropriate level (typically 5-25W for VHF)
        
        Returns:
            bool: True if configuration successful
        """
        try:
            logger.info("Configuring radio for APRS operation...")
            
            # Set APRS frequency (144.390 MHz)
            self.radio.set_frequency_a(self.aprs_frequency)
            logger.info(f"Set frequency to 144.390 MHz")
            
            # Set FM mode (wide bandwidth for packet)
            self.radio.set_mode(Mode.FM)
            logger.info("Set mode to FM")
            
            # Optional: Set appropriate power level
            # Note: Power setting depends on local conditions and courtesy
            # Typical APRS power: 5-25W for local coverage
            
            logger.info("APRS configuration complete")
            logger.info("Ready for APRS operations on 144.390 MHz FM")
            logger.warning("⚠️  TRANSMISSION REQUIRES LICENSED OPERATOR PRESENT")
            logger.warning("⚠️  Use --confirm flag to acknowledge legal requirements")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure APRS: {e}")
            return False
    
    def encode_aprs_position(self, callsign: str, lat: float, lon: float, 
                           comment: str = "", symbol_table: str = "/", 
                           symbol_code: str = ">") -> str:
        """
        Encode APRS position packet.
        
        Args:
            callsign: Station callsign (e.g., "KO4TUV")
            lat: Latitude in decimal degrees (positive = North)
            lon: Longitude in decimal degrees (negative = West)
            comment: Optional comment text
            symbol_table: Symbol table ("/" primary, "\\" alternate)
            symbol_code: Symbol code (e.g., ">" for car, "-" for house)
        
        Returns:
            str: Complete APRS packet string ready for transmission
            
        Example:
            KO4TUV>APRS,WIDE1-1,WIDE2-1:!3546.75N/07838.29W>OpenClaw Station
        """
        try:
            # Convert decimal degrees to APRS format (DDMM.MM)
            lat_deg = int(abs(lat))
            lat_min = (abs(lat) - lat_deg) * 60
            lat_ns = 'N' if lat >= 0 else 'S'
            lat_str = f"{lat_deg:02d}{lat_min:05.2f}{lat_ns}"
            
            lon_deg = int(abs(lon))
            lon_min = (abs(lon) - lon_deg) * 60
            lon_ew = 'E' if lon >= 0 else 'W'
            lon_str = f"{lon_deg:03d}{lon_min:05.2f}{lon_ew}"
            
            # Build position string
            position = f"{lat_str}{symbol_table}{lon_str}{symbol_code}"
            
            # Build complete packet
            path = "APRS,WIDE1-1,WIDE2-1"  # Standard APRS path
            packet = f"{callsign}>{path}:!{position}{comment}"
            
            logger.debug(f"Encoded position packet: {packet}")
            return packet
            
        except Exception as e:
            logger.error(f"Failed to encode position: {e}")
            raise ValueError(f"Position encoding failed: {e}")
    
    def encode_aprs_message(self, source: str, dest: str, message: str, 
                          message_id: Optional[str] = None) -> str:
        """
        Encode APRS message packet.
        
        Args:
            source: Source callsign
            dest: Destination callsign (padded to 9 chars)
            message: Message text (max ~67 chars for APRS)
            message_id: Optional message ID for acknowledgment
        
        Returns:
            str: APRS message packet string
            
        Example:
            KO4TUV>APRS,WIDE1-1:N0CALL   :Hello from OpenClaw{001
        """
        try:
            # Pad destination to 9 characters
            dest_padded = f"{dest:<9}"[:9]
            
            # Build message string
            if message_id:
                msg_str = f"{dest_padded}:{message}{{{message_id}"
            else:
                msg_str = f"{dest_padded}:{message}"
            
            # Build complete packet
            path = "APRS,WIDE1-1"  # Messages typically use shorter path
            packet = f"{source}>{path}::{msg_str}"
            
            logger.debug(f"Encoded message packet: {packet}")
            return packet
            
        except Exception as e:
            logger.error(f"Failed to encode message: {e}")
            raise ValueError(f"Message encoding failed: {e}")
    
    def decode_aprs_packet(self, raw_packet: str) -> Optional[APRSPacket]:
        """
        Decode APRS packet into structured data.
        
        Args:
            raw_packet: Raw APRS packet string
            
        Returns:
            APRSPacket: Decoded packet data or None if invalid
            
        Handles:
        - Position reports (with/without timestamp)
        - Messages
        - Weather reports
        - Status updates
        """
        try:
            # Basic packet format: CALL>DEST,PATH:DATA
            if ':' not in raw_packet:
                logger.warning(f"Invalid packet format (no data separator): {raw_packet}")
                return None
            
            header, data = raw_packet.split(':', 1)
            
            # Parse header: SOURCE>DEST,PATH1,PATH2...
            if '>' not in header:
                logger.warning(f"Invalid header format: {header}")
                return None
            
            source_call, dest_path = header.split('>', 1)
            path_parts = dest_path.split(',')
            destination = path_parts[0]
            path = path_parts[1:] if len(path_parts) > 1 else []
            
            # Validate we have actual content
            if not source_call or not destination:
                logger.warning(f"Missing source or destination: {header}")
                return None
            
            # Determine packet type from first character of data
            if not data:
                logger.warning("Empty data field")
                return None
            
            packet_type = data[0]
            parsed_data = {}
            
            # Parse based on packet type
            if packet_type in ['!', '/']:
                # Position report
                parsed_data = self._parse_position_data(data)
                parsed_data['type'] = 'position'
                
            elif packet_type == ':':
                # Message
                parsed_data = self._parse_message_data(data[1:])
                parsed_data['type'] = 'message'
                
            elif packet_type == '_':
                # Weather
                parsed_data = self._parse_weather_data(data[1:])
                parsed_data['type'] = 'weather'
                
            elif packet_type == '>':
                # Status
                parsed_data = {'status_text': data[1:], 'type': 'status'}
                
            else:
                # Unknown type
                parsed_data = {'raw_data': data, 'type': 'unknown'}
                logger.warning(f"Unknown packet type: {packet_type}")
            
            return APRSPacket(
                source_call=source_call,
                destination=destination,
                path=path,
                packet_type=packet_type,
                data=parsed_data,
                raw_packet=raw_packet
            )
            
        except Exception as e:
            logger.error(f"Failed to decode packet: {e}")
            logger.debug(f"Raw packet: {raw_packet}")
            return None
    
    def _parse_position_data(self, data: str) -> Dict[str, Any]:
        """Parse APRS position data"""
        try:
            # Skip timestamp if present (format: /HHMMSS or DDHHMM)
            pos_data = data[1:]  # Skip ! or /
            if data.startswith('/') and len(pos_data) >= 7:
                # Has timestamp, skip it
                if pos_data[6] in ['h', 'z']:  # HMS format
                    pos_data = pos_data[7:]
                elif pos_data[6] == '/':  # DHM format
                    pos_data = pos_data[7:]
            
            # Parse position: DDMM.MMN/DDDMM.MMW or similar
            if len(pos_data) < 19:  # Minimum for lat/lon/symbol
                return {'error': 'Position data too short'}
            
            # Extract latitude (8 chars: DDMM.MMN)
            lat_str = pos_data[:8]
            symbol_table = pos_data[8]
            
            # Extract longitude (9 chars: DDDMM.MMW)  
            lon_str = pos_data[9:18]
            symbol_code = pos_data[18]
            
            # Parse coordinates
            try:
                lat_deg = int(lat_str[:2])
                lat_min = float(lat_str[2:7])
                lat_ns = lat_str[7]
                latitude = lat_deg + lat_min/60
                if lat_ns == 'S':
                    latitude = -latitude
                
                lon_deg = int(lon_str[:3])
                lon_min = float(lon_str[3:8])
                lon_ew = lon_str[8]
                longitude = lon_deg + lon_min/60
                if lon_ew == 'W':
                    longitude = -longitude
                    
            except (ValueError, IndexError):
                return {'error': 'Invalid coordinate format'}
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90):
                return {'error': f'Invalid latitude: {latitude}'}
            if not (-180 <= longitude <= 180):
                return {'error': f'Invalid longitude: {longitude}'}
            
            # Extract comment (everything after symbol)
            comment = pos_data[19:] if len(pos_data) > 19 else ""
            
            return {
                'latitude': latitude,
                'longitude': longitude,
                'symbol_table': symbol_table,
                'symbol_code': symbol_code,
                'comment': comment.strip(),
                'type': 'position'
            }
            
        except Exception as e:
            return {'error': f'Position parsing failed: {e}'}
    
    def _parse_message_data(self, data: str) -> Dict[str, Any]:
        """Parse APRS message data"""
        try:
            # Format: ADDRESSEE:MESSAGE{ID or :MESSAGE
            if len(data) < 10:  # At least 9 char addressee + :
                return {'error': 'Message too short'}
            
            addressee = data[:9].strip()
            if len(data) <= 9 or data[9] != ':':
                return {'error': 'Invalid message format'}
            
            message_text = data[10:]
            message_id = None
            
            # Check for message ID (format: message{ID)
            if '{' in message_text:
                message_text, message_id = message_text.rsplit('{', 1)
            
            return {
                'addressee': addressee,
                'message': message_text,
                'message_id': message_id,
                'type': 'message'
            }
            
        except Exception as e:
            return {'error': f'Message parsing failed: {e}'}
    
    def _parse_weather_data(self, data: str) -> Dict[str, Any]:
        """Parse APRS weather data (basic implementation)"""
        # Weather parsing is complex - this is a basic implementation
        # Full weather parsing would handle wind, temperature, humidity, etc.
        return {
            'weather_data': data,
            'note': 'Weather parsing not fully implemented'
        }
    
    def transmit_packet(self, packet: str, confirmed: bool = False) -> bool:
        """
        Transmit APRS packet via radio.
        
        ⚠️  CRITICAL SAFETY WARNING ⚠️
        This method requires:
        1. Licensed amateur radio operator physically present
        2. Explicit confirmation via --confirm flag
        3. Legal compliance with amateur radio regulations
        
        Args:
            packet: APRS packet string to transmit
            confirmed: Must be True to proceed (safety check)
            
        Returns:
            bool: True if transmission successful
        """
        if not confirmed:
            logger.error("❌ TRANSMISSION DENIED - Missing --confirm flag")
            logger.error("⚠️  Amateur radio transmission requires licensed operator present")
            logger.error("⚠️  Use --confirm flag to acknowledge legal compliance")
            return False
        
        logger.warning("🚨 TRANSMITTING ON AMATEUR RADIO FREQUENCIES")
        logger.warning("⚠️  Licensed operator must be physically present")
        logger.warning(f"📡 Packet: {packet}")
        
        try:
            # Note: Actual transmission would require additional hardware/software
            # for packet encoding (TNC, sound card interface, etc.)
            logger.error("❌ TRANSMISSION HARDWARE NOT IMPLEMENTED")
            logger.error("📋 Packet ready for external TNC/sound card interface")
            logger.error(f"📦 Encoded packet: {packet}")
            
            # TODO: Implement actual packet transmission via:
            # - Hardware TNC (Terminal Node Controller)
            # - Software TNC (direwolf, etc.)
            # - Sound card interface (AFSK modulation)
            
            return False  # Not implemented yet
            
        except Exception as e:
            logger.error(f"Transmission failed: {e}")
            return False