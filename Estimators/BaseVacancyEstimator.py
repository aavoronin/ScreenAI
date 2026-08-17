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
        self.PARSING_VERSION = 2

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
        current_version = config.get('parsing_version', 0)
        if current_version < self.PARSING_VERSION:
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

    def _load_estimator_config(self):
        """Load estimator configuration from Estimators/estimator_config.json"""
        estimator_config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'estimator_config.json'
        )
        if not os.path.exists(estimator_config_path):
            print(f"⚠️ Estimator config not found at: {estimator_config_path}")
            return {}
        try:
            with open(estimator_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Could not load estimator config: {e}")
            return {}

    def _extract_keywords_from_config(self, config_data):
        """Extract keywords, countries, and industries from estimator config."""
        keywords = set()
        countries = set()
        industries = set()

        # Extract tech keywords
        tech_section = config_data.get('tech', {})
        if isinstance(tech_section, dict):
            for category, items in tech_section.items():
                if isinstance(items, dict):
                    for keyword in items.keys():
                        keywords.add(keyword)
                elif isinstance(items, list):
                    for keyword in items:
                        keywords.add(keyword)

        # Extract synonyms (handles both list and dict formats)
        # Note: the config file uses "synonymns" (typo in key), so we check both
        synonyms_section = config_data.get('synonyms', config_data.get('synonymns', []))
        if isinstance(synonyms_section, list):
            for sublist in synonyms_section:
                if isinstance(sublist, list):
                    for keyword in sublist:
                        keywords.add(keyword)
                else:
                    keywords.add(sublist)
        elif isinstance(synonyms_section, dict):
            for category, items in synonyms_section.items():
                if isinstance(items, list):
                    for keyword in items:
                        keywords.add(keyword)

        # Extract countries (handles list of lists format)
        countries_section = config_data.get('countries', [])
        if isinstance(countries_section, list):
            for sublist in countries_section:
                if isinstance(sublist, list):
                    for country in sublist:
                        countries.add(country)
                else:
                    countries.add(sublist)
        elif isinstance(countries_section, dict):
            for category, items in countries_section.items():
                if isinstance(items, list):
                    for country in items:
                        countries.add(country)

        # Extract industries (handles list of lists format)
        industries_section = config_data.get('industries', [])
        if isinstance(industries_section, list):
            for sublist in industries_section:
                if isinstance(sublist, list):
                    for industry in sublist:
                        industries.add(industry)
                else:
                    industries.add(sublist)
        elif isinstance(industries_section, dict):
            for category, items in industries_section.items():
                if isinstance(items, list):
                    for industry in items:
                        industries.add(industry)

        return sorted(keywords), sorted(countries), sorted(industries)

    def _find_matches_in_text(self, text, keywords):
        """Find all keywords in text using word boundary regex, case-insensitive."""
        found = set()
        text_lower = text.lower()

        # Sort keywords by length (descending) to match longer phrases first
        sorted_keywords = sorted(keywords, key=lambda x: -len(x))

        for keyword in sorted_keywords:
            keyword_lower = keyword.lower()
            # Escape special regex characters
            escaped_keyword = re.escape(keyword_lower)
            # Replace spaces with \s+ to handle variable spacing
            pattern_str = escaped_keyword.replace(r'\ ', r'\s+')
            # Wrap with word boundaries
            pattern = r'\b' + pattern_str + r'\b'
            if re.search(pattern, text_lower):
                found.add(keyword)

        return sorted(found)

    def update_config_with_keywords(self, config, text):
        """
        Update config with keywords, countries, and industries extracted from text.
        Only updates if parsing_version is less than current PARSING_VERSION.
        """
        current_version = config.get('parsing_version', 0)
        if current_version >= self.PARSING_VERSION:
            return config

        estimator_config = self._load_estimator_config()
        if not estimator_config:
            return config

        keywords_list, countries_list, industries_list = self._extract_keywords_from_config(
            estimator_config
        )

        matched_keywords = self._find_matches_in_text(text, keywords_list)
        matched_countries = self._find_matches_in_text(text, countries_list)
        matched_industries = self._find_matches_in_text(text, industries_list)

        config['keywords'] = matched_keywords
        config['countries'] = matched_countries
        config['industries'] = matched_industries
        config['parsing_version'] = self.PARSING_VERSION

        return config

    # ------------------------------------------------------------------
    # Main entry point (to be overridden by subclasses)
    # ------------------------------------------------------------------
    def estimate(self, mhtml_path):
        """
        Main estimation method. Subclasses must implement this.
        """
        raise NotImplementedError("Subclasses must implement estimate()")