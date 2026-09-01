import os
import time
import re
import subprocess
import pyautogui
import pyperclip
from datetime import datetime
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
        self.MAX_VACANCIES_PER_URL = 250
        self.MAX_SCROLL_DOWNS = 10
        self.HIRIFY_URLS_FILE_PATH = r"C:\Py\ScreenAI\Navigators\hirify_urls.csv"
        self.VACANCIES_OUTPUT_PATH = config.get_path('vacancies_hirify_output_path')
        # Estimator responsible for parsing saved MHTML files
        self.estimator = HirifyVacancyEstimator()

    def get_vacancies_output_path(self):
        return self.VACANCIES_OUTPUT_PATH

    def run_on_urls(self, max_urls: int = None):
        """Load URLs, open in Chrome, and run automation logic."""
        config = Config()
        urls_file_path = config.get_path('hirify_urls_file_path') or self.HIRIFY_URLS_FILE_PATH
        log_path = config.get_path('hirify_log_path') or r"C:\Py\ScreenAI\out\Hirify\log\log.txt"
        if not os.path.exists(urls_file_path):
            print(f"⚠️ URLs file not found: {urls_file_path}")
            return
        with open(urls_file_path, 'r', encoding='utf-8') as f:
            urls = list(dict.fromkeys(line.strip() for line in f if line.strip()))
        if not urls:
            print("⚠️ No URLs found in the file.")
            return
        url_log = self._load_url_log(log_path)
        processed_count = 0
        while True:
            if max_urls is not None and processed_count >= max_urls:
                print(f"✅ Reached max_urls limit ({max_urls}). Stopping.")
                break
            next_url = self._select_next_url(urls, url_log)
            if next_url is None:
                print("✅ All URLs have been processed and logged. No more URLs to process.")
                break
            print(f"\n🌐 [{processed_count + 1}] Processing URL: {next_url}")
            chrome_paths = [r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
            chrome_executable = next((path for path in chrome_paths if os.path.exists(path)), None)
            if chrome_executable:
                subprocess.Popen([chrome_executable, next_url])
            else:
                os.startfile(next_url)
            print("⏳ Waiting 30 seconds for the page to load...")
            time.sleep(30)
            try:
                # Run the automation logic
                print("🤖 Starting Hirify automation logic for this URL...")
                self._execute_hirify_automation()
            except Exception as e:
                print(f"⚠️ Error during automation: {e}")
                continue
            url_log[next_url] = datetime.now()
            self._save_url_log(log_path, url_log)
            processed_count += 1
            print(f"✅ Finished processing URL: {next_url}")
        print("✅ Finished processing URLs.")

    def _execute_hirify_automation(self):
        """
        State-machine logic to handle BOTH List Screen and Vacancy Screen.
        """
        vacancies_processed = 0
        tracked_vacancy_urls = []
        while vacancies_processed < self.MAX_VACANCIES_PER_URL:
            print("📊 Parsing screen...")
            for _ in range(10):
                try:
                    self.check_wait()
                    self.obtain_screen_size()
                    screenshot = self._grab_screenshot()
                    self.parser.parse_screen(screenshot)
                except Exception as e:
                    time.sleep(10)
                    continue
                break
            more_options_buttons = self.parser._more_options_buttons
            triangle_downs = self.parser._triangle_down_candidates
            next_buttons = self.parser._next_buttons
            vacancies_processed0 = vacancies_processed
            # 1. Process all "More" buttons found on the current screen
            for more_btn in more_options_buttons:
                if vacancies_processed >= self.MAX_VACANCIES_PER_URL:
                    print(f"✅ Reached MAX_VACANCIES_PER_URL ({self.MAX_VACANCIES_PER_URL}). Stopping.")
                    return
                print(f"  Processing vacancy {vacancies_processed + 1}/{self.MAX_VACANCIES_PER_URL}")
                bbox = more_btn.get('bbox', [])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    click_x_ratio = max(0.0, cx - 0.10)  # 10% left of the button
                    click_y_ratio = cy
                    self._click_at_ratio(click_x_ratio, click_y_ratio)
                else:
                    self.click_bbox_center(bbox)
                time.sleep(10)  # Wait for vacancy page to load
                current_url = self._get_current_url()
                if current_url and 'hirify.me/jobs/' in current_url:
                    print(f"  💾 Saving and processing vacancy: {current_url}")
                    tracked_vacancy_urls.append(current_url)

                    for n1, n2 in [(2, 8), (4, 16), (6, 20), (8, 24), (10, 30)]:
                        if len(tracked_vacancy_urls) > n2:
                            if len(set(tracked_vacancy_urls[-n2:])) <= n1:
                                print(f"🛑 Aborting: Last {n2} tracked URLs "
                                      f"contain <= {n1} distinct values.")
                                return

                    self._save_and_process_vacancy(current_url)
                    vacancies_processed += 1
                    print("  ⏪ Navigating back to vacancy list...")
                    self._navigate_back_to_list()
                    time.sleep(10)  # Wait for list page to load
                else:
                    print(f"  ⚠️ Failed to navigate to vacancy page (URL: {current_url}). Skipping this button.")
                    pyautogui.press('esc')  # Close any dropdowns that might have opened
                    time.sleep(1)
                    continue  # Skip to next button WITHOUT clicking "Back"
            # 2. AFTER processing all buttons on the current screen, we MUST load more vacancies.
            if triangle_downs and vacancies_processed0 < vacancies_processed:
                print(f"🔻 Triangle down detected. Clicking {self.MAX_SCROLL_DOWNS} times to load more vacancies...")
                for _ in range(self.MAX_SCROLL_DOWNS):
                    self.click_bbox_center(triangle_downs[0]['bbox'])
                    time.sleep(0.2)
                continue  # Reparse screen to find NEW vacancies
            if next_buttons:
                print("➡️ Next button detected. Clicking and waiting 20s...")
                self.click_bbox_center(next_buttons[0]['bbox'])
                time.sleep(20)
                continue  # Reparse screen
            # If neither scroll nor next worked, we are done with this URL
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
            self.VACANCIES_OUTPUT_PATH,
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
        # if self.parser._back_button:
        #    bbox = self.parser._back_button.get('bbox', [])
        #    if len(bbox) == 4:
        #       print("  🖱️ Clicking detected Back button on screen.")
        #        self.click_bbox_center(bbox)
        #        return
        print("  🖱️ No Back button detected on screen, using browser back (Alt+Left).")
        pyautogui.hotkey('alt', 'left')

    def extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from Hirify URL (e.g., '97028' from '.../jobs/97028-...')."""
        match = re.search(r'jobs/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def analyze_collected(self):
        """
        Analyze all collected Hirify vacancy MHTML files.
        Delegates to the HirifyVacancyEstimator to parse, clean, and estimate them.
        """
        self.estimator.estimate_vacancies()