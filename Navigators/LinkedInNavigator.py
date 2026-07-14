import os
import time
import datetime
import ctypes
import pyautogui
from PIL import ImageGrab
from Screen.LinkedInScreenParser import LinkedInScreenParser


class LinkedInNavigator:
    def __init__(self, omniparser_repo_path: str):
        self.parser = LinkedInScreenParser(omniparser_repo_path)
        self.output_dir = r"C:\Py\ScreenAI\parsed screens"
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        print("Waiting for NumLock to be ON...")
        while True:
            while not self._is_numlock_on():
                time.sleep(0.5)

            print("NumLock is ON. Taking screenshot...")
            screenshot = ImageGrab.grab()

            self.parser.parse_screen(screenshot)

            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = os.path.join(self.output_dir, f"LinkedIn_{timestamp}.png")

            self.parser.draw_and_save_parsed_image(filename)
            print(f"Saved parsed image to: {filename}")

            self._toggle_numlock()
            print("NumLock toggled OFF. Waiting for next activation...")

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')