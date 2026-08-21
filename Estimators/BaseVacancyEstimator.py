import os
import re
import json
import glob
import time
import email
from datetime import datetime
from bs4 import BeautifulSoup
from Estimators.AI_Helper import AI_Helper
from Estimators.VacancyScoring import VacancyScoring
from Estimators.ChunkHelper import ChunkHelper

class BaseVacancyEstimator:
    """
    Base class for vacancy estimators. Provides reusable methods
    for opening MHTML files, stripping tags, extracting text,
    saving results, and managing per-vacancy JSON config files.
    """
    PARSING_VERSION = 4
    ESTIMATION_VERSION = 6
    PARSING_PORTION = 100

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # MHTML handling
    # ------------------------------------------------------------------
    def open_mhtml(self, file_path):
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
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup.find_all(tags_to_remove):
            tag.decompose()
        return str(soup)

    def remove_hidden_elements(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            tag.decompose()
        for tag in soup.find_all(hidden=True):
            tag.decompose()
        return str(soup)

    def extract_visible_text(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        text = re.sub(r'\n{3,}', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    def save_text(self, file_path, text):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✅ Successfully saved text to: {file_path}")

    # ------------------------------------------------------------------
    # Config (JSON) management
    # ------------------------------------------------------------------
    def load_config(self, json_path):
        if not os.path.exists(json_path):
            return None
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Could not load config from {json_path}: {e}")
            return None

    def save_config(self, json_path, config):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved config to: {json_path}")

    def should_parse(self, json_path):
        config = self.load_config(json_path)
        if config is None:
            return True
        current_version = self.convert_to_int(config.get('parsing_version', 0))
        if current_version is None or current_version < self.PARSING_VERSION:
            return True
        return False

    def create_initial_config(self, saved_date=None):
        return {
            'saved_date': saved_date or datetime.now().isoformat(),
            'parsed_date': None,
            'parsing_version': None,
            'vacancy_score': 0
        }

    def _load_estimator_config(self):
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
        estimators_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(estimators_dir)
        resume_path = os.path.join(project_root, "prompts/voronin_resume_points.json")
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
        estimator_config = self._load_estimator_config()
        known_skills = set()
        tech_section = estimator_config.get('tech', {})
        if isinstance(tech_section, dict):
            for category, items in tech_section.items():
                if isinstance(items, dict):
                    for keyword in items.keys():
                        known_skills.add(keyword.lower())
                elif isinstance(items, list):
                    for keyword in items:
                        known_skills.add(keyword.lower())
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
        keywords = set()
        countries = set()
        industries = set()
        tech_section = config_data.get('tech', {})
        if isinstance(tech_section, dict):
            for category, items in tech_section.items():
                if isinstance(items, dict):
                    for keyword in items.keys():
                        keywords.add(keyword)
                elif isinstance(items, list):
                    for keyword in items:
                        keywords.add(keyword)
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
        found = set()
        text_lower = text.lower()
        sorted_keywords = sorted(keywords, key=lambda x: -len(x))
        for keyword in sorted_keywords:
            keyword_lower = keyword.lower()
            escaped_keyword = re.escape(keyword_lower)
            pattern_str = escaped_keyword.replace(r'\ ', r'\s+')
            pattern = r'\b' + pattern_str + r'\b'
            if re.search(pattern, text_lower):
                found.add(keyword)
        return sorted(found)

    def convert_to_int(self, text):
        if text is None:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def update_config_with_keywords(self, config, text):
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
        raise NotImplementedError("Subclasses must implement estimate()")

    # ------------------------------------------------------------------
    # AI estimation main entry point
    # ------------------------------------------------------------------
    def AI_estimate_collected(self, folder):
        print(f"\n{'#' * 70}")
        print(f"# Starting AI estimation for {folder}")
        print(f"{'#' * 70}")
        resume_json = self._load_resume_points()
        if not resume_json:
            print("⚠️ Could not load resume points. Aborting.")
            return None
        estimator_config = self._load_estimator_config()
        known_tech_skills = self._get_all_known_tech_skills()
        valid_files = []
        json_files = glob.glob(os.path.join(folder, '*.json'))
        for json_path in json_files:
            txt_path = os.path.splitext(json_path)[0] + '.txt'
            html_path = os.path.splitext(json_path)[0] + '.html'
            if not os.path.exists(txt_path):
                continue
            config = self.load_config(json_path)
            if config is None:
                continue
            current_version = self.convert_to_int(config.get('parsing_version', 0))
            if current_version != self.PARSING_VERSION:
                continue
            est_version = self.convert_to_int(config.get('estimation_version', 0))
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
                'json_path': json_path,
                'html_path': html_path
            })
        valid_files.sort(key=lambda x: x['saved_date'], reverse=True)
        selected_files = valid_files[:self.PARSING_PORTION]
        print(f"\n📋 Selected {len(selected_files)} vacancies (portion of {self.PARSING_PORTION}):")
        for f in selected_files:
            print(
                f"  vacancyId: {f['vacancy_id']}, saved_date: {f['saved_date_str']}, txt: {f['txt_name']} ({f['txt_size']} bytes), json: {f['json_name']}")
        if not selected_files:
            print("⚠️ No valid vacancies selected. Aborting.")
            return None
        ai_helper = AI_Helper()
        vacancy_scoring = VacancyScoring(
            resume_json=resume_json,
            known_tech_skills=known_tech_skills,
            estimator_config=estimator_config,
            estimation_version=self.ESTIMATION_VERSION,
            load_config_func=self.load_config,
            save_config_func=self.save_config
        )
        overall_start = time.time()
        result_data = {
            'vacancies': selected_files,
            'level1': None,
            'level2': None,
            'total_time': 0.0
        }
        try:
            l1_results, l1_success, l1_failed, l1_time, l1_model_times = (
                ai_helper._apply_level_models_to_vacancies(
                    selected_files, level_n=1, level_name="LEVEL 1"
                )
            )
            l1_by_vacancy = {}
            for r in l1_results:
                if r['success']:
                    parsed = r.get('parsed_json') or {}
                    score, protocol, unknown = vacancy_scoring.calculate_score(parsed)
                    total_abs = sum(abs(e['score']) for e in protocol)
                    vacancy_pct = round(score / total_abs, 2) if total_abs > 0 else 0.0
                    r['score'] = score
                    r['score_percentile'] = vacancy_pct
                    r['protocol'] = protocol
                    r['unknown_skills'] = unknown
                    v = next((v for v in selected_files if v['vacancy_id'] == r['vacancy_id']), None)
                    if v:
                        vacancy_scoring.save_estimation_result(v, 'estimation1', r['model_id'], parsed, score,
                                                               vacancy_pct, protocol)
                    l1_by_vacancy[r['vacancy_id']] = r
                else:
                    r['score'] = 0
                    r['score_percentile'] = 0.0
                    r['protocol'] = [{"msg": f"Generation failed: {r.get('error')}"}]
                    r['unknown_skills'] = []
            ai_helper._print_level_summary("LEVEL 1", l1_results, l1_success, l1_failed, l1_time)
            ai_helper._print_model_usage_table("LEVEL 1", l1_results, l1_model_times)
            ai_helper._print_unknown_skills_summary("LEVEL 1", l1_results)
            result_data['level1'] = {
                'results': l1_results,
                'successful_vacancies': l1_success,
                'failed_vacancies': l1_failed,
                'total_time': l1_time,
                'model_times': l1_model_times
            }
            l2_candidates = [
                v for v in l1_success
                if l1_by_vacancy.get(v['vacancy_id'], {}).get('score', 0) >= vacancy_scoring.LEVEL_2_MIN_SCORE
                or l1_by_vacancy.get(v['vacancy_id'], {}).get('score_percentile', 0.0) >= 0.5
            ]
            l2_skipped = [
                v for v in l1_success
                if l1_by_vacancy.get(v['vacancy_id'], {}).get('score', 0) < vacancy_scoring.LEVEL_2_MIN_SCORE
                and l1_by_vacancy.get(v['vacancy_id'], {}).get('score_percentile', 0.0) < 0.5
            ]
            for v in l2_skipped:
                l1_score = l1_by_vacancy[v['vacancy_id']]['score']
                l1_pct = l1_by_vacancy[v['vacancy_id']]['score_percentile']
                protocol = [{
                    "left": "N/A",
                    "left_field": "N/A",
                    "score": 0,
                    "score_percentile": 0.0,
                    "right_field": "missing",
                    "msg": f"Level 2 not started: level 1 score {l1_score} (pct: {l1_pct}) is below minimum {vacancy_scoring.LEVEL_2_MIN_SCORE} or 0.5"
                }]
                vacancy_scoring.save_estimation_result(v, 'estimation2', None, None, 0, 0.0, protocol)
            if l2_candidates:
                print(
                    f"\n🎯 {len(l2_candidates)} vacancy(ies) qualify for LEVEL 2 (score >= {vacancy_scoring.LEVEL_2_MIN_SCORE} or pct >= 0.5). {len(l2_skipped)} skipped (level 1 too low).")
                l2_results, l2_success, l2_failed, l2_time, l2_model_times = (
                    ai_helper._apply_level_models_to_vacancies(
                        l2_candidates, level_n=2, level_name="LEVEL 2"
                    )
                )
                for r in l2_results:
                    if r['success']:
                        parsed = r.get('parsed_json') or {}
                        score, protocol, unknown = vacancy_scoring.calculate_score(parsed)
                        total_abs = sum(abs(e['score']) for e in protocol)
                        vacancy_pct = round(score / total_abs, 2) if total_abs > 0 else 0.0
                        r['score'] = score
                        r['score_percentile'] = vacancy_pct
                        r['protocol'] = protocol
                        r['unknown_skills'] = unknown
                        v = next((v for v in l2_candidates if v['vacancy_id'] == r['vacancy_id']), None)
                        if v:
                            vacancy_scoring.save_estimation_result(v, 'estimation2', r['model_id'], parsed, score,
                                                                   vacancy_pct, protocol)
                    else:
                        r['score'] = 0
                        r['score_percentile'] = 0.0
                        r['protocol'] = [{"msg": f"Generation failed: {r.get('error')}"}]
                        r['unknown_skills'] = []
                ai_helper._print_level_summary("LEVEL 2", l2_results, l2_success, l2_failed, l2_time)
                ai_helper._print_model_usage_table("LEVEL 2", l2_results, l2_model_times)
                ai_helper._print_unknown_skills_summary("LEVEL 2", l2_results)
                result_data['level2'] = {
                    'results': l2_results,
                    'successful_vacancies': l2_success,
                    'failed_vacancies': l2_failed,
                    'total_time': l2_time,
                    'model_times': l2_model_times
                }
            else:
                print(
                    f"\n⚠️ No vacancies qualify for LEVEL 2 (all level 1 scores < {vacancy_scoring.LEVEL_2_MIN_SCORE} and pct < 0.5).")
                result_data['level2'] = {
                    'results': [],
                    'successful_vacancies': [],
                    'failed_vacancies': [],
                    'total_time': 0.0,
                    'model_times': {}
                }
        finally:
            ai_helper.stop_server()
        overall_time = time.time() - overall_start
        result_data['total_time'] = overall_time
        print(f"\n{'#' * 70}")
        print(f"# FINAL TIME SUMMARY")
        print(f"{'#' * 70}")
        l1_t = result_data['level1']['total_time'] if result_data['level1'] else 0.0
        l2_t = result_data['level2']['total_time'] if result_data['level2'] else 0.0
        print(f"  LEVEL 1 time: {l1_t:>10.2f}s")
        print(f"  LEVEL 2 time: {l2_t:>10.2f}s")
        print(f"  {'-' * 40}")
        print(f"  Total time:   {overall_time:>10.2f}s")
        print(f"{'#' * 70}")
        # 8. Save bulk JSON chunk
        ChunkHelper.save_bulk_json_chunk(folder, selected_files)
        return result_data