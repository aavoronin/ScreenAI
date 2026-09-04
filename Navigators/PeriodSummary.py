import os
import re
import json
from datetime import datetime
from Estimators.BaseVacancyEstimator import BaseVacancyEstimator
from Estimators.ChunkHelper import ChunkHelper
from Estimators.ExchangeRates import ExchangeRates
from Estimators.HtmlHelper import HtmlHelper

try:
    from lingua import Language, LanguageDetectorBuilder
except ImportError:
    Language = None
    LanguageDetectorBuilder = None

LANGUAGE_NAMES = {
    'english', 'russian', 'spanish', 'french', 'german', 'italian',
    'portuguese', 'dutch', 'polish', 'ukrainian', 'belarusian',
    'czech', 'slovak', 'hungarian', 'romanian', 'bulgarian',
    'serbian', 'croatian', 'bosnian', 'slovenian', 'macedonian',
    'albanian', 'greek', 'turkish', 'arabic', 'hebrew', 'persian',
    'farsi', 'hindi', 'urdu', 'bengali', 'punjabi', 'tamil',
    'telugu', 'kannada', 'malayalam', 'marathi', 'gujarati',
    'chinese', 'mandarin', 'cantonese', 'japanese', 'korean',
    'vietnamese', 'thai', 'indonesian', 'malay', 'filipino',
    'tagalog', 'swedish', 'norwegian', 'danish', 'finnish',
    'icelandic', 'estonian', 'latvian', 'lithuanian', 'irish',
    'welsh', 'scottish', 'catalan', 'basque', 'galician',
    'afrikaans', 'swahili', 'zulu', 'xhosa', 'amharic',
    'somali', 'hausa', 'yoruba', 'igbo', 'azerbaijani',
    'kazakh', 'kyrgyz', 'uzbek', 'turkmen', 'tajik', 'georgian',
    'armenian', 'latin', 'esperanto'
}

if Language is not None:
    try:
        for language in Language:
            LANGUAGE_NAMES.add(language.name.lower())
    except TypeError:
        pass

