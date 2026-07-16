import os
import time
import datetime
import ctypes
import re
import email
import pyautogui
import pyperclip
from PIL import ImageGrab
from Screen.LinkedInScreenParser import LinkedInScreenParser
from bs4 import BeautifulSoup


class LinkedInNavigator:
    def __init__(self, omniparser_repo_path: str):
        self.parser = LinkedInScreenParser(omniparser_repo_path)
        self.output_dir = r"C:\Py\ScreenAI\parsed screens"
        os.makedirs(self.output_dir, exist_ok=True)

        # Termination condition 1
        self.MAX_CLOSE_BUTTONS = 3
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
            print("\n Parsing screen...")
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
                click_close_left_partner(close_bbox)

                # Wait 5 sec
                time.sleep(5)

                # Find first bbox in _linkedin_buttons
                if linkedin_buttons:
                    first_linkedin_bbox = linkedin_buttons[0]['bbox']
                    click_bbox_center(first_linkedin_bbox)

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
                            print(f" ️ URL already processed. Skipping.")
                            # Continue loop to next close button
                            continue
                    else:
                        print(" ⚠️ Clipboard text is empty. Doing nothing.")
                else:
                    print(" ️ No LinkedIn buttons detected. Skipping clipboard logic.")

            # Termination Condition 3: No new URLs found in this pass
            if not found_new_url_in_pass:
                print("🛑 No new URLs found in this pass. Terminating logic.")
                break

            # 3. Check Next button or Scroll Down button
            if next_buttons:
                print("➡️ Next button detected. Clicking and waiting 20s...")
                click_bbox_center(next_buttons[0]['bbox'])
                time.sleep(20)
                # Loop continues, which will parse screen again
            elif scroll_downs:
                print(f"️ Scroll down (triangle_down) detected. Clicking {self.MAX_SCROLL_DOWNS} times...")
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
        Process the vacancy URL: extract job ID, save as .mhtml, then extract
        plain text (retaining apply links as URLs) and save as .txt.
        """
        # 1. Parse URL and extract job_id
        match = re.search(r'currentJobId=(\d+)', url)
        if not match:
            print(f"⚠️ Could not extract currentJobId from URL: {url}")
            return

        job_id = match.group(1)

        # 2. Create destination file path
        VACANCIES_LINKED_IN_OUTPUT_PATH = r'C:\Py\ScreenAI\out\LinkedIn\Vacancies'
        dest_file = os.path.join(VACANCIES_LINKED_IN_OUTPUT_PATH, f'LinkedIn_Vacancy_{job_id}.mhtml')
        txt_file = os.path.splitext(dest_file)[0] + '.txt'

        # 3. Make folders if they do not exist
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)

        # 4. Check if file already exists.
        if os.path.exists(dest_file):
            print(f"✅ MHTML file already exists: {dest_file}")
        else:
            print(f"💾 Saving vacancy {job_id} to: {dest_file}")

            # 5. Click ctrl-s
            pyautogui.hotkey('ctrl', 's')

            # 6. Wait 10 secs for Save dialog to appear
            time.sleep(10)

            # 7. Type full file name (using clipboard + ctrl+v is much more reliable)
            pyperclip.copy(dest_file)
            pyautogui.hotkey('ctrl', 'v')

            # 8. Click enter
            pyautogui.press('enter')

            # 9. Wait 10 secs for the file to finish saving
            time.sleep(10)
            print(f"✅ Successfully saved MHTML: {dest_file}")

        print(f"📝 Extracting plain text from {dest_file}...")

        # Open file and parse as MIME message to extract only the HTML part (prevents MultipartBoundary garbage)
        import email
        with open(dest_file, 'r', encoding='utf-8', errors='ignore') as f:
            msg = email.message_from_file(f)

        html_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_content = payload.decode(charset, errors='ignore')
                        break
        else:
            charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True)
            if payload:
                html_content = payload.decode(charset, errors='ignore')
            else:
                html_content = msg.get_payload()

        # Parse and format using BeautifulSoup (strips tags, keeps apply links as URLs)
        text = self.html_to_formatted_text(html_content)

        # Save resulting text to .txt file
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(text)

        print(f"✅ Successfully saved text to: {txt_file}")

    def html_to_formatted_text(self, html_content: str) -> str:
        """
        Strips HTML tags, removes scripts/styles, and extracts only visible plain text.
        Retains apply/job links as URLs.
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. Remove invisible content: scripts, styles, svg, etc.
        for tag in soup.find_all(['script', 'style', 'noscript', 'svg', 'link', 'meta']):
            tag.decompose()

        # 2. Remove explicitly hidden elements
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            tag.decompose()
        for tag in soup.find_all(hidden=True):
            tag.decompose()

        # 3. Retain apply/job links as "Text URL"
        for a in soup.find_all('a'):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            if href and ('apply' in href.lower() or 'job' in href.lower()):
                a.replace_with(f"{text} {href}" if text else href)
            else:
                a.replace_with(text)

        # 4. Extract all visible text
        text = soup.get_text(separator='\n', strip=True)

        # 5. Clean up excessive blank lines and spaces
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')