import os
import time
import re
import pyautogui
import pyperclip
from PIL import ImageGrab
from Screen.LinkedInScreenParser import LinkedInScreenParser
from Navigators.BaseNavigator import BaseNavigator
from Estimators.LinkedInVacancyEstimator import LinkedInVacancyEstimator


class LinkedInNavigator(BaseNavigator):
    def __init__(self, omniparser_repo_path: str):
        parser = LinkedInScreenParser(omniparser_repo_path)
        output_dir = r"C:\Py\ScreenAI\parsed screens"
        super().__init__(parser, output_dir)

        # Termination condition 1
        self.MAX_CLOSE_BUTTONS = 6
        self.MAX_SCROLL_DOWNS = 6
        self.VACANCIES_LINKED_IN_OUTPUT_PATH = r'C:\Py\ScreenAI\out\LinkedIn\Vacancies'

        # Estimator responsible for parsing saved MHTML files
        self.estimator = LinkedInVacancyEstimator()

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

        while True:
            # 1. Parse screen
            print("\nParsing screen...")
            screenshot = ImageGrab.grab()
            self.parser.parse_screen(screenshot)
            close_pairs = self.parser._close_pairs
            linkedin_buttons = self.parser._linkedin_buttons
            next_buttons = self.parser._next_buttons
            scroll_downs = self.parser._scroll_down_candidates

            # Termination Condition 1: MAX_CLOSE_BUTTONS unique URLs processed
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
                self.click_area_near_bbox(close_bbox, dx=-0.1, dy=0.0)

                # Wait 5 sec
                time.sleep(5)

                # Find first bbox in _linkedin_buttons
                if linkedin_buttons:
                    first_linkedin_bbox = linkedin_buttons[0]['bbox']
                    self.click_bbox_center(first_linkedin_bbox)

                    # Wait for Chrome to gain focus
                    time.sleep(0.5)

                    # Send Ctrl+C
                    pyautogui.hotkey('ctrl', 'c')
                    time.sleep(0.5)  # Wait for clipboard to update

                    # Take text from clipboard
                    clipboard_text = pyperclip.paste().strip()
                    print(f" 📋 Clipboard text: '{clipboard_text}'")

                    if clipboard_text:
                        if clipboard_text not in processed_urls:
                            processed_urls.add(clipboard_text)
                            self.process_vacancy(clipboard_text)
                            found_new_url_in_pass = True
                            print(f" ✅ New URL added. Total unique URLs: {len(processed_urls)}")
                        else:
                            print(f" ⚠️ URL already processed. Skipping.")
                    else:
                        print(" ⚠️ Clipboard text is empty. Doing nothing.")
                else:
                    print(" ⚠️ No LinkedIn buttons detected. Skipping clipboard logic.")

                # Continue loop to next close button
                continue

            # Termination Condition 3: No new URLs found in this pass
            if not found_new_url_in_pass and not next_buttons:
                print("🛑 No new URLs found in this pass. Terminating logic.")
                break

            # 3. Check Next button or Scroll Down button
            if next_buttons:
                print("➡️ Next button detected. Clicking and waiting 20s...")
                self.click_bbox_center(next_buttons[0]['bbox'])
                time.sleep(20)
                # Loop continues, which will parse screen again
            elif scroll_downs:
                print(f"️ Scroll down (triangle_down) detected. Clicking {self.MAX_SCROLL_DOWNS} times...")
                for _ in range(self.MAX_SCROLL_DOWNS):
                    self.click_bbox_center(scroll_downs[0]['bbox'])
                    time.sleep(0.3)  # small pause between clicks
                # Loop continues, which will parse screen again
            else:
                # Termination Condition 2: Neither Next nor triangle_down found
                print(" No Next button and no Scroll Down button found. Terminating logic.")
                break

    def process_vacancy(self, url: str):
        """
        Process the vacancy URL: extract job ID, save the current
        browser page as MHTML, then hand it over to the estimator
        for parsing / scoring.
        """
        # 1. Parse URL and extract job_id
        match = re.search(r'currentJobId=(\d+)', url)
        if not match:
            print(f"⚠️ Could not extract currentJobId from URL: {url}")
            return

        job_id = match.group(1)

        # 2. Create destination file path
        dest_file = os.path.join(
            self.VACANCIES_LINKED_IN_OUTPUT_PATH,
            f'LinkedIn_Vacancy_{job_id}.mhtml'
        )

        # 3. Make folders if they do not exist
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)

        # 4. Check if file already exists.
        if os.path.exists(dest_file):
            print(f"✅ MHTML file already exists: {dest_file}")
        else:
            # Delegate the actual Ctrl+S / typing / Enter to the base class
            self.save_browser_page_as_mhtml(dest_file)

        # 5. Let the estimator handle parsing / config / scoring
        self.estimator.estimate(dest_file)

    def analyze_collected(self):
        pass