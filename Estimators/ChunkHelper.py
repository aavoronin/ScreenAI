import os
import json
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    pd = None

class ChunkHelper:
    """
    Helper class for creating and saving bulk JSON chunks of vacancy data.
    """
    # Constants for salary period conversion to annual
    # Conversion factors:
    # - Hour to year: 40 hours/week * 52 weeks/year = 2080 hours/year
    # - Day to year: 5 days/week * 52 weeks/year = 260 days/year
    # - Week to year: 52 weeks/year
    # - Month to year: 12 months/year
    HOURS_PER_WEEK = 40
    WEEKS_PER_YEAR = 52
    DAYS_PER_WEEK = 5
    MONTHS_PER_YEAR = 12

    @staticmethod
    def _parse_salary_value(val):
        if val is None or val == '' or str(val).lower() == 'none':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _convert_to_annual(val, period):
        if val is None:
            return None
        period_lower = str(period).lower() if period else ''
        if 'hour' in period_lower:
            return val * ChunkHelper.HOURS_PER_WEEK * ChunkHelper.WEEKS_PER_YEAR
        elif 'day' in period_lower:
            return val * ChunkHelper.DAYS_PER_WEEK * ChunkHelper.WEEKS_PER_YEAR
        elif 'week' in period_lower:
            return val * ChunkHelper.WEEKS_PER_YEAR
        elif 'month' in period_lower:
            return val * ChunkHelper.MONTHS_PER_YEAR
        else:
            return val

    @staticmethod
    def _convert_currency(amount, from_curr, to_curr, rates_df):
        if amount is None or from_curr == to_curr:
            return amount
        if rates_df is None or pd is None:
            return None
        from_row = rates_df[rates_df['Currency'] == from_curr.upper()]
        to_row = rates_df[rates_df['Currency'] == to_curr.upper()]
        if from_row.empty or to_row.empty:
            return None
        from_rate_usd = from_row['Rate_USD'].values[0]
        to_rate_usd = to_row['Rate_USD'].values[0]
        if pd.isna(from_rate_usd) or pd.isna(to_rate_usd) or from_rate_usd == 0:
            return None
        amount_usd = amount / from_rate_usd
        amount_target = amount_usd * to_rate_usd
        return amount_target

    @staticmethod
    def _extract_country_str(country_val):
        """Safely extract country as a string from list or string value."""
        if not country_val:
            return ""
        if isinstance(country_val, list):
            return ", ".join(str(c).strip() for c in country_val if c)
        return str(country_val).strip()

    @staticmethod
    def _load_estimator_config():
        estimator_config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'estimator_config.json'
        )
        if not os.path.exists(estimator_config_path):
            return {}
        try:
            with open(estimator_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _build_country_synonym_map():
        config = ChunkHelper._load_estimator_config()
        countries_section = config.get('countries', [])
        synonym_map = {}
        valid_canonical_names = set()
        if isinstance(countries_section, list):
            for group in countries_section:
                if isinstance(group, list) and len(group) > 0:
                    canonical = str(group[0]).strip()
                    valid_canonical_names.add(canonical.lower())
                    for syn in group:
                        if isinstance(syn, str):
                            synonym_map[syn.lower()] = canonical
        return synonym_map, valid_canonical_names

    @staticmethod
    def save_bulk_json_chunk(folder, selected_files):
        """
        Save a bulk JSON chunk containing the parsed vacancy data.
        The chunk is saved in the 'Chunks' directory relative to the folder.
        """
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
        # Create HTML summary file
        from Estimators.ChunkHtmlHelper import ChunkHtmlHelper
        ChunkHtmlHelper.create_html_summary(chunk_filepath, chunk_data, selected_files, chunks_dir)
        return chunk_filepath