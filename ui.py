import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.logger import Logger

try:
    from nfc_handler import NFCHandler
    from p2p_manager import P2PManager  
    from file_manager import FileManager
    from utils import generate_session_id, format_file_size
    from android_utils import open_android_file_selector, request_file_permissions
    ANDROID_FILE_SELECTOR_AVAILABLE = True
    Logger.info("Android file selector modules loaded successfully")
except ImportError as e:
    Logger.warning(f"Could not import module: {e}")
    ANDROID_FILE_SELECTOR_AVAILABLE = False
    
    class NFCHandler:
        def __init__(self): 
            self.is_listening = False
        def get_status(self): 
            return "NFC not available"
        def start_listening(self, callback): 
            self.is_listening = True
        def stop_listening(self): 
            self.is_listening = False
        def is_nfc_available(self):
            return False
            
    class P2PManager:
        def __init__(self): pass
        def start_server(self): pass
        def stop_server(self): pass
        
    class FileManager:
        def __init__(self): pass
        def get_downloads_dir(self): return "/sdcard/Download"
        
    def generate_session_id(): return "test-session-123"
    def format_file_size(size): return f"{size} bytes"
    def open_android_file_selector(callback, allow_multiple=True): callback([])
    def request_file_permissions(callback): callback(True)


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_files = []
        self.permissions_granted = False
        self.build_ui()
        
        # Request permissions on startup if Android file selector is available
        if ANDROID_FILE_SELECTOR_AVAILABLE:
            self.request_permissions()
    
    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Title
        title = Label(
            text="JustTouch - NFC File Sharing",
            size_hint_y=None,
            height=60,
            font_size='20sp'
        )
        layout.add_widget(title)
        
        # File chooser section
        file_section = BoxLayout(orientation='vertical', size_hint_y=0.7, spacing=5)
        
        # File selector buttons
        if ANDROID_FILE_SELECTOR_AVAILABLE:
            selector_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
            
            android_btn = Button(
                text="📱 Select Files (Android)",
                on_release=self.open_android_selector
            )
            selector_layout.add_widget(android_btn)
            
            browse_btn = Button(
                text="📁 Browse Files",
                on_release=self.toggle_file_browser
            )
            selector_layout.add_widget(browse_btn)
            
            file_section.add_widget(selector_layout)
        
        # File chooser (initially hidden if Android selector is available)
        self.file_chooser = FileChooserListView(
            multiselect=True,
            opacity=0 if ANDROID_FILE_SELECTOR_AVAILABLE else 1,
            size_hint_y=0 if ANDROID_FILE_SELECTOR_AVAILABLE else None
        )
        file_section.add_widget(self.file_chooser)
        
        layout.add_widget(file_section)
        
        # Selected files info
        self.files_info = Label(
            text="No files selected",
            size_hint_y=None,
            height=40,
            text_size=(None, None)
        )
        layout.add_widget(self.files_info)
        
        # Action buttons
        button_layout = BoxLayout(size_hint_y=None, height=60, spacing=10)
        
        send_btn = Button(
            text="Send Files",
            on_release=self.prepare_send
        )
        button_layout.add_widget(send_btn)
        
        receive_btn = Button(
            text="Receive Files", 
            on_release=self.prepare_receive
        )
        button_layout.add_widget(receive_btn)
        
        layout.add_widget(button_layout)
        
        # Status area
        self.status_label = Label(
            text="Ready",
            size_hint_y=None,
            height=40
        )
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
        
        # Update file selection info
        self.file_chooser.bind(selection=self.on_file_selection)
    
    def on_file_selection(self, instance, selection):
        """Handle file selection from built-in file chooser"""
        self.selected_files = selection
        self.update_files_info()
    
    def prepare_send(self, instance):
        if not self.selected_files:
            # If no files selected, open Android file selector first
            if ANDROID_FILE_SELECTOR_AVAILABLE:
                self.status_label.text = "Requesting file access permissions..."
                self.open_android_selector_for_send()
            else:
                self.status_label.text = "Please select files to send"
            return
            
        self.manager.get_screen('nfc').setup_send_mode(self.selected_files)
        self.manager.current = 'nfc'
    
    def prepare_receive(self, instance):
        self.manager.get_screen('nfc').setup_receive_mode()
        self.manager.current = 'nfc'
    
    def request_permissions(self):
        """Request file access permissions"""
        def on_permissions_result(granted):
            self.permissions_granted = granted
            if granted:
                self.status_label.text = "Ready - Permissions granted"
            else:
                self.status_label.text = "File access permissions required"
        
        request_file_permissions(on_permissions_result)
    
    def open_android_selector(self, instance):
        """Open Android native file selector"""
        if not self.permissions_granted:
            self.status_label.text = "Requesting permissions..."
            self.request_permissions()
            return
        
        self.status_label.text = "Opening file selector..."
        
        def on_files_selected(files):
            self.selected_files = files
            self.update_files_info()
            if files:
                self.status_label.text = f"Selected {len(files)} files"
            else:
                self.status_label.text = "No files selected"
        
        open_android_file_selector(on_files_selected, allow_multiple=True)
    
    def open_android_selector_for_send(self):
        """Open Android native file selector specifically for sending files"""
        def on_permissions_result(granted):
            self.permissions_granted = granted
            if granted:
                self.status_label.text = "Permissions granted, opening file selector..."
                Clock.schedule_once(lambda dt: self._open_selector_for_send(), 0.5)
            else:
                self.status_label.text = "ERROR: File access permissions denied. Cannot select files."
        
        if not self.permissions_granted:
            self.status_label.text = "Requesting file access permissions..."
            request_file_permissions(on_permissions_result)
        else:
            self._open_selector_for_send()
    
    def _open_selector_for_send(self):
        """Internal method to open file selector after permissions are granted"""
        self.status_label.text = "Opening file selector..."
        
        def on_files_selected(files):
            self.selected_files = files
            self.update_files_info()
            if files:
                self.status_label.text = f"Selected {len(files)} files - Ready to send"
                # Automatically proceed to NFC screen after file selection
                Clock.schedule_once(lambda dt: self._proceed_to_nfc(), 1.0)
            else:
                self.status_label.text = "No files selected. Tap 'Send Files' to try again."
        
        try:
            open_android_file_selector(on_files_selected, allow_multiple=True)
        except Exception as e:
            Logger.error(f"Error opening file selector: {e}")
            self.status_label.text = f"Error opening file selector: {e}"
    
    def _proceed_to_nfc(self):
        """Proceed to NFC screen with selected files"""
        if self.selected_files:
            self.manager.get_screen('nfc').setup_send_mode(self.selected_files)
            self.manager.current = 'nfc'
    
    def toggle_file_browser(self, instance):
        """Toggle the built-in file browser visibility"""
        if self.file_chooser.opacity == 0:
            # Show file browser
            self.file_chooser.opacity = 1
            self.file_chooser.size_hint_y = None
            self.file_chooser.height = 300
            instance.text = "📱 Hide Browser"
        else:
            # Hide file browser
            self.file_chooser.opacity = 0
            self.file_chooser.size_hint_y = 0
            self.file_chooser.height = 0
            instance.text = "📁 Browse Files"
    
    def update_files_info(self):
        """Update the files info label"""
        if not self.selected_files:
            self.files_info.text = "No files selected"
        else:
            total_size = sum(os.path.getsize(f) for f in self.selected_files if os.path.exists(f))
            self.files_info.text = f"{len(self.selected_files)} files selected ({format_file_size(total_size)})"
    
class NFCScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.nfc_handler = NFCHandler()
        self.p2p_manager = P2PManager()
        self.file_manager = FileManager()
        self.is_sending = False
        self.files_to_send = []
        self.build_ui()
    
    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # Title
        self.title_label = Label(
            text="NFC Ready",
            size_hint_y=None,
            height=60,
            font_size='24sp'
        )
        layout.add_widget(self.title_label)
        
        # NFC status
        self.nfc_status = Label(
            text=self.nfc_handler.get_status(),
            size_hint_y=None,
            height=40,
            font_size='16sp'
        )
        layout.add_widget(self.nfc_status)
        
        # Instructions
        self.instructions = Label(
            text="Touch devices together to start sharing",
            size_hint_y=None,
            height=80,
            text_size=(None, None),
            halign='center'
        )
        layout.add_widget(self.instructions)
        
        # Progress bar (hidden initially)
        self.progress_bar = ProgressBar(
            size_hint_y=None,
            height=20,
            opacity=0
        )
        layout.add_widget(self.progress_bar)
        
        # Progress label
        self.progress_label = Label(
            text="",
            size_hint_y=None,
            height=40,
            opacity=0
        )
        layout.add_widget(self.progress_label)
        
        # Action buttons
        button_layout = BoxLayout(size_hint_y=None, height=60, spacing=10)
        
        self.action_btn = Button(
            text="Cancel",
            on_release=self.cancel_operation
        )
        button_layout.add_widget(self.action_btn)
        
        back_btn = Button(
            text="Back",
            on_release=self.go_back
        )
        button_layout.add_widget(back_btn)
        
        layout.add_widget(button_layout)
        
        self.add_widget(layout)
        
        # Update NFC status periodically
        Clock.schedule_interval(self.update_nfc_status, 2.0)
    
    def setup_send_mode(self, files):
        self.is_sending = True
        self.files_to_send = files
        self.title_label.text = f"Send {len(files)} Files"
        self.instructions.text = "Touch devices together to start sending"
        self.start_nfc_listening()
    
    def setup_receive_mode(self):
        self.is_sending = False
        self.files_to_send = []
        self.title_label.text = "Receive Files"
        self.instructions.text = "Touch devices together to start receiving"
        self.start_nfc_listening()
    
    def start_nfc_listening(self):
        self.nfc_handler.start_listening(self.on_nfc_data)
        self.action_btn.text = "Stop Listening"
    
    def on_nfc_data(self, data):
        Logger.info(f"NFC data received: {data}")
        
        try:
            import json
            nfc_data = json.loads(data)
            session_id = nfc_data.get('session_id')
            
            if self.is_sending:
                self.start_file_transfer(session_id)
            else:
                self.start_file_reception(session_id)
                
        except Exception as e:
            Logger.error(f"Error processing NFC data: {e}")
            self.instructions.text = f"Error: {e}"
    
    def start_file_transfer(self, session_id):
        self.instructions.text = "Starting file transfer..."
        self.show_progress()
        
        # In a real implementation, this would start the P2P transfer
        # For now, just simulate progress
        self.simulate_transfer_progress()
    
    def start_file_reception(self, session_id):
        self.instructions.text = "Starting file reception..."
        self.show_progress()
        
        # In a real implementation, this would start the P2P reception
        self.simulate_transfer_progress()
    
    def show_progress(self):
        self.progress_bar.opacity = 1
        self.progress_label.opacity = 1
        self.progress_bar.value = 0
        self.action_btn.text = "Cancel Transfer"
    
    def simulate_transfer_progress(self):
        def update_progress(dt):
            self.progress_bar.value += 2
            self.progress_label.text = f"Transfer progress: {int(self.progress_bar.value)}%"
            
            if self.progress_bar.value >= 100:
                self.transfer_complete()
                return False
            return True
        
        Clock.schedule_interval(update_progress, 0.1)
    
    def transfer_complete(self):
        self.progress_label.text = "Transfer complete!"
        self.instructions.text = "Files transferred successfully"
        self.action_btn.text = "Done"
        self.nfc_handler.stop_listening()
    
    def update_nfc_status(self, dt):
        self.nfc_status.text = self.nfc_handler.get_status()
    
    def cancel_operation(self, instance):
        self.nfc_handler.stop_listening()
        if self.action_btn.text == "Done":
            self.go_back(instance)
        else:
            self.instructions.text = "Operation cancelled"
            self.action_btn.text = "Back"
    
    def go_back(self, instance):
        self.nfc_handler.stop_listening()
        self.manager.current = 'main'
