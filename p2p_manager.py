import asyncio
import json
import os
import hashlib
import socket
import threading
import time
from pathlib import Path
from typing import List, Callable, Optional, Dict, Any

from kivy.logger import Logger

try:
    import aiortc
    from aiortc import RTCPeerConnection, RTCDataChannel, RTCSessionDescription
    from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    Logger.warning("WebRTC (aiortc) not available")

try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    LIBTORRENT_AVAILABLE = False
    Logger.warning("LibTorrent not available")


class FileChunk:
    """Represents a chunk of file data."""
    
    def __init__(self, file_id: str, chunk_id: int, data: bytes, total_chunks: int):
        self.file_id = file_id
        self.chunk_id = chunk_id
        self.data = data
        self.total_chunks = total_chunks
        self.checksum = hashlib.md5(data).hexdigest()


class TransferSession:
    """Represents a file transfer session."""
    
    def __init__(self, session_id: str, files: List[str] = None):
        self.session_id = session_id
        self.files = files or []
        self.file_metadata = {}
        self.received_chunks = {}
        self.total_size = 0
        self.transferred_size = 0
        self.is_active = False
        self.peer_connection = None
        self.data_channel = None
        
        if files:
            self._calculate_metadata()
    
    def _calculate_metadata(self):
        """Calculate metadata for all files in the session."""
        for file_path in self.files:
            if os.path.exists(file_path):
                file_stat = os.stat(file_path)
                file_id = hashlib.md5(file_path.encode()).hexdigest()
                
                self.file_metadata[file_id] = {
                    'path': file_path,
                    'name': os.path.basename(file_path),
                    'size': file_stat.st_size,
                    'chunks': (file_stat.st_size // 8192) + 1,  # 8KB chunks
                    'checksum': self._calculate_file_checksum(file_path)
                }
                self.total_size += file_stat.st_size
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        except Exception as e:
            Logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""
        return hash_md5.hexdigest()


class P2PManager:
    """Manages peer-to-peer file transfers."""
    
    def __init__(self):
        self.sessions: Dict[str, TransferSession] = {}
        self.signaling_server = None
        self.local_ip = self._get_local_ip()
        self.discovery_port = 45678
        self.transfer_port = 45679
        self._discovery_socket = None
        self._transfer_server = None
        self._running = False
        
        self._start_discovery_service()
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    def _start_discovery_service(self):
        """Start UDP discovery service for local network peers."""
        def discovery_worker():
            try:
                self._discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._discovery_socket.bind(('', self.discovery_port))
                self._discovery_socket.settimeout(1.0)
                
                Logger.info(f"P2P: Discovery service started on port {self.discovery_port}")
                
                while self._running:
                    try:
                        data, addr = self._discovery_socket.recvfrom(1024)
                        self._handle_discovery_message(data.decode(), addr)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self._running:
                            Logger.error(f"Discovery service error: {e}")
                        break
                        
            except Exception as e:
                Logger.error(f"Failed to start discovery service: {e}")
        
        self._running = True
        discovery_thread = threading.Thread(target=discovery_worker, daemon=True)
        discovery_thread.start()
    
    def _handle_discovery_message(self, message: str, addr: tuple):
        """Handle incoming discovery messages."""
        try:
            data = json.loads(message)
            if data.get('type') == 'session_discovery':
                session_id = data.get('session_id')
                if session_id in self.sessions:
                    # Respond with session info
                    response = {
                        'type': 'session_response',
                        'session_id': session_id,
                        'endpoint': f"{self.local_ip}:{self.transfer_port}"
                    }
                    response_data = json.dumps(response).encode()
                    self._discovery_socket.sendto(response_data, addr)
                    
        except json.JSONDecodeError:
            pass  # Ignore invalid messages
    
    def create_session(self, session_id: str, files: List[str]) -> bool:
        """Create a new transfer session."""
        try:
            session = TransferSession(session_id, files)
            self.sessions[session_id] = session
            
            Logger.info(f"P2P: Created session {session_id} with {len(files)} files")
            return True
            
        except Exception as e:
            Logger.error(f"Error creating session: {e}")
            return False
    
    def discover_session(self, session_id: str) -> Optional[str]:
        """Discover a session on the local network."""
        try:
            # Broadcast discovery message
            discovery_msg = {
                'type': 'session_discovery',
                'session_id': session_id
            }
            msg_data = json.dumps(discovery_msg).encode()
            
            # Create discovery socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(5.0)  # 5 second timeout
            
            # Broadcast to local network
            sock.sendto(msg_data, ('<broadcast>', self.discovery_port))
            
            # Wait for response
            try:
                data, addr = sock.recvfrom(1024)
                response = json.loads(data.decode())
                
                if (response.get('type') == 'session_response' and 
                    response.get('session_id') == session_id):
                    endpoint = response.get('endpoint')
                    sock.close()
                    Logger.info(f"P2P: Discovered session at {endpoint}")
                    return endpoint
                    
            except socket.timeout:
                Logger.info("P2P: No session response received")
            except json.JSONDecodeError:
                Logger.warning("P2P: Invalid discovery response")
            
            sock.close()
            return None
            
        except Exception as e:
            Logger.error(f"Session discovery error: {e}")
            return None
    
    def send_files(self, session_id: str, progress_callback: Callable[[float, str], None] = None) -> bool:
        """Send files for a session."""
        if session_id not in self.sessions:
            Logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        
        try:
            if WEBRTC_AVAILABLE:
                return self._send_files_webrtc(session, progress_callback)
            else:
                return self._send_files_direct(session, progress_callback)
                
        except Exception as e:
            Logger.error(f"Error sending files: {e}")
            return False
    
    def receive_files(self, session_id: str, download_dir: str, 
                     progress_callback: Callable[[float, str], None] = None) -> bool:
        """Receive files for a session."""
        try:
            # Discover the session
            endpoint = self.discover_session(session_id)
            if not endpoint:
                Logger.error(f"Could not discover session {session_id}")
                return False
            
            if WEBRTC_AVAILABLE:
                return self._receive_files_webrtc(session_id, download_dir, endpoint, progress_callback)
            else:
                return self._receive_files_direct(session_id, download_dir, endpoint, progress_callback)
                
        except Exception as e:
            Logger.error(f"Error receiving files: {e}")
            return False
    
    def _send_files_direct(self, session: TransferSession, 
                          progress_callback: Callable[[float, str], None] = None) -> bool:
        """Send files using direct TCP connection."""
        try:
            # Start TCP server
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.local_ip, self.transfer_port))
            server_socket.listen(1)
            server_socket.settimeout(30.0)  # 30 second timeout
            
            Logger.info(f"P2P: Waiting for connection on {self.local_ip}:{self.transfer_port}")
            
            try:
                client_socket, addr = server_socket.accept()
                Logger.info(f"P2P: Client connected from {addr}")
                
                # Send session metadata
                metadata = {
                    'session_id': session.session_id,
                    'files': session.file_metadata,
                    'total_size': session.total_size
                }
                self._send_json(client_socket, metadata)
                
                # Send files
                for file_id, file_info in session.file_metadata.items():
                    file_path = file_info['path']
                    file_size = file_info['size']
                    
                    if progress_callback:
                        progress_callback(
                            (session.transferred_size / session.total_size) * 100,
                            f"Sending {file_info['name']}"
                        )
                    
                    with open(file_path, 'rb') as f:
                        bytes_sent = 0
                        while bytes_sent < file_size:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            
                            client_socket.sendall(chunk)
                            bytes_sent += len(chunk)
                            session.transferred_size += len(chunk)
                            
                            if progress_callback:
                                progress = (session.transferred_size / session.total_size) * 100
                                progress_callback(progress, f"Sending {file_info['name']}")
                
                client_socket.close()
                server_socket.close()
                
                Logger.info("P2P: File transfer completed successfully")
                return True
                
            except socket.timeout:
                Logger.error("P2P: Connection timeout")
                server_socket.close()
                return False
                
        except Exception as e:
            Logger.error(f"Direct transfer error: {e}")
            return False
    
    def _receive_files_direct(self, session_id: str, download_dir: str, endpoint: str,
                             progress_callback: Callable[[float, str], None] = None) -> bool:
        """Receive files using direct TCP connection."""
        try:
            host, port = endpoint.split(':')
            port = int(port)
            
            # Connect to sender
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(30.0)
            client_socket.connect((host, port))
            
            Logger.info(f"P2P: Connected to sender at {endpoint}")
            
            # Receive metadata
            metadata = self._receive_json(client_socket)
            if not metadata or metadata.get('session_id') != session_id:
                Logger.error("Invalid session metadata")
                client_socket.close()
                return False
            
            files_info = metadata['files']
            total_size = metadata['total_size']
            received_size = 0
            
            # Create download directory
            download_path = Path(download_dir)
            download_path.mkdir(parents=True, exist_ok=True)
            
            # Receive files
            for file_id, file_info in files_info.items():
                file_name = file_info['name']
                file_size = file_info['size']
                file_path = download_path / file_name
                
                if progress_callback:
                    progress_callback(
                        (received_size / total_size) * 100,
                        f"Receiving {file_name}"
                    )
                
                with open(file_path, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < file_size:
                        chunk = client_socket.recv(min(8192, file_size - bytes_received))
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        bytes_received += len(chunk)
                        received_size += len(chunk)
                        
                        if progress_callback:
                            progress = (received_size / total_size) * 100
                            progress_callback(progress, f"Receiving {file_name}")
            
            client_socket.close()
            Logger.info("P2P: File reception completed successfully")
            return True
            
        except Exception as e:
            Logger.error(f"Direct reception error: {e}")
            return False
    
    def _send_json(self, socket: socket.socket, data: dict):
        """Send JSON data over socket."""
        json_data = json.dumps(data).encode('utf-8')
        length = len(json_data)
        socket.sendall(length.to_bytes(4, byteorder='big'))
        socket.sendall(json_data)
    
    def _receive_json(self, socket: socket.socket) -> dict:
        """Receive JSON data from socket."""
        # First receive the length
        length_bytes = socket.recv(4)
        if len(length_bytes) < 4:
            return None
        
        length = int.from_bytes(length_bytes, byteorder='big')
        
        # Then receive the JSON data
        json_data = b''
        while len(json_data) < length:
            chunk = socket.recv(length - len(json_data))
            if not chunk:
                return None
            json_data += chunk
        
        return json.loads(json_data.decode('utf-8'))
    
    def _send_files_webrtc(self, session: TransferSession,
                          progress_callback: Callable[[float, str], None] = None) -> bool:
        """Send files using WebRTC (placeholder implementation)."""
        Logger.info("WebRTC sending not yet implemented - falling back to direct transfer")
        return self._send_files_direct(session, progress_callback)
    
    def _receive_files_webrtc(self, session_id: str, download_dir: str, endpoint: str,
                             progress_callback: Callable[[float, str], None] = None) -> bool:
        """Receive files using WebRTC (placeholder implementation)."""
        Logger.info("WebRTC receiving not yet implemented - falling back to direct transfer")
        return self._receive_files_direct(session_id, download_dir, endpoint, progress_callback)
    
    def cleanup_session(self, session_id: str):
        """Clean up a transfer session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            Logger.info(f"P2P: Cleaned up session {session_id}")
    
    def stop(self):
        """Stop the P2P manager."""
        self._running = False
        if self._discovery_socket:
            self._discovery_socket.close()
        Logger.info("P2P: Manager stopped")
