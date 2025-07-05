from kivy.logger import Logger
from typing import Callable, List, Optional

try:
    from android.permissions import request_permissions, Permission
    from jnius import autoclass, cast
    from android import activity, mActivity
    ANDROID_AVAILABLE = True
except ImportError:
    ANDROID_AVAILABLE = False
    Logger.warning("Android modules not available")


class AndroidFileSelector:  # Handle Android file selection using native file picker    
    def __init__(self):
        self.callback = None
        self.activity = None
        self.intent_chooser = None
        
        if ANDROID_AVAILABLE:
            self._setup_android()
    
    def _setup_android(self):  # Setup Android activity and intent handling
        try:
            # Get Android classes
            self.Intent = autoclass('android.content.Intent')
            self.Uri = autoclass('android.net.Uri')
            self.DocumentsContract = autoclass('android.provider.DocumentsContract')
            
            # Get the current activity
            self.activity = mActivity
            
            # Bind to activity result
            activity.bind(on_activity_result=self._on_activity_result)
            
        except Exception as e:
            Logger.error(f"Error setting up Android file selector: {e}")
    
    def request_permissions(self, callback: Callable[[bool], None]):  # Request necessary permissions for file access
        if not ANDROID_AVAILABLE:
            Logger.info("Not on Android, skipping permission request")
            callback(True)
            return
        
        try:
            Logger.info("Starting permission request process")
            
            # Check Android version
            Build = autoclass('android.os.Build')
            sdk_version = Build.VERSION.SDK_INT
            Logger.info(f"Android SDK version: {sdk_version}")
            
            permissions = []
            
            if sdk_version >= 33:  # Android 13+ (API 33+)
                # Use new media permissions for Android 13+
                Logger.info("Using Android 13+ media permissions")
                permissions.extend([
                    Permission.READ_MEDIA_IMAGES,
                    Permission.READ_MEDIA_VIDEO,
                    Permission.READ_MEDIA_AUDIO,
                ])
            else:
                # Use legacy storage permissions for older versions
                Logger.info("Using legacy storage permissions")
                permissions.extend([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ])
            
            # For Android 11+ (API 30+), MANAGE_EXTERNAL_STORAGE requires special handling
            if sdk_version >= 30:
                # Check if we need to request MANAGE_EXTERNAL_STORAGE
                try:
                    Environment = autoclass('android.os.Environment')
                    if not Environment.isExternalStorageManager():
                        Logger.info("MANAGE_EXTERNAL_STORAGE permission needed")
                        # This permission requires special intent handling
                        self._request_manage_external_storage(callback)
                        return
                    else:
                        Logger.info("MANAGE_EXTERNAL_STORAGE already granted")
                except Exception as e:
                    Logger.warning(f"Could not check MANAGE_EXTERNAL_STORAGE: {e}")
            
            def permission_callback(permissions_result, grant_results):
                granted = all(grant_results) if grant_results else False
                Logger.info(f"Permission request result: {permissions_result}")
                Logger.info(f"Grant results: {grant_results}")
                Logger.info(f"All permissions granted: {granted}")
                callback(granted)
            
            if permissions:
                Logger.info(f"Requesting permissions: {permissions}")
                request_permissions(permissions, permission_callback)
            else:
                # No permissions needed or already granted
                Logger.info("No additional permissions needed")
                callback(True)
            
        except Exception as e:
            Logger.error(f"Error requesting permissions: {e}")
            callback(False)
    
    def _request_manage_external_storage(self, callback: Callable[[bool], None]):   # Request MANAGE_EXTERNAL_STORAGE permission on Android 11+
        try:
            Settings = autoclass('android.provider.Settings')
            intent = self.Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            
            # Add the app's URI
            Uri = autoclass('android.net.Uri')
            package_name = self.activity.getPackageName()
            uri = Uri.parse(f"package:{package_name}")
            intent.setData(uri)
            
            # Start the settings activity
            self.activity.startActivity(intent)
            
            callback(True)
            
        except Exception as e:
            Logger.error(f"Error requesting MANAGE_EXTERNAL_STORAGE: {e}")
            callback(False)
    
    def open_file_selector(self, callback: Callable[[List[str]], None], allow_multiple: bool = True):
        """Open Android file selector"""
        if not ANDROID_AVAILABLE:
            Logger.warning("Android file selector not available")
            callback([])
            return
        
        self.callback = callback
        
        try:
            Logger.info(f"Opening Android file selector (multiple: {allow_multiple})")
            
            # Create intent for file selection
            intent = self.Intent(self.Intent.ACTION_GET_CONTENT)
            intent.setType("*/*")  # Allow all file types
            
            if allow_multiple:
                intent.putExtra(self.Intent.EXTRA_ALLOW_MULTIPLE, True)
            
            # Add categories
            intent.addCategory(self.Intent.CATEGORY_OPENABLE)
            
            # Create chooser
            chooser = self.Intent.createChooser(intent, "Select Files")
            
            # Start the activity
            Logger.info("Starting file selector activity")
            self.activity.startActivityForResult(chooser, 1001)
            
        except Exception as e:
            Logger.error(f"Error opening file selector: {e}")
            callback([])
    
    def _on_activity_result(self, request_code, result_code, intent):  # Handle file selection result
        if request_code != 1001 or not self.callback:
            return
        
        RESULT_OK = -1  # Activity.RESULT_OK
        
        if result_code != RESULT_OK:
            Logger.info("File selection cancelled")
            self.callback([])
            return
        
        try:
            selected_files = []
            
            if intent.getClipData() is not None:
                # Multiple files selected
                clip_data = intent.getClipData()
                for i in range(clip_data.getItemCount()):
                    uri = clip_data.getItemAt(i).getUri()
                    file_path = self._get_file_path_from_uri(uri)
                    if file_path:
                        selected_files.append(file_path)
            else:
                # Single file selected
                uri = intent.getData()
                if uri:
                    file_path = self._get_file_path_from_uri(uri)
                    if file_path:
                        selected_files.append(file_path)
            
            Logger.info(f"Selected {len(selected_files)} files")
            self.callback(selected_files)
            
        except Exception as e:
            Logger.error(f"Error processing file selection result: {e}")
            self.callback([])
    
    def _get_file_path_from_uri(self, uri) -> Optional[str]:     # Convert Android URI to file path
        try:
            # Try to get real path from URI
            ContentResolver = autoclass('android.content.ContentResolver')
            cursor = None
            
            # For document URIs, try to get the actual file path
            if self.DocumentsContract.isDocumentUri(self.activity, uri):
                # Handle different document providers
                uri_str = str(uri)
                
                if "primary:" in uri_str:
                    # Primary external storage
                    path = uri_str.split("primary:")[1]
                    external_storage = autoclass('android.os.Environment').getExternalStorageDirectory()
                    return f"{external_storage}/{path}"
                
                elif "downloads:" in uri_str:
                    # Downloads folder
                    downloads = autoclass('android.os.Environment').getExternalStoragePublicDirectory(
                        autoclass('android.os.Environment').DIRECTORY_DOWNLOADS
                    )
                    return f"{downloads}/{uri_str.split('downloads:')[1]}"
            
            # Fallback: use content resolver to copy file to cache
            return self._copy_uri_to_cache(uri)
            
        except Exception as e:
            Logger.error(f"Error getting file path from URI {uri}: {e}")
            return None
    
    def _copy_uri_to_cache(self, uri) -> Optional[str]:  #  Copy URI content to cache directory and return path
        try:
            # Get cache directory
            cache_dir = self.activity.getCacheDir()
            
            # Generate filename from URI
            import time
            timestamp = int(time.time())
            filename = f"selected_file_{timestamp}"
            
            # Try to get original filename
            ContentResolver = autoclass('android.content.ContentResolver')
            cursor = self.activity.getContentResolver().query(uri, None, None, None, None)
            
            if cursor and cursor.moveToFirst():
                try:
                    name_index = cursor.getColumnIndex("_display_name")
                    if name_index >= 0:
                        original_name = cursor.getString(name_index)
                        if original_name:
                            filename = original_name
                except:
                    pass
                finally:
                    cursor.close()
            
            # Copy file to cache
            cache_file = f"{cache_dir}/{filename}"
            
            input_stream = self.activity.getContentResolver().openInputStream(uri)
            FileOutputStream = autoclass('java.io.FileOutputStream')
            output_stream = FileOutputStream(cache_file)
            
            # Copy data
            buffer_size = 1024
            buffer = [0] * buffer_size
            
            while True:
                bytes_read = input_stream.read(buffer)
                if bytes_read == -1:
                    break
                output_stream.write(buffer, 0, bytes_read)
            
            input_stream.close()
            output_stream.close()
            
            Logger.info(f"Copied file to cache: {cache_file}")
            return cache_file
            
        except Exception as e:
            Logger.error(f"Error copying URI to cache: {e}")
            return None


# Global instance
android_file_selector = AndroidFileSelector()


def request_file_permissions(callback: Callable[[bool], None]):  #  Request file access permissions
    android_file_selector.request_permissions(callback)


def open_android_file_selector(callback: Callable[[List[str]], None], allow_multiple: bool = True):   # Open Android native file selector
    android_file_selector.open_file_selector(callback, allow_multiple)
