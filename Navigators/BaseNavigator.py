import os
import ctypes
import time
import pyautogui
import pyperclip

class BaseNavigator:
    def __init__(self, parser, output_dir: str):
        self.parser = parser
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.screen_width, self.screen_height = pyautogui.size()

    def get_pixel_center(self, bbox):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        return int(cx * self.screen_width), int(cy * self.screen_height)

    def click_area_near_bbox(self, bbox, dx, dy):
        cx, cy = self.get_pixel_center(bbox)
        # Shift by dx and dy ratios of screen dimensions, ensure x > 0
        click_x = max(1, int(cx + (dx * self.screen_width)))
        click_y = int(cy + (dy * self.screen_height))
        print(f"  🖱️ Clicking at pixel coords: ({click_x}, {click_y})")
        pyautogui.click(click_x, click_y)

    def click_bbox_center(self, bbox):
        x, y = self.get_pixel_center(bbox)
        pyautogui.click(x, y)

    def save_browser_page_as_mhtml(self, dest_file):
        """
        Save the current browser page as MHTML to the specified file.
        Presses Ctrl+S, enters the filename via clipboard, and confirms.
        Does not know anything about the page content or source.
        """
        print(f"💾 Saving browser page to: {dest_file}")
        # 1. Click ctrl-s
        pyautogui.hotkey('ctrl', 's')
        # 2. Wait for Save dialog to appear
        time.sleep(10)
        # 3. Type full file name (clipboard + ctrl+v is much more reliable)
        pyperclip.copy(dest_file)
        pyautogui.hotkey('ctrl', 'v')
        # 4. Click enter
        pyautogui.press('enter')
        # 5. Wait for the file to finish saving
        time.sleep(10)
        print(f"✅ Successfully saved MHTML: {dest_file}")

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')