import json
import threading
import time
from kivy.logger import Logger

try:
    from jnius import autoclass, PythonJavaClass, java_method
    from android.permissions import request_permissions, Permission

    # Android NFC classes
    NfcAdapter = autoclass('android.nfc.NfcAdapter')
    NdefMessage = autoclass('android.nfc.NdefMessage')
    NdefRecord = autoclass('android.nfc.NdefRecord')
    Intent = autoclass('android.content.Intent')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    ANDROID_AVAILABLE = True
except ImportError:
    ANDROID_AVAILABLE = False
    Logger.warning("Android/Pyjnius not available")
    
    class PythonJavaClass:
        pass
    
    def java_method(signature):
        def decorator(func):
            return func
        return decorator


class NFCCallbackInterface(PythonJavaClass):
    __javainterfaces__ = ['android/nfc/NfcAdapter$ReaderCallback']
    
    def __init__(self, python_callback):
        super().__init__()
        self.python_callback = python_callback
    
    @java_method('(Landroid/nfc/Tag;)V')
    def onTagDiscovered(self, tag):
        try:
            ndef_data = self.extract_ndef_data(tag)
            if ndef_data and self.python_callback:
                self.python_callback(ndef_data)
        except Exception as e:
            Logger.error(f"NFC tag discovery error: {e}")
    
    def extract_ndef_data(self, tag):
        try:
            Ndef = autoclass('android.nfc.tech.Ndef')
            ndef = Ndef.get(tag)
            
            if ndef is None:
                return None
            
            ndef.connect()
            ndef_message = ndef.getNdefMessage()
            
            if ndef_message is None:
                ndef.close()
                return None
            
            records = ndef_message.getRecords()
            if len(records) > 0:
                payload = records[0].getPayload()
                payload_str = ''.join(chr(b & 0xFF) for b in payload)
                ndef.close()
                return payload_str
            
            ndef.close()
            return None
            
        except Exception as e:
            Logger.error(f"Error extracting NDEF data: {e}")
            return None


class NFCHandler:
    def __init__(self):
        self.nfc_adapter = None
        self.is_listening = False
        self.is_broadcasting = False
        self.callback_interface = None
        self.broadcast_data = None
        self.listen_callback = None
        
        self.initialize_nfc()
    
    def initialize_nfc(self):
        if not ANDROID_AVAILABLE:
            Logger.info("NFC: Android not available")
            return
            
        try:
            request_permissions([Permission.NFC])
            
            activity = PythonActivity.mActivity
            self.nfc_adapter = NfcAdapter.getDefaultAdapter(activity)
            
            if self.nfc_adapter is None:
                Logger.warning("NFC: No NFC adapter found")
                return
            
            if not self.nfc_adapter.isEnabled():
                Logger.warning("NFC: NFC is disabled")
                return
            
            Logger.info("NFC: Adapter initialized successfully")
            
        except Exception as e:
            Logger.error(f"NFC initialization error: {e}")
    
    def start_listening(self, callback):
        if not ANDROID_AVAILABLE:
            return
            
        if self.nfc_adapter is None:
            Logger.warning("NFC: Cannot start listening - adapter not available")
            return
        
        try:
            self.listen_callback = callback
            self.callback_interface = NFCCallbackInterface(self._handle_nfc_data)
            
            activity = PythonActivity.mActivity
            flags = (NfcAdapter.FLAG_READER_NFC_A | 
                    NfcAdapter.FLAG_READER_NFC_B | 
                    NfcAdapter.FLAG_READER_NFC_F | 
                    NfcAdapter.FLAG_READER_NFC_V)
            
            self.nfc_adapter.enableReaderMode(
                activity,
                self.callback_interface,
                flags,
                None
            )
            
            self.is_listening = True
            Logger.info("NFC: Started listening for tags")
            
        except Exception as e:
            Logger.error(f"NFC listening error: {e}")
    
    def stop_listening(self):
        if not ANDROID_AVAILABLE:
            self.is_listening = False
            return
            
        if self.nfc_adapter is None:
            return
        
        try:
            activity = PythonActivity.mActivity
            self.nfc_adapter.disableReaderMode(activity)
            self.is_listening = False
            Logger.info("NFC: Stopped listening for tags")
            
        except Exception as e:
            Logger.error(f"NFC stop listening error: {e}")
    
    def start_broadcasting(self, data):
        if not ANDROID_AVAILABLE:
            return
            
        if self.nfc_adapter is None:
            Logger.warning("NFC: Cannot start broadcasting - adapter not available")
            return
        
        try:
            self.broadcast_data = data
            
            payload = data.encode('utf-8')
            ndef_record = NdefRecord.createTextRecord('en', data)
            ndef_message = NdefMessage([ndef_record])
            
            activity = PythonActivity.mActivity
            intent = Intent(activity, activity.getClass())
            intent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
            
            self.nfc_adapter.setNdefPushMessage(ndef_message, activity)
            
            self.is_broadcasting = True
            Logger.info("NFC: Started broadcasting data")
            
        except Exception as e:
            Logger.error(f"NFC broadcasting error: {e}")
    
    def stop_broadcasting(self):
        if not ANDROID_AVAILABLE:
            self.is_broadcasting = False
            return
            
        if self.nfc_adapter is None:
            return
        
        try:
            activity = PythonActivity.mActivity
            self.nfc_adapter.setNdefPushMessage(None, activity)
            self.is_broadcasting = False
            Logger.info("NFC: Stopped broadcasting data")
            
        except Exception as e:
            Logger.error(f"NFC stop broadcasting error: {e}")
    
    def _handle_nfc_data(self, data):
        if self.listen_callback:
            self.listen_callback(data)
    
    def is_nfc_available(self):
        if not ANDROID_AVAILABLE:
            return False
            
        return (self.nfc_adapter is not None and 
                self.nfc_adapter.isEnabled())
    
    def get_status(self):
        if not ANDROID_AVAILABLE:
            return "NFC not available"
            
        if self.nfc_adapter is None:
            return "NFC not available"
        
        if not self.nfc_adapter.isEnabled():
            return "NFC disabled"
        
        status = []
        if self.is_listening:
            status.append("listening")
        if self.is_broadcasting:
            status.append("broadcasting")
        
        if status:
            return f"NFC active ({', '.join(status)})"
        else:
            return "NFC ready"
