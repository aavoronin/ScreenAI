import os
import re
import glob
from datetime import datetime
from bs4 import BeautifulSoup
from Estimators.BaseVacancyEstimator import BaseVacancyEstimator
from cfg.cfg import Config


class LinkedInVacancyEstimator(BaseVacancyEstimator):
    """
    Estimator specialized for LinkedIn vacancy MHTML files.
    Knows how to:
    - Parse the filename to extract vacancy type and job ID
    - Apply LinkedIn-specific HTML cleaning rules
    - Manage the per-vacancy JSON config
    """

    def __init__(self):
        super().__init__()
        self.PARSING_VERSION = 1

    # ------------------------------------------------------------------
    # Filename parsing
    # ------------------------------------------------------------------
    def parse_filename(self, mhtml_path):
        """
        Extract vacancy_type and job_id from filename.
        Expected format: <VacancyType>_Vacancy_<job_id>.mhtml
        e.g. "LinkedIn_Vacancy_4243685939.mhtml" -> ("LinkedIn", "4243685939")
        Returns (vacancy_type, job_id) or (None, None) on failure.
        """
        filename = os.path.basename(mhtml_path)
        match = re.match(r'^(\w+)_Vacancy_(\d+)\.mhtml$', filename)
        if match:
            return match.group(1), match.group(2)
        return None, None

    # ------------------------------------------------------------------
    # LinkedIn-specific HTML cleaning
    # ------------------------------------------------------------------
    def get_tags_to_remove(self):
        """Tags that should be removed for LinkedIn vacancy pages."""
        return ['script', 'style', 'noscript', 'svg', 'link', 'meta']

    def html_to_formatted_text(self, html_content):
        """
        Convert LinkedIn vacancy HTML to formatted plain text.
        Retains apply/job links as 'Text URL' pairs.
        """
        # 1. Remove invisible content (scripts, styles, etc.)
        html_content = self.strip_tags(html_content, self.get_tags_to_remove())

        # 2. Remove explicitly hidden elements
        html_content = self.remove_hidden_elements(html_content)

        # 3. LinkedIn-specific link handling via BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        for a in soup.find_all('a'):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            if href and ('apply' in href.lower() or 'job' in href.lower()):
                a.replace_with(f"{text} {href}" if text else href)
            else:
                a.replace_with(text)

        # 4. Extract visible text (generic)
        text = self.extract_visible_text(str(soup))

        # 5. LinkedIn-specific: trim header/footer noise
        start_marker = "Get job alerts for this search"
        if start_marker in text:
            text = text[text.index(start_marker) + len(start_marker):]

        end_marker = "Job search faster with Premium"
        if end_marker in text:
            text = text[:text.index(end_marker)]

        return text.strip()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def estimate(self, mhtml_path):
        """
        Estimate a LinkedIn vacancy from its MHTML file.

        Logic:
        - If JSON config doesn't exist -> full parsing
        - If JSON exists and parsing_version == PARSING_VERSION -> skip
        - Otherwise -> full parsing
        After parsing, parsed_date and parsing_version are updated,
        and vacancy_score is set to 0.
        """
        # 1. Parse filename to get vacancy type and job id
        vacancy_type, job_id = self.parse_filename(mhtml_path)
        if not vacancy_type or not job_id:
            print(f"⚠️ Could not parse filename: {mhtml_path}")
            return

        print(f"🔍 Processing {vacancy_type} vacancy, job ID: {job_id}")

        # 2. Derive sibling paths (.txt and .json)
        base_path = os.path.splitext(mhtml_path)[0]
        txt_path = base_path + '.txt'
        json_path = base_path + '.json'

        # 3. Decide whether we need to (re)parse
        if not self.should_parse(json_path):
            print(f"✅ Already parsed with current version. Skipping: {mhtml_path}")
            return

        # 4. Load existing config or create a fresh one
        config = self.load_config(json_path)
        if config is None:
            # Use MHTML file mtime as saved_date when creating fresh config
            try:
                saved_date = datetime.fromtimestamp(
                    os.path.getmtime(mhtml_path)
                ).isoformat()
            except OSError:
                saved_date = datetime.now().isoformat()
            config = self.create_initial_config(saved_date)

        # 5. Full parsing
        print(f"🔄 Performing full parsing for: {mhtml_path}")
        html_content = self.open_mhtml(mhtml_path)
        text = self.html_to_formatted_text(html_content)
        self.save_text(txt_path, text)

        # 6. Update config with parsing results
        config['parsed_date'] = datetime.now().isoformat()
        config['parsing_version'] = self.PARSING_VERSION
        config['vacancy_score'] = 0
        self.save_config(json_path, config)

        print(f"✅ Completed parsing for job ID: {job_id}")

    # ------------------------------------------------------------------
    # Batch estimation
    # ------------------------------------------------------------------
    def estimate_vacancies(self):
        """
        Scan all mhtml files in vacancies_linkedin_output_path
        and apply estimate method to each of them.
        """
        config = Config()
        vacancies_dir = config.get_path('vacancies_linkedin_output_path')

        if not os.path.exists(vacancies_dir):
            print(f"⚠️ Vacancies directory does not exist: {vacancies_dir}")
            return

        mhtml_files = glob.glob(os.path.join(vacancies_dir, '*.mhtml'))

        if not mhtml_files:
            print(f"ℹ️ No .mhtml files found in {vacancies_dir}")
            return

        print(f"🔍 Found {len(mhtml_files)} .mhtml file(s) to estimate.")

        for i, mhtml_path in enumerate(mhtml_files):
            if i % 10 == 0:
                print(f"{i:<6} files estimated")
            self.estimate(mhtml_path)

        print("✅ Finished estimating all vacancies.")