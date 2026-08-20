import os
import re
import json
import glob
import time
import email
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from ai_clients.start_server import start_wsl_server, stop_wsl_server
from ai_clients.TextToTextClient import TextToTextClient


class BaseVacancyEstimator:
    """
    Base class for vacancy estimators. Provides reusable methods
    for opening MHTML files, stripping tags, extracting text,
    saving results, and managing per-vacancy JSON config files.
    """

    PARSING_VERSION = 4
    ESTIMATION_VERSION = 5
    PARSING_PORTION = 50
    PROMPT_FILE = "prompts/PROMPT_SIMPLE5.txt"
    RESUME_POINTS_FILE = "prompts/voronin_resume_points.json"
    VACANCY_TIMEOUT = 60 * 20
    WARMUP_TIMEOUT = 60 * 20

    LEVEL_1_MODELS = [
        "matrixportalx/Llama-3.3-8B-Instruct-128K-Q5_K_M-GGUF|GPU|32768",
        "NikolayKozloff/gemma-3-4b-it-Q8_0-GGUF|GPU|32768",
        "rktmeister/Meta-Llama-3.1-8B-Instruct-Q5_K_M-GGUF|GPU|32768",
    ]

    LEVEL_2_MODELS = [
        "Brunobkr/OFFELLIA_Q6_K_gemma-4-26B-A4B-it-ultra-uncensored-heretic.gguf|CPU|32768",
        "majentik/gemma-4-12B-it-RotorQuant-GGUF-Q5_K_M|CPU|32768",
    ]

    # Scoring constants
    TITLE_ADJUSTMENT = 0.6
    SCORE_TITLE_EXACT = int(20 * TITLE_ADJUSTMENT)
    SCORE_TITLE_80 = int(16 * TITLE_ADJUSTMENT)
    SCORE_TITLE_60 = int(12 * TITLE_ADJUSTMENT)
    SCORE_INDUSTRY_PENALTY = -100

    PROFICIENCY_SCORE_MATRIX = {
        "expert": {"expert": 6, "required": 4, "nice-to-have": 1},
        "required": {"expert": 4, "required": 5, "nice-to-have": 1},
        "nice-to-have": {"expert": 1, "required": 1, "nice-to-have": 2},
    }

    MISSING_PENALTY = {
        "expert": -6,
        "required": -5,
        "nice-to-have": -1,
    }

    LEVEL_2_MIN_SCORE = 20

    def __init__(self):
        pass

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
        current_version = self.convert_to_int(
            config.get('parsing_version', 0)
        )
        if current_version is None or current_version < self.PARSING_VERSION:
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

    def _load_resume_points(self):
        """Load resume points JSON from RESUME_POINTS_FILE."""
        estimators_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(estimators_dir)
        resume_path = os.path.join(project_root, self.RESUME_POINTS_FILE)
        if not os.path.exists(resume_path):
            print(f"⚠️ Resume points file not found: {resume_path}")
            return {}
        try:
            with open(resume_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Could not load resume points: {e}")
            return {}

    def _get_all_known_tech_skills(self):
        """
        Get a set of all known tech skills (lowercase) from estimator_config.json.
        Includes keys from 'tech' and all items from 'synonymns'.
        """
        estimator_config = self._load_estimator_config()
        known_skills = set()

        # Tech keys
        tech_section = estimator_config.get('tech', {})
        if isinstance(tech_section, dict):
            for category, items in tech_section.items():
                if isinstance(items, dict):
                    for keyword in items.keys():
                        known_skills.add(keyword.lower())
                elif isinstance(items, list):
                    for keyword in items:
                        known_skills.add(keyword.lower())

        # Synonyms (handle typo 'synonymns' and correct 'synonyms')
        synonyms_section = estimator_config.get(
            'synonyms', estimator_config.get('synonymns', [])
        )
        if isinstance(synonyms_section, list):
            for group in synonyms_section:
                if isinstance(group, list):
                    for syn in group:
                        if isinstance(syn, str):
                            known_skills.add(syn.lower())

        return known_skills

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
        synonyms_section = config_data.get(
            'synonyms', config_data.get('synonymns', [])
        )
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

    def convert_to_int(self, text):
        if text is None:
            return None
        try:
            # Attempt to convert the string to an integer
            number = int(text)
            return number
        except ValueError:
            return None

    def update_config_with_keywords(self, config, text):
        """
        Update config with keywords, countries, and industries extracted from text.
        Only updates if parsing_version is less than current PARSING_VERSION.
        """
        estimator_config = self._load_estimator_config()
        if not estimator_config:
            return config

        keywords_list, countries_list, industries_list = (
            self._extract_keywords_from_config(estimator_config)
        )

        matched_keywords = self._find_matches_in_text(text, keywords_list)
        matched_countries = self._find_matches_in_text(text, countries_list)
        matched_industries = self._find_matches_in_text(text, industries_list)

        config['keywords'] = matched_keywords
        config['countries'] = matched_countries
        config['industries'] = matched_industries
        config['parsing_version'] = str(self.PARSING_VERSION)

        return config

    # ------------------------------------------------------------------
    # Main entry point (to be overridden by subclasses)
    # ------------------------------------------------------------------
    def estimate(self, mhtml_path, url: str):
        """
        Main estimation method. Subclasses must implement this.
        """
        raise NotImplementedError("Subclasses must implement estimate()")

    # ------------------------------------------------------------------
    # AI estimation helpers
    # ------------------------------------------------------------------
    def _parse_json_safely(self, text):
        """
        Try to parse JSON from text. Attempts direct parse first,
        then extracts from markdown code blocks, then finds first
        balanced { ... } block. Returns parsed dict or None.
        """
        if not text or not isinstance(text, str):
            return None
        text = text.strip()

        # 1. Direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Extract from ```json ... ``` or ``` ... ``` block
        match = re.search(
            r'```(?:json)?\s*(\{.*?\})\s*```',
            text, re.DOTALL | re.IGNORECASE
        )
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # 3. Find first balanced { ... } block
        start = text.find('{')
        if start != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except (json.JSONDecodeError, ValueError):
                            break
        return None

    def _read_vacancy_text(self, txt_path):
        """Read vacancy text from a .txt file."""
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (IOError, OSError) as e:
            print(f"⚠️ Could not read {txt_path}: {e}")
            return ""

    def _load_prompt(self):
        """Load prompt text from PROMPT_FILE relative to project root."""
        estimators_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(estimators_dir)
        prompt_path = os.path.join(project_root, self.PROMPT_FILE)
        if not os.path.exists(prompt_path):
            print(f"⚠️ Prompt file not found: {prompt_path}")
            return None
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (IOError, OSError) as e:
            print(f"⚠️ Could not read prompt file: {e}")
            return None

    def _warmup_model(self, client, model_id):
        """Send a simple ping to warm up the model with up to 5 retries."""
        start_time = time.time()
        max_retries = 5

        for attempt in range(1, max_retries + 1):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  🔥 [{ts}] Warming up {model_id} (Attempt {attempt}/{max_retries})")
            try:
                client.generate(
                    model_id, "2+2",
                    model_limit_seconds=self.WARMUP_TIMEOUT
                )
                duration = time.time() - start_time
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"  ✅ [{ts}] Warmup done in {duration:.2f}s")
                return
            except Exception as e:
                print(f"  ⚠️ Warmup failed on attempt {attempt}: {e}")
                if attempt < max_retries:
                    print("  🔄 Restarting server and waiting 30 seconds before retrying...")
                    try:
                        stop_wsl_server()
                    except Exception as stop_e:
                        print(f"  ⚠️ Error stopping server: {stop_e}")
                    time.sleep(30)
                    try:
                        start_wsl_server()
                    except Exception as start_e:
                        print(f"  ⚠️ Error starting server: {start_e}")
                    time.sleep(30)
                else:
                    print(f"  ❌ Warmup failed after {max_retries} attempts. Exiting.")
                    sys.exit(1)

    def _apply_prompt_to_vacancy(
            self, client, model_id, prompt_text, vacancy_text
    ):
        """
        Apply prompt to one vacancy with one model.
        Handles context window exceeded errors by reducing prompt size.
        Returns dict with success, duration, prompt_size, generated_text,
        parsed_json, and optional error.
        """
        full_prompt = prompt_text + "\n" + vacancy_text
        original_prompt_size = len(full_prompt)
        vacancy_size = len(vacancy_text)

        max_retries = 10
        current_prompt = full_prompt
        total_start_time = time.time()
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = client.generate(
                    model_id, current_prompt,
                    model_limit_seconds=self.VACANCY_TIMEOUT
                )
                generated_text = response.get("generated_text", "")
                if not isinstance(generated_text, str):
                    generated_text = str(generated_text)
                duration = time.time() - total_start_time
                parsed = self._parse_json_safely(generated_text)

                # If the generation run is successful (no exception),
                # we consider it a success and use its data.
                return {
                    'success': True,
                    'duration': duration,
                    'prompt_size': original_prompt_size,
                    'vacancy_size': vacancy_size,
                    'generated_text': generated_text,
                    'parsed_json': parsed,
                    'error': None
                }
            except Exception as e:
                error_str = str(e)
                last_error = error_str

                # Check if it's a context window exceeded error
                if "exceed context window" in error_str or "Requested tokens" in error_str:
                    if attempt == 0:
                        # First retry: reduce to 64K
                        new_size = 64000
                    else:
                        # Subsequent retries: reduce by 5%
                        new_size = int(len(current_prompt) * 0.95)

                    if new_size < 1000:
                        break

                    current_prompt = current_prompt[:new_size]
                    print(
                        f"  ⚠️ Context window exceeded. Reducing prompt to {len(current_prompt)} chars and retrying (Attempt {attempt + 1}/{max_retries})...")
                    continue
                else:
                    # Not a context window error, fail immediately
                    break

        duration = time.time() - total_start_time
        return {
            'success': False,
            'duration': duration,
            'prompt_size': original_prompt_size,
            'vacancy_size': vacancy_size,
            'generated_text': '',
            'parsed_json': None,
            'error': last_error
        }

    def _apply_model_to_vacancies(
            self, client, model_id, vacancies, prompt_text
    ):
        """
        Apply one model to a list of vacancies in sequence.
        Returns list of result dicts, one per vacancy.
        """
        results = []
        for v in vacancies:
            vid = v['vacancy_id']
            print(f"  📄 Vacancy {vid} -> {model_id}")
            try:
                vacancy_text = self._read_vacancy_text(v['txt_path'])
                if not vacancy_text:
                    results.append({
                        'vacancy_id': vid,
                        'txt_name': v['txt_name'],
                        'model_id': model_id,
                        'success': False,
                        'duration': 0.0,
                        'prompt_size': 0,
                        'vacancy_size': 0,
                        'error': 'empty_text'
                    })
                    print(f"    ❌ Time: 0.00s | Error: empty_text")
                    continue

                result = self._apply_prompt_to_vacancy(
                    client, model_id, prompt_text, vacancy_text
                )
                result['vacancy_id'] = vid
                result['txt_name'] = v['txt_name']
                result['model_id'] = model_id
                results.append(result)

                status = "✅" if result['success'] else "❌"
                err = f" | Error: {result['error']}" if result['error'] else ""
                print(
                    f"    {status} Time: {result['duration']:.2f}s | "
                    f"Prompt: {result['prompt_size']} chars | "
                    f"Vacancy: {result['vacancy_size']} chars{err}"
                )
            except Exception as e:
                print(f"    ❌ Error processing vacancy {vid}: {e}")
                results.append({
                    'vacancy_id': vid,
                    'txt_name': v.get('txt_name', ''),
                    'model_id': model_id,
                    'success': False,
                    'duration': 0.0,
                    'prompt_size': 0,
                    'vacancy_size': 0,
                    'error': str(e)
                })
        return results

    def _apply_level_models_to_vacancies(
            self, client, models, vacancies, prompt_text, level_name
    ):
        """
        Apply a list of models (one level) to vacancies.
        Tries first model on all vacancies; if any fail, tries the next
        model on failed ones only. Stops when all succeed or models
        are exhausted.
        Returns (all_results, successful_vacancies, failed_vacancies,
                 level_time, model_times).
        """
        print(f"\n{'=' * 70}")
        print(f"🎯 {level_name} - {len(vacancies)} vacancies, "
              f"{len(models)} model(s)")
        print(f"{'=' * 70}")

        all_results = []
        model_times = {}
        remaining = list(vacancies)
        successful = []
        level_start = time.time()

        for model_id in models:
            if not remaining:
                break
            print(f"\n🔄 Model: {model_id}")
            print(f"   Vacancies to process: {len(remaining)}")
            self._warmup_model(client, model_id)

            model_start = time.time()
            results = self._apply_model_to_vacancies(
                client, model_id, remaining, prompt_text
            )
            model_duration = time.time() - model_start
            model_times[model_id] = model_duration
            all_results.extend(results)

            # Split into successful and still-failed
            new_remaining = []
            for r, v in zip(results, remaining):
                if r['success']:
                    successful.append(v)
                else:
                    new_remaining.append(v)

            succeeded_this_round = len(remaining) - len(new_remaining)
            print(
                f"\n--- {level_name} Model Summary: "
                f"{model_id} ---"
            )
            print(
                f"  Succeeded: {succeeded_this_round}/{len(remaining)} | "
                f"Model Time: {model_duration:.2f}s"
            )

            remaining = new_remaining

            if not remaining:
                print(
                    f"\n✅ All vacancies succeeded with {model_id}. "
                    f"Stopping {level_name}."
                )
                break

        level_time = time.time() - level_start

        if remaining:
            print(
                f"\n⚠️ {len(remaining)} vacancy(ies) still failed "
                f"after all {level_name} models."
            )

        return all_results, successful, remaining, level_time, model_times

    def _print_level_summary(
            self, level_name, all_results, successful, failed, level_time
    ):
        """Print summary table for a level: each vacancy with its result."""
        print(f"\n{'=' * 70}")
        print(f"📊 {level_name} SUMMARY")
        print(f"{'=' * 70}")
        header = (
            f"{'Vacancy':<15} | {'Model':<45} | "
            f"{'Score':>6} | {'Pct':>5} | {'Time':>8} | Status"
        )
        print(header)
        print("-" * 70)

        # Group results by vacancy_id, show the successful one (or last)
        by_vacancy = {}
        for r in all_results:
            vid = r['vacancy_id']
            by_vacancy.setdefault(vid, []).append(r)

        for vid, results in by_vacancy.items():
            # Pick the successful result if any, otherwise the last one
            successful_r = next((r for r in results if r['success']), None)
            display_r = successful_r if successful_r else results[-1]
            model_short = display_r['model_id']
            if len(model_short) > 45:
                model_short = "..." + model_short[-42:]
            status = "✅" if display_r['success'] else "❌"
            score_str = f"{display_r.get('score', 0):>6}"
            pct_str = f"{display_r.get('score_percentile', 0.0):>5.2f}"
            print(
                f"{vid:<15} | {model_short:<45} | "
                f"{score_str} | {pct_str} | {display_r['duration']:>7.2f}s | {status}"
            )

        print("-" * 70)
        print(
            f"Total {level_name}: {len(successful)} succeeded, "
            f"{len(failed)} failed | Time: {level_time:.2f}s"
        )

    def _print_model_usage_table(self, level_name, all_results, model_times):
        """Print table of total time and usage per model."""
        print(f"\n📈 {level_name} - Model Usage")
        print("-" * 70)
        print(f"{'Model':<55} | {'Time':>8} | Calls")
        print("-" * 70)

        # Aggregate per model
        by_model = {}
        for r in all_results:
            mid = r['model_id']
            if mid not in by_model:
                by_model[mid] = {'count': 0, 'success': 0, 'time': 0.0}
            by_model[mid]['count'] += 1
            by_model[mid]['time'] += r['duration']
            if r['success']:
                by_model[mid]['success'] += 1

        for mid, stats in by_model.items():
            total_time = model_times.get(mid, stats['time'])
            model_short = mid if len(mid) <= 55 else "..." + mid[-52:]
            print(
                f"{model_short:<55} | {total_time:>7.2f}s | "
                f"{stats['success']}/{stats['count']}"
            )
        print("-" * 70)

    def _print_unknown_skills_summary(self, level_name, all_results):
        """
        Print unknown skills summary grouped by skill, showing how many
        vacancies were missing each skill.
        """
        print(f"\n{'=' * 70}")
        print(f"🔍 {level_name} - UNKNOWN SKILLS (grouped by skill)")
        print(f"{'=' * 70}")
        skill_counts = {}
        for r in all_results:
            if r.get('unknown_skills'):
                for skill, level in r['unknown_skills']:
                    key = f"{skill} ({level})"
                    skill_counts[key] = skill_counts.get(key, 0) + 1

        if skill_counts:
            # Sort by count descending, then alphabetically
            sorted_skills = sorted(
                skill_counts.items(), key=lambda x: (-x[1], x[0])
            )
            for skill_key, count in sorted_skills:
                print(f"  {skill_key}: {count} vacancy(ies)")
            print(f"\nTotal unique unknown skills: {len(skill_counts)}")
        else:
            print("  No unknown skills found.")
        print("-" * 70)

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    def _levenshtein_ratio(self, s1, s2):
        """
        Calculate Levenshtein similarity ratio between two strings.
        Returns value in [0, 1] where 1 means identical.
        Comparison is case-insensitive.
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        s1, s2 = s1.lower(), s2.lower()
        len1, len2 = len(s1), len(s2)

        # Create distance matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost
                )

        distance = matrix[len1][len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len) if max_len > 0 else 1.0

    def _build_synonym_map(self):
        """
        Build a mapping synonym (lowercase) -> canonical (first item in group).
        Used to normalize skill names so that e.g. 'Transact-SQL' and
        'Transact SQL' both become 'T-SQL'.
        """
        estimator_config = self._load_estimator_config()
        synonyms_section = estimator_config.get(
            'synonyms', estimator_config.get('synonymns', [])
        )
        synonym_map = {}
        if isinstance(synonyms_section, list):
            for group in synonyms_section:
                if isinstance(group, list) and len(group) > 0:
                    canonical = group[0]
                    for syn in group:
                        if isinstance(syn, str):
                            synonym_map[syn.lower()] = canonical
        return synonym_map

    def _normalize_by_synonyms(self, items, synonym_map):
        """
        Normalize a list of skill names using the synonym map.
        Each item is replaced by the canonical (first) synonym if found.
        Comparison is case-insensitive.
        """
        if not items:
            return []
        normalized = []
        for item in items:
            if not isinstance(item, str):
                continue
            item_lower = item.strip().lower()
            if item_lower in synonym_map:
                normalized.append(synonym_map[item_lower])
            else:
                normalized.append(item.strip())
        return normalized

    def _calculate_score(self, vacancy_json, resume_json, known_tech_skills):
        """
        Calculate score for a generated vacancy JSON against the resume
        points JSON. Returns (score, protocol_entries, unknown_skills) where
        protocol_entries is a list of dicts explaining each point addition or
        subtraction, and unknown_skills is a list of (skill, level) tuples
        for skills not found in resume or known tech skills.
        """
        protocol_entries = []
        unknown_skills = []
        score = 0
        synonym_map = self._build_synonym_map()

        # --- Title matching ---
        vacancy_title = (vacancy_json.get('Title') or '').strip()
        resume_titles = resume_json.get('Title', []) or []
        title_matched = False
        for rt in resume_titles:
            if not isinstance(rt, str):
                continue
            ratio = self._levenshtein_ratio(vacancy_title, rt)
            if ratio >= 1.0:
                points = self.SCORE_TITLE_EXACT
                score += points
                protocol_entries.append({
                    "left": vacancy_title,
                    "left_field": "Title",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": rt,
                    "right_field": "Title",
                    "msg": f"+{points} points vacancy title exact match: '{vacancy_title}' vs '{rt}'"
                })
                title_matched = True
                break
            elif ratio >= 0.8:
                points = self.SCORE_TITLE_80
                score += points
                protocol_entries.append({
                    "left": vacancy_title,
                    "left_field": "Title",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": rt,
                    "right_field": "Title",
                    "msg": f"+{points} points vacancy title 80% match ({int(ratio * 100)}%): '{vacancy_title}' vs '{rt}'"
                })
                title_matched = True
                break
            elif ratio >= 0.6:
                points = self.SCORE_TITLE_60
                score += points
                protocol_entries.append({
                    "left": vacancy_title,
                    "left_field": "Title",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": rt,
                    "right_field": "Title",
                    "msg": f"+{points} points vacancy title 60% match ({int(ratio * 100)}%): '{vacancy_title}' vs '{rt}'"
                })
                title_matched = True
                break

        if not title_matched and vacancy_title:
            protocol_entries.append({
                "left": vacancy_title,
                "left_field": "Title",
                "score": 0,
                "score_percentile": 0.0,
                "right": "",
                "right_field": "Title",
                "msg": f"+0 points vacancy title no match: '{vacancy_title}'"
            })

        # --- CompanyNoIndustry penalty ---
        vacancy_industry = (
                vacancy_json.get('CompanyIndustry') or ''
        ).strip()
        no_industries = resume_json.get('CompanyNoIndustry', []) or []
        for ni in no_industries:
            if not isinstance(ni, str):
                continue
            ratio = self._levenshtein_ratio(vacancy_industry, ni)
            if ratio >= 0.9:
                points = self.SCORE_INDUSTRY_PENALTY
                score += points
                protocol_entries.append({
                    "left": vacancy_industry,
                    "left_field": "CompanyIndustry",
                    "score": points,
                    "score_percentile": 0.0,
                    "right": ni,
                    "right_field": "CompanyNoIndustry",
                    "msg": f"{points} points company industry matches CompanyNoIndustry ({int(ratio * 100)}%): '{vacancy_industry}' vs '{ni}'"
                })
                break

        # --- Skills matching (expert / required / nice-to-have) ---
        levels = ["expert", "required", "nice-to-have"]
        vacancy_by_level = {}
        resume_by_level = {}
        for level in levels:
            vacancy_by_level[level] = set(
                s.lower() for s in self._normalize_by_synonyms(
                    vacancy_json.get(level, []) or [], synonym_map
                )
            )
            resume_by_level[level] = set(
                s.lower() for s in self._normalize_by_synonyms(
                    resume_json.get(level, []) or [], synonym_map
                )
            )

        # Collect all vacancy skills with their level
        all_vacancy_skills = {}
        for level in levels:
            for skill in vacancy_by_level[level]:
                if skill not in all_vacancy_skills:
                    all_vacancy_skills[skill] = level

        for v_skill, v_level in all_vacancy_skills.items():
            # Find which level it's at in resume
            r_level = None
            for level in levels:
                if v_skill in resume_by_level[level]:
                    r_level = level
                    break

            if r_level is not None:
                points = self.PROFICIENCY_SCORE_MATRIX[v_level][r_level]
                score += points
                protocol_entries.append({
                    "left": v_skill,
                    "left_field": v_level,
                    "score": points,
                    "score_percentile": 0.0,
                    "right": v_skill,
                    "right_field": r_level,
                    "msg": f"+{points} points vacancy '{v_skill}' {v_level} vs resume '{v_skill}' {r_level}"
                })
            else:
                # Skill not in resume. Check if it's a known tech skill.
                if v_skill in known_tech_skills:
                    points = self.MISSING_PENALTY[v_level]
                    score += points
                    protocol_entries.append({
                        "left": v_skill,
                        "left_field": v_level,
                        "score": points,
                        "score_percentile": 0.0,
                        "missing": v_skill,
                        "right_field": "missing",
                        "msg": f"{points} points vacancy '{v_skill}' {v_level} does not exist in resume json"
                    })
                else:
                    # Unknown skill: no penalty, just collect it
                    unknown_skills.append((v_skill, v_level))
                    protocol_entries.append({
                        "left": v_skill,
                        "left_field": v_level,
                        "score": 0,
                        "score_percentile": 0.0,
                        "missing": v_skill,
                        "right_field": "unknown",
                        "msg": f"0 points vacancy '{v_skill}' {v_level} is unknown (not in tech/synonyms), no penalty"
                    })

        # Calculate score_percentile for each entry
        total_abs_score = sum(abs(e['score']) for e in protocol_entries)
        for entry in protocol_entries:
            if total_abs_score > 0:
                entry['score_percentile'] = round(entry['score'] / total_abs_score, 2)
            else:
                entry['score_percentile'] = 0.0

        return score, protocol_entries, unknown_skills

    def _save_estimation_result(
            self, vacancy, estimation_tag, model_id, parsed_json,
            score, score_percentile, protocol
    ):
        """
        Save estimation result into the vacancy's JSON config file.
        estimation_tag is 'estimation1' or 'estimation2'.
        """
        config = self.load_config(vacancy['json_path'])
        if config is None:
            config = {}
        config[estimation_tag] = {
            'model_id': model_id,
            'score': score,
            'score_percentile': score_percentile,
            'json': parsed_json,
            'scoring_protocol': protocol,
        }
        config['estimation_version'] = str(self.ESTIMATION_VERSION)
        self.save_config(vacancy['json_path'], config)

    # ------------------------------------------------------------------
    # AI estimation main entry point
    # ------------------------------------------------------------------
    def AI_estimate_collected(self, folder):
        """
        Main AI estimation entry point.
        1. Select vacancies where txt+json exist, parsing_version matches,
           and estimation_version is missing or < ESTIMATION_VERSION.
        2. Apply level 1 models in sequence until all succeed.
        3. Score each vacancy and save estimation1 to json.
        4. Apply level 2 models only on vacancies with score >= 20 or percentile >= 0.5.
        5. Save estimation2 to json.
        6. Print summaries and statistics.
        7. Save bulk JSON chunk.
        """
        print(f"\n{'#' * 70}")
        print(f"# Starting AI estimation for {folder}")
        print(f"{'#' * 70}")

        resume_json = self._load_resume_points()
        if not resume_json:
            print("⚠️ Could not load resume points. Aborting.")
            return None

        known_tech_skills = self._get_all_known_tech_skills()

        # 1. Select valid files
        valid_files = []
        json_files = glob.glob(os.path.join(folder, '*.json'))
        for json_path in json_files:
            txt_path = os.path.splitext(json_path)[0] + '.txt'
            if not os.path.exists(txt_path):
                continue

            config = self.load_config(json_path)
            if config is None:
                continue

            current_version = self.convert_to_int(
                config.get('parsing_version', 0)
            )
            if current_version != self.PARSING_VERSION:
                continue

            est_version = self.convert_to_int(
                config.get('estimation_version', 0)
            )
            if est_version is not None and est_version >= self.ESTIMATION_VERSION:
                continue

            saved_date_str = config.get('saved_date', '1900-01-01')
            try:
                saved_date = datetime.fromisoformat(saved_date_str)
            except (ValueError, TypeError):
                saved_date = datetime(1900, 1, 1)

            filename = os.path.basename(json_path)
            match = re.search(r'(\d+)', filename)
            vacancy_id = match.group(1) if match else filename
            txt_size = os.path.getsize(txt_path)

            valid_files.append({
                'vacancy_id': vacancy_id,
                'saved_date': saved_date,
                'saved_date_str': saved_date_str,
                'txt_name': os.path.basename(txt_path),
                'txt_path': txt_path,
                'txt_size': txt_size,
                'json_name': filename,
                'json_path': json_path
            })

        # Sort by saved_date descending (latest first) and take portion
        valid_files.sort(key=lambda x: x['saved_date'], reverse=True)
        selected_files = valid_files[:self.PARSING_PORTION]

        print(f"\n📋 Selected {len(selected_files)} vacancies "
              f"(portion of {self.PARSING_PORTION}):")
        for f in selected_files:
            print(
                f"  vacancyId: {f['vacancy_id']}, "
                f"saved_date: {f['saved_date_str']}, "
                f"txt: {f['txt_name']} ({f['txt_size']} bytes), "
                f"json: {f['json_name']}"
            )

        if not selected_files:
            print("⚠️ No valid vacancies selected. Aborting.")
            return None

        # 2. Load prompt
        prompt_text = self._load_prompt()
        if prompt_text is None:
            print("⚠️ Could not load prompt. Aborting.")
            return None
        print(f"\n📝 Loaded prompt: {self.PROMPT_FILE} "
              f"({len(prompt_text)} chars)")

        # 3. Start server
        print("\n🚀 Starting AI server...")
        start_wsl_server()
        time.sleep(5)
        client = TextToTextClient()

        overall_start = time.time()
        result_data = {
            'vacancies': selected_files,
            'level1': None,
            'level2': None,
            'total_time': 0.0
        }

        try:
            # 4. Level 1 estimation
            l1_results, l1_success, l1_failed, l1_time, l1_model_times = (
                self._apply_level_models_to_vacancies(
                    client, self.LEVEL_1_MODELS, selected_files,
                    prompt_text, "LEVEL 1"
                )
            )

            # Score each vacancy and save estimation1 to json
            l1_by_vacancy = {}
            for r in l1_results:
                if r['success']:
                    parsed = r.get('parsed_json') or {}
                    score, protocol, unknown = self._calculate_score(
                        parsed, resume_json, known_tech_skills
                    )

                    total_abs = sum(abs(e['score']) for e in protocol)
                    if total_abs > 0:
                        vacancy_pct = round(score / total_abs, 2)
                    else:
                        vacancy_pct = 0.0

                    r['score'] = score
                    r['score_percentile'] = vacancy_pct
                    r['protocol'] = protocol
                    r['unknown_skills'] = unknown

                    # Find corresponding vacancy
                    v = next(
                        (v for v in selected_files
                         if v['vacancy_id'] == r['vacancy_id']),
                        None
                    )
                    if v:
                        self._save_estimation_result(
                            v, 'estimation1', r['model_id'],
                            parsed, score, vacancy_pct, protocol
                        )
                    l1_by_vacancy[r['vacancy_id']] = r
                else:
                    r['score'] = 0
                    r['score_percentile'] = 0.0
                    r['protocol'] = [{"msg": f"Generation failed: {r.get('error')}"}]
                    r['unknown_skills'] = []

            self._print_level_summary(
                "LEVEL 1", l1_results, l1_success, l1_failed, l1_time
            )
            self._print_model_usage_table(
                "LEVEL 1", l1_results, l1_model_times
            )
            self._print_unknown_skills_summary("LEVEL 1", l1_results)

            result_data['level1'] = {
                'results': l1_results,
                'successful_vacancies': l1_success,
                'failed_vacancies': l1_failed,
                'total_time': l1_time,
                'model_times': l1_model_times
            }

            # 5. Level 2 estimation - only on vacancies with score >= 20 OR score_percentile >= 0.5
            l2_candidates = [
                v for v in l1_success
                if l1_by_vacancy.get(v['vacancy_id'], {}).get('score', 0) >= self.LEVEL_2_MIN_SCORE
                   or l1_by_vacancy.get(v['vacancy_id'], {}).get('score_percentile', 0.0) >= 0.5
            ]
            l2_skipped = [
                v for v in l1_success
                if l1_by_vacancy.get(v['vacancy_id'], {}).get('score', 0) < self.LEVEL_2_MIN_SCORE
                   and l1_by_vacancy.get(v['vacancy_id'], {}).get('score_percentile', 0.0) < 0.5
            ]

            # Save estimation2 for skipped vacancies (level1 too low)
            for v in l2_skipped:
                l1_score = l1_by_vacancy[v['vacancy_id']]['score']
                l1_pct = l1_by_vacancy[v['vacancy_id']]['score_percentile']
                protocol = [{
                    "left": "N/A",
                    "left_field": "N/A",
                    "score": 0,
                    "score_percentile": 0.0,
                    "right_field": "missing",
                    "msg": f"Level 2 not started: level 1 score {l1_score} (pct: {l1_pct}) is below minimum {self.LEVEL_2_MIN_SCORE} or 0.5"
                }]
                self._save_estimation_result(
                    v, 'estimation2', None, None, 0, 0.0, protocol
                )

            if l2_candidates:
                print(
                    f"\n🎯 {len(l2_candidates)} vacancy(ies) qualify "
                    f"for LEVEL 2 (score >= {self.LEVEL_2_MIN_SCORE} or pct >= 0.5). "
                    f"{len(l2_skipped)} skipped (level 1 too low)."
                )
                l2_results, l2_success, l2_failed, l2_time, l2_model_times = (
                    self._apply_level_models_to_vacancies(
                        client, self.LEVEL_2_MODELS, l2_candidates,
                        prompt_text, "LEVEL 2"
                    )
                )

                # Score and save estimation2
                for r in l2_results:
                    if r['success']:
                        parsed = r.get('parsed_json') or {}
                        score, protocol, unknown = self._calculate_score(
                            parsed, resume_json, known_tech_skills
                        )

                        total_abs = sum(abs(e['score']) for e in protocol)
                        if total_abs > 0:
                            vacancy_pct = round(score / total_abs, 2)
                        else:
                            vacancy_pct = 0.0

                        r['score'] = score
                        r['score_percentile'] = vacancy_pct
                        r['protocol'] = protocol
                        r['unknown_skills'] = unknown

                        v = next(
                            (v for v in l2_candidates
                             if v['vacancy_id'] == r['vacancy_id']),
                            None
                        )
                        if v:
                            self._save_estimation_result(
                                v, 'estimation2', r['model_id'],
                                parsed, score, vacancy_pct, protocol
                            )
                    else:
                        r['score'] = 0
                        r['score_percentile'] = 0.0
                        r['protocol'] = [{"msg": f"Generation failed: {r.get('error')}"}]
                        r['unknown_skills'] = []

                self._print_level_summary(
                    "LEVEL 2", l2_results, l2_success, l2_failed, l2_time
                )
                self._print_model_usage_table(
                    "LEVEL 2", l2_results, l2_model_times
                )
                self._print_unknown_skills_summary("LEVEL 2", l2_results)

                result_data['level2'] = {
                    'results': l2_results,
                    'successful_vacancies': l2_success,
                    'failed_vacancies': l2_failed,
                    'total_time': l2_time,
                    'model_times': l2_model_times
                }
            else:
                print(
                    f"\n⚠️ No vacancies qualify for LEVEL 2 "
                    f"(all level 1 scores < {self.LEVEL_2_MIN_SCORE} and pct < 0.5)."
                )
                result_data['level2'] = {
                    'results': [],
                    'successful_vacancies': [],
                    'failed_vacancies': [],
                    'total_time': 0.0,
                    'model_times': {}
                }

        finally:
            # 6. Stop server
            print("\n🛑 Stopping AI server...")
            stop_wsl_server()

        # 7. Final summary
        overall_time = time.time() - overall_start
        result_data['total_time'] = overall_time

        print(f"\n{'#' * 70}")
        print(f"# FINAL TIME SUMMARY")
        print(f"{'#' * 70}")
        l1_t = (
            result_data['level1']['total_time']
            if result_data['level1'] else 0.0
        )
        l2_t = (
            result_data['level2']['total_time']
            if result_data['level2'] else 0.0
        )
        print(f"  LEVEL 1 time: {l1_t:>10.2f}s")
        print(f"  LEVEL 2 time: {l2_t:>10.2f}s")
        print(f"  {'-' * 40}")
        print(f"  Total time:   {overall_time:>10.2f}s")
        print(f"{'#' * 70}")

        # 8. Save bulk JSON chunk
        chunks_dir = os.path.join(os.path.dirname(folder), 'Chunks')
        os.makedirs(chunks_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        chunk_filename = f"linkedin_bulk_jsons_{len(selected_files)}_{timestamp}.json"
        chunk_filepath = os.path.join(chunks_dir, chunk_filename)

        chunk_data = {}
        for v in selected_files:
            vid = v['vacancy_id']
            json_path = v['json_path']
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                chunk_data[vid] = data
            except Exception as e:
                chunk_data[vid] = {
                    "error": f"json for vacancy {os.path.basename(json_path)} was faulty: {str(e)}"
                }

        with open(chunk_filepath, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved bulk JSON chunk to: {chunk_filepath}")

        return result_data