import os
import re
import glob
from datetime import datetime
from bs4 import BeautifulSoup
from Estimators.BaseVacancyEstimator import BaseVacancyEstimator
from cfg.cfg import Config

class HirifyVacancyEstimator(BaseVacancyEstimator):
    """
    Estimator specialized for Hirify vacancy MHTML files.
    Knows how to:
    - Parse the filename to extract vacancy type and job ID
    - Apply Hirify-specific HTML cleaning rules
    - Manage the per-vacancy JSON config
    """
    def __init__(self):
        super().__init__()

    def parse_filename(self, mhtml_path):
        """
        Extract vacancy_type and job_id from filename.
        Expected format: Hirify_Vacancy_<job_id>.mhtml
        e.g. "Hirify_Vacancy_740725.mhtml" -> ("Hirify", "740725")
        Returns (vacancy_type, job_id) or (None, None) on failure.
        """
        filename = os.path.basename(mhtml_path)
        match = re.match(r'^Hirify_Vacancy_(\d+)\.mhtml$', filename)
        if match:
            return "Hirify", match.group(1)
        return None, None

    def get_tags_to_remove(self):
        """Tags that should be removed for Hirify vacancy pages."""
        return ['script', 'style', 'noscript', 'svg', 'link', 'meta', 'iframe']

    def html_to_formatted_text(self, html_content):
        """
        Convert Hirify vacancy HTML to formatted plain text.
        Truncates the text at "Similar vacancies" to remove footer noise
        and other job listings that are not part of the current vacancy.
        """
        # 1. Remove invisible content (scripts, styles, etc.)
        html_content = self.strip_tags(html_content, self.get_tags_to_remove())
        # 2. Remove explicitly hidden elements
        html_content = self.remove_hidden_elements(html_content)
        # 3. Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        text_parts = []
        # Extract all visible text
        visible_text = self.extract_visible_text(str(soup))
        # Truncate at "Similar vacancies" to remove noise from other listings
        cutoff_marker = "Similar vacancies"
        if cutoff_marker in visible_text:
            visible_text = visible_text[:visible_text.index(cutoff_marker)]
        text_parts.append(visible_text.strip())
        # Join all parts
        text = '\n'.join(text_parts)
        # Clean up excessive whitespace (more than 2 consecutive newlines)
        text = re.sub(r'\n{3,}', '\n', text)
        # Clean up spaces around newlines and multiple spaces
        text = re.sub(r' *\n *', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def estimate(self, mhtml_path, url: str = ""):
        """
        Estimate a Hirify vacancy from its MHTML file.
        vacancy_url should be the full URL from the browser (e.g., https://hirify.me/jobs/97028-...)
        """
        # 1. Parse filename to get vacancy type and job id
        vacancy_type, job_id = self.parse_filename(mhtml_path)
        if not vacancy_type or not job_id:
            print(f"⚠️ Could not parse filename: {mhtml_path}")
            return
        print(f"🔍 Processing {vacancy_type} vacancy, job ID: {job_id}")
        # 2. Derive sibling paths (.txt, .json, and .html)
        base_path = os.path.splitext(mhtml_path)[0]
        txt_path = base_path + '.txt'
        json_path = base_path + '.json'
        html_path = base_path + '.html'
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
        print(f" Performing full parsing for: {mhtml_path}")
        html_content = self.open_mhtml(mhtml_path)
        text = self.html_to_formatted_text(html_content)
        self.save_text(txt_path, text)
        # 6. Update config with parsing results and keywords
        config['parsed_date'] = datetime.now().isoformat()
        config['parsing_version'] = str(self.PARSING_VERSION)
        config['json_path'] = json_path
        config['txt_path'] = txt_path
        config['html_path'] = html_path
        if url:
            config['url'] = url
        config = self.update_config_with_keywords(config, text)
        self.save_config(json_path, config)
        print(f"✅ Completed parsing for job ID: {job_id}")

    def estimate_vacancies(self):
        """
        Scan all mhtml files in vacancies_hirify_output_path
        and apply estimate method to each of them.
        """
        config = Config()
        vacancies_dir = config.get_path('vacancies_hirify_output_path')
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

    def vacancy_clean(self, text: str) -> str:
        return text

