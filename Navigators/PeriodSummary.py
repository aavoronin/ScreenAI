import os
import re
import json
from datetime import datetime
from Estimators.BaseVacancyEstimator import BaseVacancyEstimator
from Estimators.ChunkHelper import ChunkHelper
from Estimators.ExchangeRates import ExchangeRates


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
        PeriodSummary._create_salary_summary_html(
            salary_summary_filepath,
            chunk_data,
            selected_files,
            period_start_str,
            period_end_str
        )
        print(f"✅ Salary summary generated: {salary_summary_filepath}")

        missing_skills_filepath = os.path.join(
            output_folder,
            f"vacancies_{period_start_str}_{period_end_str}_MissingSkills.html"
        )
        PeriodSummary._create_missing_skills_html(
            missing_skills_filepath,
            chunk_data,
            selected_files,
            period_start_str,
            period_end_str
        )
        print(f"✅ Missing skills summary generated: {missing_skills_filepath}")

    @staticmethod
    def _escape_html(value):
        return (
            str(value)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
        )

    @staticmethod
    def _format_salary_range(avg_min, avg_max, currency_symbol):
        if avg_min is None or avg_max is None:
            return "-"
        return (
            f"{currency_symbol}{avg_min:,.0f} - "
            f"{currency_symbol}{avg_max:,.0f}"
        )

    @staticmethod
    def _create_salary_summary_html(
        filepath,
        chunk_data,
        selected_files,
        period_start_str,
        period_end_str
    ):
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

            est2 = data.get('estimation2', {})
            est1 = data.get('estimation1', {})

            # Level 2 takes priority, but if model_id is null, it is missing.
            if est2.get('model_id') is not None:
                estimation_data = est2
            elif est1.get('model_id') is not None:
                estimation_data = est1
            else:
                estimation_data = {}

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

        country_rows = []

        for country, stats in country_stats.items():
            if stats['count'] <= 0:
                continue

            avg_usd_min = stats['usd_min'] / stats['count']
            avg_usd_max = stats['usd_max'] / stats['count']
            avg_eur_min = stats['eur_min'] / stats['count']
            avg_eur_max = stats['eur_max'] / stats['count']

            # Sort by the midpoint of the average USD salary range.
            sort_value = (avg_usd_min + avg_usd_max) / 2.0

            country_rows.append({
                'country': country,
                'count': stats['count'],
                'avg_usd_min': avg_usd_min,
                'avg_usd_max': avg_usd_max,
                'avg_eur_min': avg_eur_min,
                'avg_eur_max': avg_eur_max,
                'sort_value': sort_value
            })

        country_rows.sort(key=lambda row: row['sort_value'], reverse=True)

        html_parts = []
        html_parts.append("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Salary Summary by Country</title>
<style>
body {
font-family: Arial, sans-serif;
margin: 20px;
background-color: #f5f5f5;
}
table {
border-collapse: collapse;
background-color: white;
box-shadow: 0 2px 4px rgba(0,0,0,0.1);
min-width: 800px;
}
th, td {
border: 1px solid #ddd;
padding: 8px;
text-align: left;
}
th {
background-color: #4CAF50;
color: white;
}
tr:nth-child(even) {
background-color: #f9f9f9;
}
tr:hover {
background-color: #f1f1f1;
}
.total-row {
font-weight: bold;
background-color: #e7f3fe;
}
</style>
</head>
<body>
<h1>Salary Summary by Country</h1>
""")

        period_text = f"Period: {period_start_str} - {period_end_str}"
        html_parts.append(
            f'<p>{PeriodSummary._escape_html(period_text)}</p>\n'
        )

        if total_count > 0 or country_rows:
            html_parts.append(
                '<table>\n'
                '<thead>\n'
                '<tr>\n'
                '    <th>#</th>\n'
                '    <th>Country</th>\n'
                '    <th>Vacancies</th>\n'
                '    <th>Average USD Salary Range</th>\n'
                '    <th>Average EUR Salary Range</th>\n'
                '</tr>\n'
                '</thead>\n'
                '<tbody>\n'
            )

            rownum = 1
            for row in country_rows:
                usd_range = PeriodSummary._format_salary_range(
                    row['avg_usd_min'],
                    row['avg_usd_max'],
                    '$'
                )
                eur_range = PeriodSummary._format_salary_range(
                    row['avg_eur_min'],
                    row['avg_eur_max'],
                    '€'
                )

                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{rownum}</td>\n'
                    f'                <td>'
                    f'{PeriodSummary._escape_html(row["country"])}'
                    f'</td>\n'
                    f'                <td>{row["count"]}</td>\n'
                    f'                <td>{usd_range}</td>\n'
                    f'                <td>{eur_range}</td>\n'
                    '            </tr>\n'
                )

                rownum += 1

            if total_count > 0:
                total_avg_usd_min = total_usd_min / total_count
                total_avg_usd_max = total_usd_max / total_count
                total_avg_eur_min = total_eur_min / total_count
                total_avg_eur_max = total_eur_max / total_count

                total_usd_range = PeriodSummary._format_salary_range(
                    total_avg_usd_min,
                    total_avg_usd_max,
                    '$'
                )
                total_eur_range = PeriodSummary._format_salary_range(
                    total_avg_eur_min,
                    total_avg_eur_max,
                    '€'
                )
            else:
                total_usd_range = "-"
                total_eur_range = "-"

            html_parts.append(
                '            <tr class="total-row">\n'
                '                <td></td>\n'
                '                <td>Total</td>\n'
                f'                <td>{total_count}</td>\n'
                f'                <td>{total_usd_range}</td>\n'
                f'                <td>{total_eur_range}</td>\n'
                '            </tr>\n'
            )

            html_parts.append(
                '        </tbody>\n'
                '</table>\n'
            )
        else:
            html_parts.append(
                '<p>No valid salary data found for the period.</p>\n'
            )

        html_parts.append(
            '</body>\n'
            '</html>\n'
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(''.join(html_parts))

    @staticmethod
    def _create_missing_skills_html(
        filepath,
        chunk_data,
        selected_files,
        period_start_str,
        period_end_str
    ):
        skill_counts = {}

        for v in selected_files:
            vid = v['vacancy_id']
            data = chunk_data.get(vid)
            if not data:
                continue

            est2 = data.get('estimation2', {})
            est1 = data.get('estimation1', {})

            # Level 2 takes priority, but if model_id is null, it is missing.
            if est2.get('model_id') is not None:
                estimation_data = est2
            elif est1.get('model_id') is not None:
                estimation_data = est1
            else:
                continue

            protocol = estimation_data.get('scoring_protocol') or []
            seen_in_vacancy = set()

            for entry in protocol:
                # Unknown skills are marked with right_field='unknown'.
                if entry.get('right_field') != 'unknown':
                    continue

                skill = str(
                    entry.get('missing') or entry.get('left') or ''
                ).strip()

                if not skill:
                    continue

                key = skill.lower()
                if key in seen_in_vacancy:
                    continue

                seen_in_vacancy.add(key)

                if key not in skill_counts:
                    skill_counts[key] = {
                        'skill': skill,
                        'count': 0
                    }

                skill_counts[key]['count'] += 1

        rows = []

        for item in skill_counts.values():
            rows.append({
                'skill': item['skill'],
                'count': item['count']
            })

        rows.sort(
            key=lambda row: (-row['count'], row['skill'].lower())
        )

        html_parts = []
        html_parts.append("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Missing Skills Summary</title>
<style>
body {
font-family: Arial, sans-serif;
margin: 20px;
background-color: #f5f5f5;
}
table {
border-collapse: collapse;
background-color: white;
box-shadow: 0 2px 4px rgba(0,0,0,0.1);
min-width: 700px;
}
th, td {
border: 1px solid #ddd;
padding: 8px;
text-align: left;
}
th {
background-color: #4CAF50;
color: white;
}
tr:nth-child(even) {
background-color: #f9f9f9;
}
tr:hover {
background-color: #f1f1f1;
}
</style>
</head>
<body>
<h1>Missing Skills Summary</h1>
""")

        period_text = f"Period: {period_start_str} - {period_end_str}"
        html_parts.append(
            f'<p>{PeriodSummary._escape_html(period_text)}</p>\n'
        )

        if rows:
            html_parts.append(
                f'<p>Total unique missing skills: {len(rows)}</p>\n'
                '<table>\n'
                '<thead>\n'
                '<tr>\n'
                '    <th>#</th>\n'
                '    <th>Missing Skill</th>\n'
                '    <th>Vacancies</th>\n'
                '</tr>\n'
                '</thead>\n'
                '<tbody>\n'
            )

            for i, row in enumerate(rows, start=1):
                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{i}</td>\n'
                    f'                <td>'
                    f'{PeriodSummary._escape_html(row["skill"])}'
                    f'</td>\n'
                    f'                <td>{row["count"]}</td>\n'
                    '            </tr>\n'
                )

            html_parts.append(
                '        </tbody>\n'
                '</table>\n'
            )
        else:
            html_parts.append(
                '<p>No missing skills found for the period.</p>\n'
            )

        html_parts.append(
            '</body>\n'
            '</html>\n'
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(''.join(html_parts))