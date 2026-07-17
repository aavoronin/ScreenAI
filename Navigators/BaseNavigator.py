import os
import ctypes
import pyautogui

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

    def click_close_left_partner(self, close_bbox):
        cx, cy = self.get_pixel_center(close_bbox)
        # Move left 10% of screen width, ensure x > 0
        click_x = max(1, int(cx - (self.screen_width * 0.10)))
        click_y = cy
        print(f"  🖱️ Clicking Close left partner at pixel coords: ({click_x}, {click_y})")
        pyautogui.click(click_x, click_y)

    def click_bbox_center(self, bbox):
        x, y = self.get_pixel_center(bbox)
        pyautogui.click(x, y)

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')