class PeriodSummary:
    @staticmethod
    def generate_period_summary(
        navigators,
        output_folder,
        period_start,
        period_end
    ):
        """
        Generate a period summary HTML file for vacancies parsed and estimated
        within the specified period.
        """
        os.makedirs(output_folder, exist_ok=True)

        if isinstance(period_start, datetime):
            start_str = period_start.isoformat()
        else:
            start_str = str(period_start)

        if isinstance(period_end, datetime):
            end_str = period_end.isoformat()
        else:
            end_str = str(period_end)

        selected_files = []
        chunk_data = {}

        for nav in navigators:
            vacancies_dir = nav.get_vacancies_output_path()
            if not vacancies_dir or not os.path.exists(vacancies_dir):
                continue

            for filename in os.listdir(vacancies_dir):
                if not filename.endswith('.json'):
                    continue

                json_path = os.path.join(vacancies_dir, filename)
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue

                parsing_version = data.get('parsing_version')
                estimation_version = data.get('estimation_version')

                try:
                    p_ver = int(parsing_version) if parsing_version is not None else 0
                    e_ver = int(estimation_version) if estimation_version is not None else 0
                except (ValueError, TypeError):
                    continue

                if p_ver != BaseVacancyEstimator.PARSING_VERSION:
                    continue

                if e_ver != BaseVacancyEstimator.ESTIMATION_VERSION:
                    continue

                saved_date_str = data.get('saved_date', '')
                if not saved_date_str:
                    continue

                if start_str <= saved_date_str <= end_str:
                    match = re.search(r'(\d+)', filename)
                    vacancy_id = match.group(1) if match else filename

                    selected_files.append({
                        'vacancy_id': vacancy_id,
                        'json_path': json_path
                    })

                    chunk_data[vacancy_id] = data

        if not selected_files:
            print("ℹ️ No vacancies found matching the criteria for the specified period.")
            return

        period_start_str = period_start.strftime("%Y-%m-%d") if isinstance(period_start, datetime) else str(
            period_start).replace(':', '-')
        period_end_str = period_end.strftime("%Y-%m-%d") if isinstance(period_end, datetime) else str(
            period_end).replace(':', '-')

        chunk_filename = f"vacancies_{period_start_str}_{period_end_str}.html"
        chunk_filepath = os.path.join(output_folder, chunk_filename)

        ChunkHelper._create_html_summary(chunk_filepath, chunk_data, selected_files, output_folder)
        print(f"✅ Period summary generated: {chunk_filepath}")

        salary_summary_filepath = os.path.join(
            output_folder,
            f"vacancies_{period_start_str}_{period_end_str}_SalarySummary.html"
        )
        salary_data = PeriodSummary._collect_salary_summary_data(
            chunk_data,
            selected_files
        )
        HtmlHelper.generate_salary_summary_html(
            salary_summary_filepath,
            salary_data['country_rows'],
            salary_data['total'],
            period_start_str,
            period_end_str
        )
        print(f"✅ Salary summary generated: {salary_summary_filepath}")

        missing_skills_filepath = os.path.join(
            output_folder,
            f"vacancies_{period_start_str}_{period_end_str}_MissingSkills.html"
        )
        missing_skills_data = PeriodSummary._collect_missing_skills_data(
            chunk_data,
            selected_files
        )
        HtmlHelper.generate_missing_skills_html(
            missing_skills_filepath,
            missing_skills_data['skill_rows'],
            missing_skills_data['required_language_rows'],
            period_start_str,
            period_end_str
        )
        print(f"✅ Missing skills summary generated: {missing_skills_filepath}")

    @staticmethod
    def _select_estimation_data(vacancy_data):
        est2 = vacancy_data.get('estimation2', {})
        est1 = vacancy_data.get('estimation1', {})

        # Level 2 takes priority, but if model_id is null, it is missing.
        if est2.get('model_id') is not None:
            return est2

        if est1.get('model_id') is not None:
            return est1

        return None

    @staticmethod
    def _safe_list(value):
        if isinstance(value, list):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        if isinstance(value, str) and value.strip():
            return [value.strip()]

        return []

    @staticmethod
    def _read_vacancy_text(txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except (IOError, OSError):
            return ""

    @staticmethod
    def _extract_language_name(skill):
        if not skill:
            return None

        skill_lower = str(skill).strip().lower()

        if skill_lower in LANGUAGE_NAMES:
            return skill_lower.title()

        cleaned = re.sub(r'\([^)]*\)', '', skill_lower).strip()

        if cleaned in LANGUAGE_NAMES:
            return cleaned.title()

        if cleaned.endswith(' language'):
            root = cleaned[:-len(' language')].strip()
            if root in LANGUAGE_NAMES:
                return root.title()

        return None

    @staticmethod
    def _add_language(language, seen_languages, language_counts):
        if not language:
            return

        language = str(language).strip()

        if not language:
            return

        if language.lower() in {'none', 'n/a', 'na', '-'}:
            return

        display = language.title()
        key = display.lower()

        if key in seen_languages:
            return

        seen_languages.add(key)

        if key not in language_counts:
            language_counts[key] = {
                'language': display,
                'count': 0
            }

        language_counts[key]['count'] += 1

    @staticmethod
    def _detect_non_english_languages(text, detector):
        if not text or detector is None:
            return []

        total_chars = len(text)

        if total_chars == 0:
            return []

        try:
            candidates = detector.detect_multiple_languages_of(text)
        except Exception:
            return []

        language_totals = {}
        language_display_names = {}

        for candidate in candidates:
            iso_code = candidate.language.iso_code_639_1.name.upper()
            span_length = candidate.end_index - candidate.start_index

            if span_length <= 0:
                continue

            language_totals[iso_code] = (
                language_totals.get(iso_code, 0) + span_length
            )

            if iso_code not in language_display_names:
                raw_name = candidate.language.name.lower()
                raw_name = raw_name.replace('_', ' ')
                language_display_names[iso_code] = raw_name.title()

        detected_languages = []

        for iso_code, span_length in language_totals.items():
            if iso_code == 'EN':
                continue

            percentage = span_length / total_chars

            # Include only languages occupying more than 40% of the text.
            if percentage <= 0.40:
                continue

            language_name = language_display_names.get(iso_code)

            if language_name and language_name not in detected_languages:
                detected_languages.append(language_name)

        return detected_languages

    @staticmethod
    def _collect_missing_skills_data(chunk_data, selected_files):
        known_skills = BaseVacancyEstimator()._get_all_known_tech_skills()

        skill_counts = {}

        print(f'collecting missing skills')
        for nf, v in enumerate(selected_files):
            if nf % 20 == 0:
                print(f'{nf:<6} of {len(selected_files)} files processes')

            vid = v['vacancy_id']
            data = chunk_data.get(vid)
            if not data:
                continue

            estimation_data = PeriodSummary._select_estimation_data(data)
            if estimation_data is None:
                estimation_data = {}

            protocol = estimation_data.get('scoring_protocol') or []

            seen_skills = set()

            for entry in protocol:
                # Unknown skills are marked with right_field='unknown'.
                if entry.get('right_field') != 'unknown':
                    continue

                skill = str(
                    entry.get('missing') or entry.get('left') or ''
                ).strip()

                if not skill:
                    continue

                # If the unknown entry is a language name, it is not a skill. Skip it.
                language_name = PeriodSummary._extract_language_name(skill)
                if language_name:
                    continue

                key = skill.lower()

                # Existing skills and their synonyms from estimator_config.json
                # are excluded even if old estimator JSONs still contain them.
                if key in known_skills:
                    continue

                if key in seen_skills:
                    continue

                seen_skills.add(key)

                if key not in skill_counts:
                    skill_counts[key] = {
                        'skill': skill,
                        'count': 0
                    }

                skill_counts[key]['count'] += 1

        skill_rows = []

        for item in skill_counts.values():
            skill_rows.append({
                'skill': item['skill'],
                'count': item['count']
            })

        skill_rows.sort(
            key=lambda row: (-row['count'], row['skill'].lower())
        )

        return {
            'skill_rows': skill_rows,
            'required_language_rows': []
        }

    @staticmethod
    def _collect_salary_summary_data(chunk_data, selected_files):
        exchange_rates_df = ExchangeRates.get_currencies()
        synonym_map, valid_canonical_names = (
            ChunkHelper._build_country_synonym_map()
        )

        country_stats = {}
        total_count = 0
        total_usd_min = 0.0
        total_usd_max = 0.0
        total_eur_min = 0.0
        total_eur_max = 0.0

        for v in selected_files:
            vid = v['vacancy_id']
            data = chunk_data.get(vid)
            if not data:
                continue

            estimation_data = PeriodSummary._select_estimation_data(data)
            if estimation_data is None:
                continue

            json_data = estimation_data.get('json') or {}

            sal_min = json_data.get('SalaryMin')
            sal_max = json_data.get('SalaryMax')
            sal_curr = json_data.get('SalaryCurrency')
            sal_period = json_data.get('SalaryPeriod')

            if not sal_curr:
                continue

            min_val = ChunkHelper._parse_salary_value(sal_min)
            max_val = ChunkHelper._parse_salary_value(sal_max)

            if min_val is None or max_val is None:
                continue

            ann_min = ChunkHelper._convert_to_annual(min_val, sal_period)
            ann_max = ChunkHelper._convert_to_annual(max_val, sal_period)

            if ann_min is None or ann_max is None:
                continue

            curr = sal_curr.upper().strip()

            usd_min = ChunkHelper._convert_currency(
                ann_min,
                curr,
                'USD',
                exchange_rates_df
            )
            usd_max = ChunkHelper._convert_currency(
                ann_max,
                curr,
                'USD',
                exchange_rates_df
            )

            if usd_min is None or usd_max is None:
                continue

            # Existing salary filter: valid USD annual range 15k to 300k.
            if usd_min < 15000 or usd_max >= 300000:
                continue

            eur_min = ChunkHelper._convert_currency(
                ann_min,
                curr,
                'EUR',
                exchange_rates_df
            )
            eur_max = ChunkHelper._convert_currency(
                ann_max,
                curr,
                'EUR',
                exchange_rates_df
            )

            total_count += 1
            total_usd_min += usd_min
            total_usd_max += usd_max

            if eur_min is not None:
                total_eur_min += eur_min

            if eur_max is not None:
                total_eur_max += eur_max

            country_val = (
                json_data.get('CandidateCountry')
                or json_data.get('EmployerCountry')
            )
            raw_str = ChunkHelper._extract_country_str(country_val)
            countries_for_row = []

            if raw_str:
                for c in raw_str.split(','):
                    c = c.strip()
                    if not c:
                        continue

                    canonical = synonym_map.get(c.lower(), c)
                    if canonical.lower() not in valid_canonical_names:
                        continue

                    if canonical not in countries_for_row:
                        countries_for_row.append(canonical)

            for country in countries_for_row:
                if country not in country_stats:
                    country_stats[country] = {
                        'count': 0,
                        'usd_min': 0.0,
                        'usd_max': 0.0,
                        'eur_min': 0.0,
                        'eur_max': 0.0
                    }

                stats = country_stats[country]
                stats['count'] += 1
                stats['usd_min'] += usd_min
                stats['usd_max'] += usd_max

                if eur_min is not None:
                    stats['eur_min'] += eur_min

                if eur_max is not None:
                    stats['eur_max'] += eur_max

        rows_for_sort = []

        for country, stats in country_stats.items():
            if stats['count'] <= 0:
                continue

            avg_usd_min = stats['usd_min'] / stats['count']
            avg_usd_max = stats['usd_max'] / stats['count']
            avg_eur_min = stats['eur_min'] / stats['count']
            avg_eur_max = stats['eur_max'] / stats['count']

            # Sort by the midpoint of the average USD salary range.
            sort_value = (avg_usd_min + avg_usd_max) / 2.0

            rows_for_sort.append((
                sort_value,
                {
                    'country': country,
                    'count': stats['count'],
                    'avg_usd_min': avg_usd_min,
                    'avg_usd_max': avg_usd_max,
                    'avg_eur_min': avg_eur_min,
                    'avg_eur_max': avg_eur_max
                }
            ))

        rows_for_sort.sort(key=lambda item: item[0], reverse=True)
        country_rows = [row for _, row in rows_for_sort]

        if total_count > 0:
            total = {
                'count': total_count,
                'avg_usd_min': total_usd_min / total_count,
                'avg_usd_max': total_usd_max / total_count,
                'avg_eur_min': total_eur_min / total_count,
                'avg_eur_max': total_eur_max / total_count
            }
        else:
            total = {
                'count': 0,
                'avg_usd_min': None,
                'avg_usd_max': None,
                'avg_eur_min': None,
                'avg_eur_max': None
            }

        return {
            'country_rows': country_rows,
            'total': total
        }