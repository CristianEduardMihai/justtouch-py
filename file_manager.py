import os
import shutil
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

from kivy.logger import Logger

try:
    from plyer import storagepath
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    Logger.warning("Plyer not available - using default paths")


class FileInfo:
    def __init__(self, file_path: str):
        self.path = file_path
        self.name = os.path.basename(file_path)
        self.size = 0
        self.mime_type = "application/octet-stream"
        self.checksum = ""
        self.last_modified = 0
        
        if os.path.exists(file_path):
            self._load_info()
    
    def _load_info(self):
        """Load file information."""
        try:
            stat = os.stat(self.path)
            self.size = stat.st_size
            self.last_modified = stat.st_mtime
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(self.path)
            if mime_type:
                self.mime_type = mime_type
            
            # Calculate checksum for smaller files
            if self.size < 100 * 1024 * 1024:  # 100MB limit
                self.checksum = self._calculate_checksum()
                
        except Exception as e:
            Logger.error(f"Error loading file info for {self.path}: {e}")
    
    def _calculate_checksum(self) -> str:
        """Calculate MD5 checksum of the file."""
        hash_md5 = hashlib.md5()
        try:
            with open(self.path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            Logger.error(f"Error calculating checksum: {e}")
            return ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'size': self.size,
            'mime_type': self.mime_type,
            'checksum': self.checksum,
            'last_modified': self.last_modified
        }
    
    @classmethod
    def from_dict(cls, data: Dict, download_path: str = None) -> 'FileInfo':
        """Create FileInfo from dictionary."""
        file_info = cls.__new__(cls)
        file_info.name = data['name']
        file_info.size = data['size']
        file_info.mime_type = data.get('mime_type', 'application/octet-stream')
        file_info.checksum = data.get('checksum', '')
        file_info.last_modified = data.get('last_modified', 0)
        
        if download_path:
            file_info.path = os.path.join(download_path, file_info.name)
        else:
            file_info.path = file_info.name
            
        return file_info


