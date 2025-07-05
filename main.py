from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.logger import Logger

from ui import MainScreen, NFCScreen


class JustTouchApp(App):
    def build(self):
        # Create screen manager
        sm = ScreenManager()
        
        # Add screens
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(NFCScreen(name='nfc'))
        
        return sm
    
    def on_start(self):
        Logger.info("JustTouch app started")
    
    def on_stop(self):
        Logger.info("JustTouch app stopped")


if __name__ == '__main__':
    JustTouchApp().run()
