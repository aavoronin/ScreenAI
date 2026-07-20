import os
import time
import re
import subprocess
import pyautogui
import pyperclip
from PIL import ImageGrab
from Screen.HirifyScreenParser import HirifyScreenParser
from Navigators.BaseNavigator import BaseNavigator
from Estimators.HirifyVacancyEstimator import HirifyVacancyEstimator
from cfg.cfg import Config


class HirifyNavigator(BaseNavigator):
    def __init__(self, omniparser_repo_path: str = None):
        config = Config()
        if omniparser_repo_path is None:
            omniparser_repo_path = config.get_path('omniparser_repo_path')
        parser = HirifyScreenParser(omniparser_repo_path)
        output_dir = config.get_path('output_dir')
        super().__init__(parser, output_dir)

        # Termination conditions
        self.MAX_VACANCIES_PER_URL = 50
        self.MAX_SCROLL_DOWNS = 10
        self.HIRIFY_URLS_FILE_PATH = r"C:\Py\ScreenAI\Navigators\hirify_urls.csv"
        self.VACANCIES_HIRIFY_OUTPUT_PATH = config.get_path('vacancies_hirify_output_path')

        # Estimator responsible for parsing saved MHTML files
        self.estimator = HirifyVacancyEstimator()

    def run_on_urls(self):
        """Load URLs, open in Chrome, and run automation logic."""
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

            chrome_paths = [r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
            chrome_executable = next((path for path in chrome_paths if os.path.exists(path)), None)

            if chrome_executable:
                subprocess.Popen([chrome_executable, url])
            else:
                os.startfile(url)

            print("⏳ Waiting 30 seconds for the page to load...")
            time.sleep(30)

            print("🤖 Starting Hirify automation logic for this URL...")
            self._execute_hirify_automation()

            print(f"✅ Finished processing URL: {url}")

        print("\n✅ Finished processing all URLs.")

    def _execute_hirify_automation(self):
        """
        State-machine logic to handle BOTH List Screen and Vacancy Screen.
        """
        vacancies_processed = 0
        scroll_count = 0

        while vacancies_processed < self.MAX_VACANCIES_PER_URL:
            # 1. Parse screen ONCE per page state
            print("📊 Parsing screen...")
            screenshot = ImageGrab.grab()
            self.parser.parse_screen(screenshot)

            more_options_buttons = self.parser._more_options_buttons
            triangle_downs = self.parser._triangle_down_candidates
            next_buttons = self.parser._next_buttons

            # 2. Process ALL vacancies based on CURRENT parsing (without reparsing in between)
            processed_on_this_parse = 0

            for more_btn in more_options_buttons:
                if vacancies_processed >= self.MAX_VACANCIES_PER_URL:
                    print(f"✅ Reached MAX_VACANCIES_PER_URL ({self.MAX_VACANCIES_PER_URL}). Stopping.")
                    return

                print(f"  Processing vacancy {vacancies_processed + 1}/{self.MAX_VACANCIES_PER_URL}")

                # Click 10% left of the more options button
                bbox = more_btn.get('bbox', [])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    click_x_ratio = max(0.0, cx - 0.10)
                    click_y_ratio = cy
                    self._click_at_ratio(click_x_ratio, click_y_ratio)
                else:
                    self.click_bbox_center(bbox)

                time.sleep(5)  # Wait for vacancy page to load

                # Process vacancy
                current_url = self._get_current_url()
                if current_url and 'hirify.me/jobs/' in current_url:
                    self._save_and_process_vacancy(current_url)
                    vacancies_processed += 1
                    processed_on_this_parse += 1
                else:
                    print("  ⚠️ Failed to navigate to vacancy page or URL not detected.")

                # Navigate back
                print("  ⏪ Navigating back to vacancy list...")
                self._navigate_back_to_list()
                time.sleep(10)  # Wait at least 10 seconds for list to load

            # 3. After iterating through all found buttons, check if we need to scroll or go next
            if processed_on_this_parse == 0:
                print("⚠️ No vacancies were processed in this pass.")

            # Check if we should scroll down to load more
            if triangle_downs:
                print(f"🔻 Triangle down detected. Clicking to load more vacancies...")
                for _ in range(self.MAX_SCROLL_DOWNS):
                    self.click_bbox_center(triangle_downs[0]['bbox'])
                    time.sleep(0.2)
                # Loop continues, which will reparse the screen
                continue

            # Check if we should go to next page
            if next_buttons:
                print("➡️ Next button detected. Clicking and waiting 20s...")
                self.click_bbox_center(next_buttons[0]['bbox'])
                time.sleep(20)
                # Loop continues, which will reparse the screen
                continue

            # If no more options, no scroll, and no next, we are done with this URL
            print("🛑 No more vacancies, no scroll, and no next button. Ending automation for this URL.")
            break

    def _get_current_url(self) -> str:
        """Get the current URL from the browser address bar safely."""
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.5)
        url = pyperclip.paste().strip()
        pyautogui.press('esc')  # Deselect address bar safely
        time.sleep(0.5)
        return url

    def _click_at_ratio(self, x_ratio: float, y_ratio: float):
        """Click at a specific ratio of the screen."""
        screen_width, screen_height = pyautogui.size()
        x = int(x_ratio * screen_width)
        y = int(y_ratio * screen_height)
        pyautogui.click(x, y)

    def _save_and_process_vacancy(self, vacancy_url: str):
        """Save the current vacancy page as MHTML and process it."""
        job_id = self.extract_job_id_from_url(vacancy_url)
        if not job_id:
            print(f"  ⚠️ Could not extract job ID from URL: {vacancy_url}")
            return

        dest_file = os.path.join(
            self.VACANCIES_HIRIFY_OUTPUT_PATH,
            f'Hirify_Vacancy_{job_id}.mhtml'
        )

        os.makedirs(os.path.dirname(dest_file), exist_ok=True)

        if os.path.exists(dest_file):
            print(f"  ✅ MHTML file already exists: {dest_file}")
        else:
            self.save_browser_page_as_mhtml(dest_file)

        self.estimator.estimate(dest_file, vacancy_url)

    def _navigate_back_to_list(self):
        """Navigate back to the vacancy list page."""
        if self.parser._back_button:
            bbox = self.parser._back_button.get('bbox', [])
            if len(bbox) == 4:
                print("  🖱️ Clicking detected Back button on screen.")
                self.click_bbox_center(bbox)
                return

        print("  🖱️ No Back button detected on screen, using browser back (Alt+Left).")
        pyautogui.hotkey('alt', 'left')

    def extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from Hirify URL (e.g., '97028' from '.../jobs/97028-...')."""
        match = re.search(r'jobs/(\d+)', url)
        if match:
            return match.group(1)
        return None