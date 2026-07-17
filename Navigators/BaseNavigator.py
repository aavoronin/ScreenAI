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

    def click_area_near_bbox(self, bbox, dx, dy):
        cx, cy = self.get_pixel_center(bbox)
        # Shift by dx and dy ratios of screen dimensions, ensure x > 0
        click_x = max(1, int(cx + (dx * self.screen_width)))
        click_y = int(cy + (dy * self.screen_height))
        print(f"  🖱️ Clicking Close left partner at pixel coords: ({click_x}, {click_y})")
        pyautogui.click(click_x, click_y)

    def click_bbox_center(self, bbox):
        x, y = self.get_pixel_center(bbox)
        pyautogui.click(x, y)

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')