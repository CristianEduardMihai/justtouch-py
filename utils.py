"""
Utilities for JustTouch
Common utility functions and helpers.
"""

import hashlib
import secrets
import time
import uuid
from typing import Dict, Any, Optional
import io

from kivy.logger import Logger

try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    Logger.warning("QR code generation not available (qrcode/PIL missing)")


def generate_session_id() -> str:
    """Generate a unique session ID."""
    # Combine timestamp, random bytes, and UUID for uniqueness
    timestamp = str(int(time.time()))
    random_bytes = secrets.token_hex(8)
    unique_id = str(uuid.uuid4())[:8]
    
    # Create hash for shorter ID
    combined = f"{timestamp}-{random_bytes}-{unique_id}"
    session_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    return f"jt{session_hash}"


def generate_peer_id() -> str:
    """Generate a unique peer ID."""
    return f"peer_{secrets.token_hex(12)}"


def create_qr_code(data: str, size: int = 200) -> Optional[bytes]:
    """Create QR code image from data."""
    if not QR_AVAILABLE:
        Logger.warning("QR code generation not available")
        return None
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Resize if needed
        if size != 200:
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        
        # Convert to bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        return img_buffer.getvalue()
        
    except Exception as e:
        Logger.error(f"Error creating QR code: {e}")
        return None


def create_share_url(session_id: str, app_name: str = "JustTouch") -> str:
    """Create a shareable URL for the session."""
    # This would typically point to a web interface or deep link
    # For now, create a simple format
    return f"justtouch://share?session={session_id}&app={app_name}"


def parse_share_url(url: str) -> Optional[Dict[str, str]]:
    """Parse a share URL and extract session information."""
    try:
        if not url.startswith("justtouch://"):
            return None
        
        # Simple URL parsing
        parts = url.split("?")
        if len(parts) != 2:
            return None
        
        params = {}
        for param in parts[1].split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
        
        return params
        
    except Exception as e:
        Logger.error(f"Error parsing share URL: {e}")
        return None


def validate_session_id(session_id: str) -> bool:
    """Validate a session ID format."""
    if not session_id:
        return False
    
    # Check if it starts with 'jt' and has correct length
    if not session_id.startswith('jt'):
        return False
    
    if len(session_id) != 18:  # 'jt' + 16 hex chars
        return False
    
    # Check if the remaining part is valid hex
    try:
        int(session_id[2:], 16)
        return True
    except ValueError:
        return False


def calculate_transfer_speed(bytes_transferred: int, elapsed_time: float) -> float:
    """Calculate transfer speed in bytes per second."""
    if elapsed_time <= 0:
        return 0
    return bytes_transferred / elapsed_time


def format_transfer_speed(bytes_per_second: float) -> str:
    """Format transfer speed in human readable format."""
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.1f} B/s"
    elif bytes_per_second < 1024 * 1024:
        return f"{bytes_per_second / 1024:.1f} KB/s"
    elif bytes_per_second < 1024 * 1024 * 1024:
        return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bytes_per_second / (1024 * 1024 * 1024):.1f} GB/s"


def estimate_time_remaining(bytes_remaining: int, bytes_per_second: float) -> str:
    """Estimate time remaining for transfer."""
    if bytes_per_second <= 0 or bytes_remaining <= 0:
        return "Unknown"
    
    seconds_remaining = bytes_remaining / bytes_per_second
    
    if seconds_remaining < 60:
        return f"{int(seconds_remaining)}s"
    elif seconds_remaining < 3600:
        minutes = int(seconds_remaining / 60)
        return f"{minutes}m"
    else:
        hours = int(seconds_remaining / 3600)
        minutes = int((seconds_remaining % 3600) / 60)
        return f"{hours}h {minutes}m"


def create_transfer_info(session_id: str, files_count: int, total_size: int) -> Dict[str, Any]:
    """Create transfer information dictionary."""
    return {
        'session_id': session_id,
        'files_count': files_count,
        'total_size': total_size,
        'timestamp': int(time.time()),
        'app': 'JustTouch',
        'version': '1.0.0'
    }


