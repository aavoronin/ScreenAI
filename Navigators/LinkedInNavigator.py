import os
import time
import re
import subprocess
import pyautogui
import pyperclip
from PIL import ImageGrab
from Screen.LinkedInScreenParser import LinkedInScreenParser
from Navigators.BaseNavigator import BaseNavigator
from Estimators.LinkedInVacancyEstimator import LinkedInVacancyEstimator
from cfg.cfg import Config


class LinkedInNavigator(BaseNavigator):
    def __init__(self, omniparser_repo_path: str = None):
        config = Config()
        if omniparser_repo_path is None:
            omniparser_repo_path = config.get_path('omniparser_repo_path')
        parser = LinkedInScreenParser(omniparser_repo_path)
        output_dir = config.get_path('output_dir')
        super().__init__(parser, output_dir)
        # Termination condition 1
        self.MAX_CLOSE_BUTTONS = 200
        self.MAX_CLOSE_BUTTONS_CLICKS = self.MAX_CLOSE_BUTTONS * 2
        self.MAX_SCROLL_DOWNS = 6
        self.VACANCIES_OUTPUT_PATH = config.get_path(
            'vacancies_linkedin_output_path'
        )
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

    def run_on_urls(self, urls_file_path: str = r"C:\Py\ScreenAI\Navigators\linkedin_urls.csv"):
        """
        Load URLs from a file, open each in Google Chrome, wait 30 seconds,
        and then run the LinkedIn automation logic.
        Stops after processing all URLs.
        """
        if not os.path.exists(urls_file_path):
            print(f"⚠️ URLs file not found: {urls_file_path}")
            return

        with open(urls_file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            print("⚠️ No URLs found in the file.")
            return

        print(f"🔍 Found {len(urls)} URLs to process.")

        for i, url in enumerate(urls):
            if len(url) < 20:
                continue
            print(f"🌐 [{i + 1}/{len(urls)}] Processing URL: {url}")

            # Execute Google Chrome with this URL
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                #r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ]
            chrome_executable = None
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_executable = path
                    break

            if chrome_executable:
                subprocess.Popen([chrome_executable, url])
            else:
                # Fallback to default browser on Windows
                os.startfile(url)

            # Wait 30 seconds
            print("⏳ Waiting 30 seconds for the page to load...")
            time.sleep(30)

            try:
                # Run the automation logic
                print("🤖 Starting LinkedIn automation logic for this URL...")
                self._execute_linkedin_automation()
            except Exception as e:
                continue

        print("✅ Finished processing all URLs.")

    def _execute_linkedin_automation(self):
        processed_urls = set()
        skipped_urls = list()
        MAX_SKIPPED_URLS = self.MAX_CLOSE_BUTTONS
        MAX_SKIPPED_URLS_IN_ROW = self.MAX_CLOSE_BUTTONS // 3 + 2
        skipped_urls_in_row = 0

        close_button_clicks = 0
        general_abort = False
        while not general_abort:
            # 1. Parse screen
            print("\nParsing screen...")
            for _ in range(10):
                try:
                    self.check_wait()
                    self.obtain_screen_size()
                    screenshot = ImageGrab.grab()
                    self.parser.parse_screen(screenshot)
                except Exception as e:
                    time.sleep(10)
                    continue
                break
            close_pairs = self.parser._close_pairs
            linkedin_buttons = self.parser._linkedin_buttons
            next_buttons = self.parser._next_buttons
            scroll_downs = self.parser._scroll_down_candidates

            # Termination Condition 1: MAX_CLOSE_BUTTONS unique URLs processed
            if len(processed_urls) >= self.MAX_CLOSE_BUTTONS:
                print(f" Reached MAX_CLOSE_BUTTONS ({self.MAX_CLOSE_BUTTONS} unique URLs). Terminating logic.")
                break

            if close_button_clicks >= self.MAX_CLOSE_BUTTONS_CLICKS:
                print(f" Reached MAX_CLOSE_BUTTONS_CLICKS ({self.MAX_CLOSE_BUTTONS_CLICKS} clicks). Terminating logic.")
                break

            found_new_url_in_pass = False
            # 2. Loop through close buttons
            print(f"🔄 Processing {len(close_pairs)} close buttons...")
            for pair in close_pairs:
                if len(processed_urls) >= self.MAX_CLOSE_BUTTONS:
                    break
                if close_button_clicks >= self.MAX_CLOSE_BUTTONS_CLICKS:
                    break
                print(pair)

                close_bbox = pair['close_button']['bbox']
                # Click left 10% of the close button
                dx = (close_bbox[2] - close_bbox[0]) * 4
                dy = (close_bbox[3] - close_bbox[1]) * 0.3
                self.click_area_near_bbox(close_bbox, dx= -dx, dy=-dy)
                close_button_clicks += 1
                # Wait 5 sec
                time.sleep(5)
                # Find first bbox in _linkedin_buttons
                #if linkedin_buttons:
                #first_linkedin_bbox = linkedin_buttons[0]['bbox']
                #self.click_bbox_center(first_linkedin_bbox)
                pyautogui.hotkey('ctrl', 'l')
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
                        skipped_urls_in_row = 0
                        print(f" ✅ New URL added. Total unique URLs: {len(processed_urls)}")
                    else:
                        skipped_urls_in_row += 1
                        skipped_urls.append(clipboard_text)
                        print(f" ⚠️ URL already processed. Skipping. "
                              f"({len(skipped_urls)} skipped, {skipped_urls_in_row} skipped in row)")
                        if (len(skipped_urls) > MAX_SKIPPED_URLS or
                                skipped_urls_in_row >= MAX_SKIPPED_URLS_IN_ROW):
                            print(f" We are waisting time. Aborting.")
                            general_abort = True
                        if skipped_urls_in_row > 30 and len(skipped_urls) > 30 and \
                                len(set(skipped_urls[:30])) < 8:
                            print(f" We are waisting time. No new recent urls. Aborting.")
                            general_abort = True
                        if skipped_urls_in_row > 15 and len(skipped_urls) > 15 and \
                                len(set(skipped_urls[:15])) < 4:
                            print(f" We are waisting time. No new recent urls. Aborting.")
                            general_abort = True
                else:
                    print(" ⚠️ Clipboard text is empty. Doing nothing.")
                # Continue loop to next close button
                continue

            if close_button_clicks >= self.MAX_CLOSE_BUTTONS_CLICKS or general_abort:
                print(f" Reached MAX_CLOSE_BUTTONS_CLICKS ({self.MAX_CLOSE_BUTTONS_CLICKS} clicks). Terminating logic.")
                break

            # Termination Condition 3: No new URLs found in this pass
            #if not found_new_url_in_pass and not next_buttons:
            #    print("🛑 No new URLs found in this pass. Terminating logic.")
            #    break

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
            self.VACANCIES_OUTPUT_PATH,
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
        self.estimator.estimate_vacancies()
