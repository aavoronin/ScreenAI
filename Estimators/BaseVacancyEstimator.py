import os
import re
import json
import email
from datetime import datetime
from bs4 import BeautifulSoup


class BaseVacancyEstimator:
    """
    Base class for vacancy estimators. Provides reusable methods
    for opening MHTML files, stripping tags, extracting text,
    saving results, and managing per-vacancy JSON config files.
    """

    def __init__(self):
        self.PARSING_VERSION = 1

    # ------------------------------------------------------------------
    # MHTML handling
    # ------------------------------------------------------------------
    def open_mhtml(self, file_path):
        """
        Open an MHTML file and extract the HTML part only
        (prevents MultipartBoundary garbage).
        Returns the HTML content as a string.
        """
        print(f"📝 Opening MHTML file: {file_path}")
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
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

        return html_content

    # ------------------------------------------------------------------
    # Generic HTML cleaning
    # ------------------------------------------------------------------
    def strip_tags(self, html_content, tags_to_remove):
        """
        Remove a list of tags (and their contents) from HTML.
        Returns the modified HTML as a string.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup.find_all(tags_to_remove):
            tag.decompose()
        return str(soup)

    def remove_hidden_elements(self, html_content):
        """
        Remove elements with display:none style or hidden attribute.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            tag.decompose()
        for tag in soup.find_all(hidden=True):
            tag.decompose()
        return str(soup)

    def extract_visible_text(self, html_content):
        """
        Extract all visible text from HTML and clean up whitespace.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        # Clean up excessive blank lines and spaces
        text = re.sub(r'\n{3,}', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    def save_text(self, file_path, text):
        """Save text content to a file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✅ Successfully saved text to: {file_path}")

    # ------------------------------------------------------------------
    # Config (JSON) management
    # ------------------------------------------------------------------
    def load_config(self, json_path):
        """
        Load JSON config file. Returns None if file doesn't exist
        or cannot be parsed as valid JSON.
        """
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Could not load config from {json_path}: {e}")
            return None

    def save_config(self, json_path, config):
        """Save JSON config file."""
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved config to: {json_path}")

    def should_parse(self, json_path):
        """
        Determine if full parsing is needed based on the config file.
        Returns True if parsing is needed, False otherwise.
        """
        config = self.load_config(json_path)
        if config is None:
            return True
        if 'parsing_version' not in config:
            return True
        if config['parsing_version'] != self.PARSING_VERSION:
            return True
        return False

    def create_initial_config(self, saved_date=None):
        """Create an initial config dictionary for a vacancy."""
        return {
            'saved_date': saved_date or datetime.now().isoformat(),
            'parsed_date': None,
            'parsing_version': None,
            'vacancy_score': 0
        }

    # ------------------------------------------------------------------
    # Main entry point (to be overridden by subclasses)
    # ------------------------------------------------------------------
    def estimate(self, mhtml_path):
        """
        Main estimation method. Subclasses must implement this.
        """
        raise NotImplementedError("Subclasses must implement estimate()")