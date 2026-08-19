import os
import re
import ctypes
import time
from datetime import datetime
import pyautogui
import pyperclip
from Estimators.BaseVacancyEstimator import BaseVacancyEstimator


class BaseNavigator:
    def __init__(self, parser, output_dir: str):
        self.parser = parser
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.obtain_screen_size()
        self.estimator: BaseVacancyEstimator = None
        self.VACANCIES_OUTPUT_PATH = None
        self.saved_pages = []

    def obtain_screen_size(self):
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

    def click_bbox_center(self, bbox, print_xy=False):
        x, y = self.get_pixel_center(bbox)
        if print_xy:
            print(f"Clicking at pixel coords: ({x}, {y})")
        pyautogui.click(x, y)

    def check_wait(self):
        if self._is_numlock_on():
            print("⏸️ NumLock is ON. Waiting until it is turned off...")
            while self._is_numlock_on():
                time.sleep(1)
            print("▶️ NumLock is OFF. Resuming.")

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
        self.saved_pages.append(dest_file)
        print(
            f"✅ Successfully saved MHTML: {dest_file} "
            f"(Total: {len(self.saved_pages)})"
        )

    def _is_numlock_on(self):
        return bool(ctypes.windll.user32.GetKeyState(0x90) & 1)

    def _toggle_numlock(self):
        pyautogui.press('numlock')

    def group_vacancies(self):
        print(self.VACANCIES_OUTPUT_PATH)
        vacancies_dir = os.path.join(self.VACANCIES_OUTPUT_PATH)
        chunks_dir = os.path.join(self.VACANCIES_OUTPUT_PATH, '..' , 'Chunks')

        if not os.path.exists(vacancies_dir):
            print(f"⚠️ Vacancies directory does not exist: {vacancies_dir}")
            return

        # Create the Chunks folder if it does not exist yet
        os.makedirs(chunks_dir, exist_ok=True)

        # Collect files matching <site>_Vacancy_<JobId>.txt
        file_pattern = re.compile(r'^(\w+)_Vacancy_(\d+)\.txt$')
        candidates = []
        for filename in os.listdir(vacancies_dir):
            match = file_pattern.match(filename)
            if not match:
                continue
            file_path = os.path.join(vacancies_dir, filename)
            if not os.path.isfile(file_path):
                continue
            created_time = os.path.getctime(file_path)
            candidates.append({
                'filename': filename,
                'file_path': file_path,
                'created_time': created_time,
                'site': match.group(1)
            })

        if not candidates:
            print(f"ℹ️ No matching vacancy .txt files in {vacancies_dir}")
            return

        # Sort by created date in ascending order
        candidates.sort(key=lambda item: item['created_time'])

        print(f"🔍 Found {len(candidates)} vacancy .txt file(s) to group.")

        max_chunk_size = 1024 * 1024 * 10
        current_chunk = []
        current_chunk_size = 0

        for item in candidates:
            with open(item['file_path'], 'r', encoding='utf-8',
                      errors='ignore') as f:
                content = f.read()

            loaded_str = datetime.fromtimestamp(
                item['created_time']
            ).strftime('%Y-%m-%d %H:%M:%S')

            # Build the wrapped block for this file and measure its size
            block = f"=======Start {item['filename']}=======\n"
            block += f"loaded: {loaded_str}\n"
            block += content
            if not content.endswith('\n'):
                block += '\n'
            block += f"=======End {item['filename']}=======\n"

            block_size = len(block.encode('utf-8'))

            # Flush the current chunk if this file would exceed the limit
            exceeds_limit = current_chunk_size + block_size > max_chunk_size
            if current_chunk and exceeds_limit:
                self._write_vacancy_chunk(current_chunk, chunks_dir)
                current_chunk = []
                current_chunk_size = 0

            current_chunk.append({
                'filename': item['filename'],
                'site': item['site'],
                'created_time': item['created_time'],
                'block': block
            })
            current_chunk_size += block_size

        # Flush the remaining chunk, if any
        if current_chunk:
            self._write_vacancy_chunk(current_chunk, chunks_dir)

        print("✅ Finished grouping vacancies into chunks.")

    def _write_vacancy_chunk(self, chunk, chunks_dir):
        """
        Write one chunk of grouped vacancy files into the Chunks folder.
        The chunk is named <site>_Vacancies_<YYYYMMDDHHMMSS>.txt where
        the timestamp comes from the latest (last) file in the chunk.
        Original vacancy files are only read, never deleted.
        """
        if not chunk:
            return

        # Chunks are built in ascending created-date order, so the last
        # item holds the latest timestamp and determines the chunk name.
        latest = chunk[-1]
        timestamp_str = datetime.fromtimestamp(
            latest['created_time']
        ).strftime('%Y%m%d%H%M%S')
        chunk_name = f"{latest['site']}_Vacancies_{timestamp_str}.txt"
        chunk_path = os.path.join(chunks_dir, chunk_name)

        chunk_content = ''.join(item['block'] for item in chunk)

        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(chunk_content)

        chunk_size = len(chunk_content.encode('utf-8'))
        print(f"📦 Chunk: {chunk_name} | Size: {chunk_size} bytes | "
              f"Files: {len(chunk)}")