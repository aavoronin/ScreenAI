import os
import time
import re
import subprocess
import pyautogui
import pyperclip
from PIL import ImageGrab
from Screen.HirifyMeScreenParser import HirifyMeScreenParser
from Navigators.BaseNavigator import BaseNavigator
from cfg.cfg import Config


class HirifyMeNavigator(BaseNavigator):
    def __init__(self, omniparser_repo_path: str = None):
        config = Config()
        if omniparser_repo_path is None:
            omniparser_repo_path = config.get_path('omniparser_repo_path')
        parser = HirifyMeScreenParser(omniparser_repo_path)
        output_dir = config.get_path('output_dir')
        super().__init__(parser, output_dir)

        # Termination conditions
        self.MAX_VACANCIES_PER_URL = 40
        self.MAX_SCROLL_DOWNS = 10
        self.HIRIFY_URLS_FILE_PATH = r"C:\Py\ScreenAI\Navigators\hirify_urls.csv"

    def run_on_urls(self):
        """
        Load URLs from hirify_urls.csv file, open each in Google Chrome,
        wait for page to load, and then run the Hirify automation logic.
        Stops after processing all URLs.
        """
        if not os.path.exists(self.HIRIFY_URLS_FILE_PATH):
            print(f"⚠️ URLs file not found: {self.HIRIFY_URLS_FILE_PATH}")
            return

        with open(self.HIRIFY_URLS_FILE_PATH, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            print("⚠️ No URLs found in the file.")
            return

        print(f"🔍 Found {len(urls)} URLs to process.")

        for i, url in enumerate(urls):
            print(f"\n🌐 [{i + 1}/{len(urls)}] Processing URL: {url}")

            # Execute Google Chrome with this URL
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
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

            # Wait for page to load
            print("⏳ Waiting 30 seconds for the page to load...")
            time.sleep(30)

            # Run the automation logic
            print("🤖 Starting Hirify automation logic for this URL...")
            self._execute_hirify_automation()

            print(f"✅ Finished processing URL: {url}")

        print("\n✅ Finished processing all URLs.")

    def _execute_hirify_automation(self):
        """
        Main automation loop for Hirify:
        1. Parse screen
        2. Find and process "more options" buttons for vacancies
        3. Scroll down using triangle_down
        4. Navigate to next page
        5. Repeat until vacancy limit reached
        """
        vacancies_processed_on_this_url = 0

        while vacancies_processed_on_this_url < self.MAX_VACANCIES_PER_URL:
            # 1. Parse screen
            print("\n Parsing screen...")
            screenshot = ImageGrab.grab()
            self.parser.parse_screen(screenshot)

            more_options_buttons = self.parser._more_options_buttons
            triangle_downs = self.parser._triangle_down_candidates
            next_buttons = self.parser._next_buttons

            # 2. Process "more options" buttons (vacancies)
            if more_options_buttons:
                print(f"🔄 Processing {len(more_options_buttons)} 'more options' buttons...")

                for more_btn in more_options_buttons:
                    if vacancies_processed_on_this_url >= self.MAX_VACANCIES_PER_URL:
                        print(f"Reached MAX_VACANCIES_PER_URL ({self.MAX_VACANCIES_PER_URL}). Stopping.")
                        return

                    print(f"\n  Processing vacancy {vacancies_processed_on_this_url + 1}/{self.MAX_VACANCIES_PER_URL}")
                    print(f"  More options button bbox: {more_btn.get('bbox')}")

                    # Call stub method for processing vacancy
                    self._process_vacancy_stub(more_btn)

                    vacancies_processed_on_this_url += 1

                    # Small delay between processing vacancies
                    time.sleep(1)

                # After processing all vacancies on current screen, scroll down
                print("\n📜 Finished processing vacancies on current screen")

            # 3. Check for triangle_down button to scroll
            if triangle_downs:
                print(f"️ Triangle down detected. Clicking {self.MAX_SCROLL_DOWNS} times...")
                for _ in range(self.MAX_SCROLL_DOWNS):
                    self.click_bbox_center(triangle_downs[0]['bbox'])
                    time.sleep(0.5)  # Small pause between clicks

            # 4. Check for next button to navigate to next page
            if next_buttons:
                print("➡️ Next button detected. Clicking and waiting 20s...")
                self.click_bbox_center(next_buttons[0]['bbox'])
                time.sleep(20)  # Wait for next page to load
                # Loop continues to parse new page
            else:
                # No next button and no triangle_down - end of results
                if not triangle_downs:
                    print("🛑 No Next button and no Scroll Down button found. End of results for this URL.")
                    break

        print(f"\n✅ Reached MAX_VACANCIES_PER_URL ({self.MAX_VACANCIES_PER_URL}) for this URL.")

    def _process_vacancy_stub(self, more_button: dict):
        """
        Stub method for processing a vacancy.
        In the next step, this will:
        - Click the more options button
        - Extract vacancy URL
        - Save vacancy as MHTML
        - Save URL to file
        For now, just print information.
        """
        print(f"    📋 STUB: Processing vacancy")
        print(f"    Content: {more_button.get('content', 'N/A')}")
        print(f"    Type: {more_button.get('type', 'N/A')}")
        print(f"    BBox: {more_button.get('bbox')}")
        # TODO: Implement actual vacancy processing in next step
        # - Click more options
        # - Extract URL
        # - Save MHTML
        # - Save URL