def extract_nfc_data(nfc_payload: bytes) -> Optional[str]:
    """Extract text data from NFC NDEF payload."""
    try:
        # NDEF Text Record format:
        # Status byte, Language length, Language code, Text
        if len(nfc_payload) < 3:
            return None
        
        # Skip status byte
        lang_length = nfc_payload[1]
        
        if len(nfc_payload) < 2 + lang_length:
            return None
        
        # Extract text (skip status, length, and language code)
        text_start = 2 + lang_length
        text_data = nfc_payload[text_start:].decode('utf-8')
        
        return text_data
        
    except Exception as e:
        Logger.error(f"Error extracting NFC data: {e}")
        return None


def create_nfc_payload(text: str, language: str = "en") -> bytes:
    """Create NFC NDEF text record payload."""
    try:
        # NDEF Text Record format
        lang_bytes = language.encode('ascii')
        text_bytes = text.encode('utf-8')
        
        # Status byte: UTF-8 encoding (0x02) + language length
        status_byte = 0x02 | len(lang_bytes)
        
        payload = bytes([status_byte]) + lang_bytes + text_bytes
        return payload
        
    except Exception as e:
        Logger.error(f"Error creating NFC payload: {e}")
        return b""


def get_local_network_range() -> str:
    """Get local network range for discovery."""
    import socket
    
    try:
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Extract network range (assuming /24)
        ip_parts = local_ip.split('.')
        network_range = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        
        return network_range
        
    except Exception as e:
        Logger.error(f"Error getting network range: {e}")
        return "192.168.1.0/24"  # Default fallback


def is_valid_ip(ip_string: str) -> bool:
    """Check if string is a valid IP address."""
    try:
        import socket
        socket.inet_aton(ip_string)
        return True
    except socket.error:
        return False


def get_mime_type_icon(mime_type: str) -> str:
    """Get icon name for MIME type."""
    # Map MIME types to icon names (for UI display)
    icon_map = {
        'image/': 'image',
        'video/': 'video',
        'audio/': 'music',
        'text/': 'file-text',
        'application/pdf': 'file-pdf',
        'application/zip': 'archive',
        'application/x-rar': 'archive',
        'application/x-7z': 'archive',
        'application/msword': 'file-word',
        'application/vnd.ms-excel': 'file-excel',
        'application/vnd.ms-powerpoint': 'file-powerpoint',
    }
    
    for mime_prefix, icon in icon_map.items():
        if mime_type.startswith(mime_prefix):
            return icon
    
    return 'file'  # Default icon


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    sanitized = filename
    
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Ensure not empty
    if not sanitized:
        sanitized = 'unnamed_file'
    
    return sanitized


def chunk_file(file_path: str, chunk_size: int = 8192):
    """Generator to read file in chunks."""
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        Logger.error(f"Error reading file {file_path}: {e}")
        raise


def verify_checksum(file_path: str, expected_checksum: str, algorithm: str = 'md5') -> bool:
    """Verify file checksum."""
    try:
        if algorithm == 'md5':
            hash_obj = hashlib.md5()
        elif algorithm == 'sha256':
            hash_obj = hashlib.sha256()
        else:
            Logger.error(f"Unsupported hash algorithm: {algorithm}")
            return False
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        calculated_checksum = hash_obj.hexdigest()
        return calculated_checksum.lower() == expected_checksum.lower()
        
    except Exception as e:
        Logger.error(f"Error verifying checksum: {e}")
        return False


def get_app_version() -> str:
    """Get application version."""
    return "1.0.0"


def get_platform_info() -> Dict[str, str]:
    """Get platform information."""
    import platform
    
    try:
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
        }
    except Exception as e:
        Logger.error(f"Error getting platform info: {e}")
        return {
            'system': 'Unknown',
            'release': 'Unknown',
            'version': 'Unknown',
            'machine': 'Unknown',
            'processor': 'Unknown',
        }