class FileManager:
    """Manages file operations for JustTouch."""
    
    def __init__(self):
        self.app_dir = self._get_app_directory()
        self.downloads_dir = self._get_downloads_directory()
        self.temp_dir = self._get_temp_directory()
        self.metadata_file = os.path.join(self.app_dir, 'file_metadata.json')
        
        self._ensure_directories()
        self._load_metadata()
    
    def _get_app_directory(self) -> str:
        """Get the application directory."""
        if PLYER_AVAILABLE:
            try:
                app_dir = os.path.join(storagepath.get_application_dir(), 'JustTouch')
            except Exception:
                app_dir = os.path.join(Path.home(), '.justtouch')
        else:
            app_dir = os.path.join(Path.home(), '.justtouch')
        
        return app_dir
    
    def _get_downloads_directory(self) -> str:
        """Get the downloads directory."""
        if PLYER_AVAILABLE:
            try:
                downloads_dir = os.path.join(storagepath.get_downloads_dir(), 'JustTouch')
            except Exception:
                downloads_dir = os.path.join(self.app_dir, 'downloads')
        else:
            downloads_dir = os.path.join(self.app_dir, 'downloads')
        
        return downloads_dir
    
    def _get_temp_directory(self) -> str:
        """Get the temporary directory."""
        return os.path.join(self.app_dir, 'temp')
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        for directory in [self.app_dir, self.downloads_dir, self.temp_dir]:
            Path(directory).mkdir(parents=True, exist_ok=True)
            Logger.info(f"FileManager: Ensured directory {directory}")
    
    def _load_metadata(self):
        """Load file metadata from storage."""
        self.file_metadata = {}
        
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    self.file_metadata = json.load(f)
                Logger.info("FileManager: Loaded file metadata")
            except Exception as e:
                Logger.error(f"Error loading file metadata: {e}")
                self.file_metadata = {}
    
    def _save_metadata(self):
        """Save file metadata to storage."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.file_metadata, f, indent=2)
            Logger.debug("FileManager: Saved file metadata")
        except Exception as e:
            Logger.error(f"Error saving file metadata: {e}")
    
    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get information about a file."""
        try:
            if os.path.exists(file_path):
                return FileInfo(file_path)
            else:
                Logger.warning(f"File not found: {file_path}")
                return None
        except Exception as e:
            Logger.error(f"Error getting file info: {e}")
            return None
    
    def get_files_info(self, file_paths: List[str]) -> List[FileInfo]:
        """Get information about multiple files."""
        files_info = []
        for file_path in file_paths:
            file_info = self.get_file_info(file_path)
            if file_info:
                files_info.append(file_info)
        return files_info
    
    def prepare_files_for_transfer(self, file_paths: List[str]) -> Dict[str, Dict]:
        """Prepare files for transfer and return metadata."""
        files_metadata = {}
        
        for file_path in file_paths:
            file_info = self.get_file_info(file_path)
            if file_info:
                file_id = hashlib.md5(file_path.encode()).hexdigest()
                files_metadata[file_id] = file_info.to_dict()
                files_metadata[file_id]['path'] = file_path
                
                # Store in local metadata
                self.file_metadata[file_id] = files_metadata[file_id]
        
        self._save_metadata()
        return files_metadata
    
    def get_download_directory(self) -> str:
        """Get the downloads directory path."""
        return self.downloads_dir
    
    def get_temp_directory(self) -> str:
        """Get the temporary directory path."""
        return self.temp_dir
    
    def get_safe_filename(self, filename: str) -> str:
        """Get a safe filename by removing invalid characters."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        safe_filename = filename
        
        for char in invalid_chars:
            safe_filename = safe_filename.replace(char, '_')
        
        # Ensure filename is not too long
        if len(safe_filename) > 255:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = name[:255-len(ext)] + ext
        
        return safe_filename
    
    def get_unique_filename(self, directory: str, filename: str) -> str:
        """Get a unique filename in the specified directory."""
        safe_filename = self.get_safe_filename(filename)
        file_path = os.path.join(directory, safe_filename)
        
        if not os.path.exists(file_path):
            return safe_filename
        
        # File exists, add number suffix
        name, ext = os.path.splitext(safe_filename)
        counter = 1
        
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_path = os.path.join(directory, new_filename)
            
            if not os.path.exists(new_path):
                return new_filename
            
            counter += 1
            
            # Prevent infinite loop
            if counter > 9999:
                import time
                timestamp = int(time.time())
                return f"{name}_{timestamp}{ext}"
    
    def create_temp_file(self, filename: str) -> str:
        """Create a temporary file path."""
        safe_filename = self.get_safe_filename(filename)
        temp_path = os.path.join(self.temp_dir, safe_filename)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        return temp_path
    
    def move_temp_to_downloads(self, temp_path: str, final_filename: str = None) -> str:
        """Move a file from temp to downloads directory."""
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Temporary file not found: {temp_path}")
        
        if final_filename is None:
            final_filename = os.path.basename(temp_path)
        
        unique_filename = self.get_unique_filename(self.downloads_dir, final_filename)
        final_path = os.path.join(self.downloads_dir, unique_filename)
        
        try:
            shutil.move(temp_path, final_path)
            Logger.info(f"FileManager: Moved {temp_path} to {final_path}")
            return final_path
        except Exception as e:
            Logger.error(f"Error moving file: {e}")
            raise
    
    def verify_file_integrity(self, file_path: str, expected_checksum: str) -> bool:
        """Verify file integrity using checksum."""
        if not expected_checksum:
            Logger.warning("No checksum provided for verification")
            return True  # Assume valid if no checksum
        
        try:
            file_info = FileInfo(file_path)
            actual_checksum = file_info.checksum
            
            is_valid = actual_checksum == expected_checksum
            if not is_valid:
                Logger.warning(f"Checksum mismatch for {file_path}")
                Logger.warning(f"Expected: {expected_checksum}")
                Logger.warning(f"Actual: {actual_checksum}")
            
            return is_valid
            
        except Exception as e:
            Logger.error(f"Error verifying file integrity: {e}")
            return False
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up old temporary files."""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            Logger.info(f"FileManager: Cleaned up old temp file {file_path}")
                    except Exception as e:
                        Logger.error(f"Error cleaning up {file_path}: {e}")
                        
        except Exception as e:
            Logger.error(f"Error during temp file cleanup: {e}")
    
    def get_storage_info(self) -> Dict[str, int]:
        """Get storage information."""
        storage_info = {
            'downloads_size': 0,
            'temp_size': 0,
            'available_space': 0
        }
        
        try:
            # Calculate downloads directory size
            for root, dirs, files in os.walk(self.downloads_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        storage_info['downloads_size'] += os.path.getsize(file_path)
                    except Exception:
                        pass
            
            # Calculate temp directory size
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        storage_info['temp_size'] += os.path.getsize(file_path)
                    except Exception:
                        pass
            
            # Get available space
            if hasattr(shutil, 'disk_usage'):
                usage = shutil.disk_usage(self.app_dir)
                storage_info['available_space'] = usage.free
            
        except Exception as e:
            Logger.error(f"Error getting storage info: {e}")
        
        return storage_info
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
