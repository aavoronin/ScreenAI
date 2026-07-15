import os
import time
import datetime
import ctypes
import pyautogui
import pyperclip
from PIL import ImageGrab
from Screen.LinkedInScreenParser import LinkedInScreenParser


class LinkedInNavigator:
    def __init__(self, omniparser_repo_path: str):
        self.parser = LinkedInScreenParser(omniparser_repo_path)
        self.output_dir = r"C:\Py\ScreenAI\parsed screens"
        os.makedirs(self.output_dir, exist_ok=True)

        # Termination condition 1
        self.MAX_CLOSE_BUTTONS = 30
        self.MAX_SCROLL_DOWNS = 6

    def run(self):
        print("Waiting for NumLock to be ON...")
        while True:
            # Wait for NumLock to be activated
            while not self._is_numlock_on():
                time.sleep(0.5)

            print("NumLock is ON. Starting LinkedIn automation logic...")
            self._execute_linkedin_automation()

            # Turn off NumLock and wait for next activation
            self._toggle_numlock()
            print("NumLock toggled OFF. Waiting for next activation...")

    def _execute_linkedin_automation(self):
        processed_urls = set()
        screen_width, screen_height = pyautogui.size()

        def get_pixel_center(bbox):
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            return int(cx * screen_width), int(cy * screen_height)

        def click_close_left_partner(close_bbox):
            cx, cy = get_pixel_center(close_bbox)
            # Move left 10% of screen width, ensure x > 0
            click_x = max(1, int(cx - (screen_width * 0.10)))
            click_y = cy
            print(f"  🖱️ Clicking Close left partner at pixel coords: ({click_x}, {click_y})")
            pyautogui.click(click_x, click_y)

        def click_bbox_center(bbox):
            x, y = get_pixel_center(bbox)
            pyautogui.click(x, y)

        while True:
            # 1. Parse screen
            print("\n📸 Parsing screen...")
            screenshot = ImageGrab.grab()
            self.parser.parse_screen(screenshot)

            close_pairs = self.parser._close_pairs
            linkedin_buttons = self.parser._linkedin_buttons
            next_buttons = self.parser._next_buttons
            scroll_downs = self.parser._scroll_down_candidates

            # Termination Condition 1: 50 unique URLs processed
            if len(processed_urls) >= self.MAX_CLOSE_BUTTONS:
                print(f" Reached MAX_CLOSE_BUTTONS ({self.MAX_CLOSE_BUTTONS} unique URLs). Terminating logic.")
                break

            found_new_url_in_pass = False

            # 2. Loop through close buttons
            print(f"🔄 Processing {len(close_pairs)} close buttons...")
            for pair in close_pairs:
                if len(processed_urls) >= self.MAX_CLOSE_BUTTONS:
                    break

                print(pair)
                close_bbox = pair['close_button']['bbox']

                # Click left 10% of the close button
                click_close_left_partner(close_bbox)

                # Wait 5 sec
                time.sleep(5)

                # Find first bbox in _linkedin_buttons
                if linkedin_buttons:
                    first_linkedin_bbox = linkedin_buttons[0]['bbox']
                    click_bbox_center(first_linkedin_bbox)

                    # Wait for Chrome to gain focus
                    time.sleep(0.5)

                    # Optional: If you need the URL from the address bar, click it first
                    # pyautogui.click(x=960, y=50) # Example coordinate for Chrome address bar
                    # time.sleep(0.2)
                    # pyautogui.hotkey('ctrl', 'a') # Select all text in address bar
                    # time.sleep(0.2)

                    # Send Ctrl+C
                    pyautogui.hotkey('ctrl', 'c')
                    time.sleep(0.5)  # Wait for clipboard to update

                    # Take text from clipboard
                    clipboard_text = pyperclip.paste().strip()
                    print(f"   Clipboard text: '{clipboard_text}'")

                    if clipboard_text:
                        if clipboard_text not in processed_urls:
                            processed_urls.add(clipboard_text)
                            self.process_vacancy(clipboard_text)
                            found_new_url_in_pass = True
                            print(f"  ✅ New URL added. Total unique URLs: {len(processed_urls)}")
                        else:
                            print(f"  ️ URL already processed. Skipping.")
                            # Continue loop to next close button
                            continue
                    else:
                        print("  ⚠️ Clipboard text is empty. Doing nothing.")
                else:
                    print("  ⚠️ No LinkedIn buttons detected. Skipping clipboard logic.")

            # Termination Condition 3: No new URLs found in this pass
            if not found_new_url_in_pass and not next_buttons:
                print("🛑 No new URLs found in this pass. Terminating logic.")
                break

            # 3. Check Next button or Scroll Down button
            if next_buttons:
                print("➡️ Next button detected. Clicking and waiting 10s...")
                click_bbox_center(next_buttons[0]['bbox'])
                time.sleep(20)
                # Loop continues, which will parse screen again
            elif scroll_downs:
                print("⬇️ Scroll down (triangle_down) detected. Clicking 10 times...")

                for _ in range(self.MAX_SCROLL_DOWNS):
                    click_bbox_center(scroll_downs[0]['bbox'])
                    time.sleep(0.3)  # small pause between clicks
                # Loop continues, which will parse screen again
            else:
                # Termination Condition 2: Neither Next nor triangle_down found
                print(" No Next button and no Scroll Down button found. Terminating logic.")
                break

    def process_vacancy(self, url: str):
        """
        Process the vacancy URL. Currently empty as requested.
        """
        pass

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')