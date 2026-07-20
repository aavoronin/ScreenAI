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
        self.PARSING_VERSION = 1

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

    def html_to_formatted_text(self, html_content, vacancy_url: str = None):
        """
        Convert Hirify vacancy HTML to formatted plain text.
        Based on the attached MHTML example structure.
        """
        # 1. Remove invisible content (scripts, styles, etc.)
        html_content = self.strip_tags(html_content, self.get_tags_to_remove())

        # 2. Remove explicitly hidden elements
        html_content = self.remove_hidden_elements(html_content)

        # 3. Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # 4. Extract main content areas specific to Hirify
        # Based on the screenshot, look for:
        # - Job title (e.g., "Data Engineer II (AWS)")
        # - Job description section
        # - Company information
        # - Requirements/benefits

        text_parts = []

        # Add vacancy URL as first line if provided
        if vacancy_url:
            text_parts.append(f"Vacancy URL: {vacancy_url}")
            text_parts.append("")  # Empty line for separation

        # Try to find job title - usually in h1 or prominent heading
        title_tags = soup.find_all(['h1', 'h2'])
        for tag in title_tags:
            text = tag.get_text(strip=True)
            if text and len(text) < 200:  # Reasonable title length
                text_parts.append(f"Title: {text}")
                break

        # Find job description section
        # Look for sections containing "Job description", "Description", etc.
        for section in soup.find_all(['div', 'section', 'article']):
            section_text = section.get_text(' ', strip=True).lower()
            if any(keyword in section_text for keyword in ['job description', 'description', 'responsibilities']):
                # Extract the full text from this section
                full_text = section.get_text(' ', strip=True)
                if full_text and len(full_text) > 100:
                    text_parts.append(f"\nJob Description:\n{full_text}")

        # Find company information
        for section in soup.find_all(['div', 'section']):
            section_text = section.get_text(' ', strip=True).lower()
            if 'company' in section_text or 'about us' in section_text:
                full_text = section.get_text(' ', strip=True)
                if full_text and len(full_text) > 50:
                    text_parts.append(f"\nCompany:\n{full_text}")
                    break

        # Find requirements/qualifications
        for section in soup.find_all(['div', 'section', 'ul']):
            section_text = section.get_text(' ', strip=True).lower()
            if any(keyword in section_text for keyword in ['requirements', 'qualifications', 'skills', 'must have']):
                full_text = section.get_text(' ', strip=True)
                if full_text and len(full_text) > 50:
                    text_parts.append(f"\nRequirements:\n{full_text}")

        # Find benefits if present
        for section in soup.find_all(['div', 'section', 'ul']):
            section_text = section.get_text(' ', strip=True).lower()
            if 'benefits' in section_text or 'we offer' in section_text:
                full_text = section.get_text(' ', strip=True)
                if full_text and len(full_text) > 50:
                    text_parts.append(f"\nBenefits:\n{full_text}")

        # If no specific sections found, extract all visible text
        if len(text_parts) <= 2:  # Only URL and maybe title
            visible_text = self.extract_visible_text(str(soup))
            if visible_text:
                text_parts.append(f"\nFull Content:\n{visible_text}")

        # Join all parts and clean up
        text = '\n'.join(text_parts)

        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def estimate(self, mhtml_path, vacancy_url: str = None):
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
        print(f" Performing full parsing for: {mhtml_path}")
        html_content = self.open_mhtml(mhtml_path)
        text = self.html_to_formatted_text(html_content, vacancy_url)
        self.save_text(txt_path, text)

        # 6. Update config with parsing results
        config['parsed_date'] = datetime.now().isoformat()
        config['parsing_version'] = self.PARSING_VERSION
        config['vacancy_score'] = 0
        config['vacancy_url'] = vacancy_url  # Store the full URL
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

            # Try to extract URL from existing JSON config if available
            base_path = os.path.splitext(mhtml_path)[0]
            json_path = base_path + '.json'
            existing_config = self.load_config(json_path)
            vacancy_url = existing_config.get('vacancy_url') if existing_config else None

            self.estimate(mhtml_path, vacancy_url)

        print("✅ Finished estimating all vacancies.")