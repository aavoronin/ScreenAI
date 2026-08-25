import os
import re
import json
from datetime import datetime
from Estimators.BaseVacancyEstimator import BaseVacancyEstimator
from Estimators.ChunkHelper import ChunkHelper


class PeriodSummary:
    @staticmethod
    def generate_period_summary(navigators, output_folder, period_start, period_end):
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