import os
import re
import json
from datetime import datetime
from Estimators.ExchangeRates import ExchangeRates

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
    def _format_salary_display(sal_min, sal_max, sal_curr, sal_period, exchange_rates_df):
        """
        Format salary display.
        Line 1: Original values and period (e.g., per month, per hour).
        Line 2: Converted to per year in USD.
        Line 3: Converted to per year in EUR.

        Conversion factors to year (defined in class constants):
        - Hour: 40 hours/week * 52 weeks/year = 2080
        - Day: 5 days/week * 52 weeks/year = 260
        - Week: 52
        - Month: 12
        """
        if not sal_curr:
            return ""
        min_val = ChunkHelper._parse_salary_value(sal_min)
        max_val = ChunkHelper._parse_salary_value(sal_max)
        if min_val is None and max_val is None:
            return ""

        curr = sal_curr.upper().strip()
        period = str(sal_period).strip().lower() if sal_period else ""

        def format_range(mn, mx, currency, period_str):
            parts = []
            if mn is not None and mx is not None:
                parts.append(f"{mn:,.0f}-{mx:,.0f}")
            elif mn is not None:
                parts.append(f"{mn:,.0f}+")
            elif mx is not None:
                parts.append(f"up to {mx:,.0f}")
            parts.append(currency)
            if period_str:
                parts.append(f"per {period_str}")
            return " ".join(parts)

        # Line 1: Original values and period
        line1 = format_range(min_val, max_val, curr, period)
        lines = [line1]

        # Convert to annual in original currency for subsequent conversions
        ann_min = ChunkHelper._convert_to_annual(min_val, period)
        ann_max = ChunkHelper._convert_to_annual(max_val, period)

        # Line 2: Convert to per year in USD
        usd_min = ChunkHelper._convert_currency(ann_min, curr, 'USD', exchange_rates_df)
        usd_max = ChunkHelper._convert_currency(ann_max, curr, 'USD', exchange_rates_df)
        if usd_min is not None or usd_max is not None:
            lines.append(format_range(usd_min, usd_max, 'USD', 'year'))

        # Line 3: Convert to per year in EUR
        eur_min = ChunkHelper._convert_currency(ann_min, curr, 'EUR', exchange_rates_df)
        eur_max = ChunkHelper._convert_currency(ann_max, curr, 'EUR', exchange_rates_df)
        if eur_min is not None or eur_max is not None:
            lines.append(format_range(eur_min, eur_max, 'EUR', 'year'))

        return "<br>".join(lines)

    @staticmethod
    def _extract_country_str(country_val):
        """Safely extract country as a string from list or string value."""
        if not country_val:
            return ""
        if isinstance(country_val, list):
            return ", ".join(str(c).strip() for c in country_val if c)
        return str(country_val).strip()

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
        # Create MHTML summary file
        ChunkHelper._create_html_summary(chunk_filepath, chunk_data, selected_files, chunks_dir)
        return chunk_filepath

    @staticmethod
    def _create_html_summary(chunk_filepath, chunk_data, selected_files, chunks_dir):
        """
        Create an MHTML file with a summary table of vacancies.
        """
        # Create MHTML filename (same as chunk but with .mhtml extension)
        html_filepath = os.path.splitext(chunk_filepath)[0] + '.html'
        # Load exchange rates for salary conversion
        exchange_rates_df = ExchangeRates.get_currencies()
        # Prepare vacancy data with scores
        vacancy_rows = []
        for v in selected_files:
            vid = v['vacancy_id']
            if vid not in chunk_data:
                continue
            vacancy_data = chunk_data[vid]
            est2 = vacancy_data.get('estimation2', {})
            est1 = vacancy_data.get('estimation1', {})
            # Level 2 takes priority, but if model_id is null, it's considered missing.
            if est2.get('model_id') is not None:
                score = est2.get('score', 0)
                score_percentile = est2.get('score_percentile', 0.0)
                estimation_data = est2
            elif est1.get('model_id') is not None:
                score = est1.get('score', 0)
                score_percentile = est1.get('score_percentile', 0.0)
                estimation_data = est1
            else:
                score = 0
                score_percentile = 0.0
                estimation_data = {}
            # Extract URLs, prioritizing estimation2 over estimation1
            est2_json = est2.get('json') or {}
            est1_json = est1.get('json') or {}
            vacancy_url = est2_json.get('VacancyURL') or est1_json.get('VacancyURL')
            apply_url = est2_json.get('ApplyURL') or est1_json.get('ApplyURL')
            # Get vacancy title
            vacancy_title = ""
            if est1.get('json'):
                vacancy_title = est1['json'].get('Title', '')
            elif est2.get('json'):
                vacancy_title = est2['json'].get('Title', '')
            # Get file paths
            base_path = os.path.splitext(v['json_path'])[0]
            txt_path = base_path + '.txt'
            mhtml_path = base_path + 'mhtml'
            # Get vacancy text
            vacancy_text = ""
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        vacancy_text = f.read()
                except:
                    vacancy_text = "Could not load text"
            vacancy_rows.append({
                'vacancy_id': vid,
                'score': score,
                'score_percentile': score_percentile,
                'title': vacancy_title,
                'estimation_data': estimation_data,
                'json_path': v['json_path'],
                'txt_path': txt_path,
                'mhtml_path': mhtml_path,
                'vacancy_text': vacancy_text,
                'vacancy_url': vacancy_url,
                'apply_url': apply_url
            })
        # Sort by score_percentile desc, then by score desc
        vacancy_rows.sort(key=lambda x: (-x['score_percentile'], -x['score']))
        # Generate HTML
        html_content = ChunkHelper._generate_html_table(vacancy_rows, exchange_rates_df)
        # Save as MHTML
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Created MHTML summary: {html_filepath}")

    @staticmethod
    def _generate_html_table(vacancy_rows, exchange_rates_df):
        """Generate HTML table with collapsible sections and country filter."""
        # Collect distinct countries for filter
        distinct_countries = set()
        for row in vacancy_rows:
            json_data = row.get('estimation_data', {}).get('json', {})
            country_val = json_data.get('CandidateCountry') or json_data.get('EmployerCountry')
            country_str = ChunkHelper._extract_country_str(country_val)
            if country_str:
                # Split by comma to handle multiple countries
                for c in country_str.split(','):
                    c = c.strip()
                    if c:
                        distinct_countries.add(c)
        sorted_countries = sorted(distinct_countries)

        html_parts = ["""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Vacancy Estimation Summary</title>
<style>
body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background-color: #f5f5f5;
    overflow-x: hidden;
}
table {
    width: 100%;
    border-collapse: collapse;
    background-color: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    table-layout: fixed;
    word-wrap: break-word;
}
th, td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
th {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
}
tr:nth-child(even) {
    background-color: #f9f9f9;
}
tr:hover {
    background-color: #f1f1f1;
}
.collapse-btn {
    background-color: #4CAF50;
    color: white;
    border: none;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: 3px;
    font-size: 12px;
}
.collapse-btn:hover {
    background-color: #45a049;
}
.collapsible-section {
    display: none;
    background-color: #fafafa;
}
.collapsible-section.show {
    display: table-row;
}
.nested-table {
    width: 100%;
    margin: 10px 0;
    font-size: 12px;
    table-layout: fixed;
    word-wrap: break-word;
}
.nested-table th, .nested-table td {
    border: 1px solid #ccc;
    padding: 4px;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
.nested-table th {
    background-color: #e0e0e0;
}
.file-link {
    color: #0066cc;
    text-decoration: none;
    margin-right: 10px;
}
.file-link:hover {
    text-decoration: underline;
}
.disabled-link {
    color: gray;
    pointer-events: none;
    cursor: default;
    text-decoration: none;
    margin-right: 10px;
}
.vacancy-text {
    margin-top: 10px;
    padding: 10px;
    background-color: white;
    border: 1px solid #ddd;
    max-height: 200px;
    overflow-y: auto;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: 11px;
    max-width: 100%;
    box-sizing: border-box;
}
.country-filter-container {
    margin: 10px 0 20px 0;
    padding: 10px;
    background-color: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    position: relative;
}
.country-filter-btn {
    background-color: #4CAF50;
    color: white;
    border: none;
    padding: 8px 16px;
    cursor: pointer;
    border-radius: 4px;
    font-size: 14px;
    min-width: 200px;
    text-align: left;
}
.country-filter-btn:hover {
    background-color: #45a049;
}
.country-dropdown {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    background-color: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    max-height: 300px;
    overflow-y: auto;
    z-index: 1000;
    min-width: 250px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.country-dropdown label {
    display: block;
    padding: 6px 12px;
    cursor: pointer;
}
.country-dropdown label:hover {
    background-color: #f1f1f1;
}
.country-dropdown input[type="checkbox"] {
    margin-right: 8px;
}
.filter-actions {
    padding: 6px 12px;
    border-top: 1px solid #ddd;
    background-color: #f9f9f9;
}
.filter-actions button {
    background-color: #4CAF50;
    color: white;
    border: none;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: 3px;
    font-size: 12px;
    margin-right: 4px;
}
.filter-actions button:hover {
    background-color: #45a049;
}
</style>
<script>
function toggleSection(btn) {
    var section = btn.parentElement.parentElement.nextElementSibling;
    if (section.classList.contains('show')) {
        section.classList.remove('show');
        btn.textContent = '[+]';
    } else {
        section.classList.add('show');
        btn.textContent = '[-]';
    }
}

function toggleCountryDropdown() {
    var dropdown = document.getElementById('countryDropdown');
    dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
}

function selectAllCountries() {
    var checkboxes = document.querySelectorAll('#countryDropdown input[type="checkbox"]');
    checkboxes.forEach(function(cb) {
        cb.checked = true;
    });
    filterByCountry();
}

function deselectAllCountries() {
    var checkboxes = document.querySelectorAll('#countryDropdown input[type="checkbox"]');
    checkboxes.forEach(function(cb) {
        cb.checked = false;
    });
    filterByCountry();
}

function filterByCountry() {
    var checkboxes = document.querySelectorAll('#countryDropdown input[type="checkbox"][data-country]');
    var selected = [];
    checkboxes.forEach(function(cb) {
        if (cb.checked) {
            selected.push(cb.getAttribute('data-country'));
        }
    });

    // Update label
    var label = document.getElementById('countryFilterLabel');
    if (selected.length === 0 || selected.length === checkboxes.length) {
        label.textContent = 'All Countries (' + checkboxes.length + ')';
    } else {
        label.textContent = selected.join(', ');
    }

    // Filter rows
    var rows = document.querySelectorAll('tr.main-row');
    rows.forEach(function(row) {
        var rowCountries = row.getAttribute('data-countries');
        var nextRow = row.nextElementSibling;
        var show = false;

        if (selected.length === 0 || selected.length === checkboxes.length) {
            show = true;
        } else {
            var rowCountryList = rowCountries ? rowCountries.split('|') : [];
            for (var i = 0; i < selected.length; i++) {
                if (rowCountryList.indexOf(selected[i]) !== -1) {
                    show = true;
                    break;
                }
            }
        }

        if (show) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
            if (nextRow && nextRow.classList.contains('collapsible-section')) {
                nextRow.style.display = 'none';
                nextRow.classList.remove('show');
            }
        }
    });
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    var container = document.querySelector('.country-filter-container');
    if (container && !container.contains(event.target)) {
        var dropdown = document.getElementById('countryDropdown');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    }
});
</script>
</head>
<body>
<h1>Vacancy Estimation Summary</h1>
"""]

        # Country filter dropdown
        html_parts.append("""<div class="country-filter-container">
    <button class="country-filter-btn" onclick="toggleCountryDropdown()">
        <span id="countryFilterLabel">All Countries (""" + str(len(sorted_countries)) + """)</span> ▼
    </button>
    <div id="countryDropdown" class="country-dropdown">
""")
        for country in sorted_countries:
            escaped_country = country.replace('"', '&quot;').replace("'", '&#39;')
            html_parts.append(
                f'        <label><input type="checkbox" data-country="{escaped_country}" checked onchange="filterByCountry()"> {country}</label>\n')
        html_parts.append("""        <div class="filter-actions">
            <button onclick="selectAllCountries()">Select All</button>
            <button onclick="deselectAllCountries()">Deselect All</button>
        </div>
    </div>
</div>
""")

        html_parts.append("""<table>
<thead>
<tr>
    <th style="width: 13%;">Country</th>
    <th style="width: 30%;">VacancyTitle</th>
    <th style="width: 13%;">Score</th>
    <th style="width: 13%;">Score Percentile</th>
    <th style="width: 13%;">VacancyId</th>
    <th style="width: 13%;">Salary</th>
    <th style="width: 5%;"></th>
</tr>
</thead>
<tbody>
""")
        row_html_parts = []
        for row in vacancy_rows:
            # Extract country separately
            json_data = row.get('estimation_data', {}).get('json', {})
            country_val = json_data.get('CandidateCountry') or json_data.get('EmployerCountry')
            country_str = ChunkHelper._extract_country_str(country_val)

            # Build data-countries attribute for filtering (pipe-separated)
            data_countries = ""
            if country_str:
                countries_list = [c.strip() for c in country_str.split(',') if c.strip()]
                data_countries = '|'.join(countries_list)

            # Title without country
            title = row.get('title', '')
            emp_type = json_data.get('EmploymentType')
            extras = []
            if emp_type:
                extras.append(str(emp_type).strip())
            if extras:
                display_title = f"{title} ({', '.join(extras)})"
            else:
                display_title = title

            # Format salary with conversions
            sal_min = json_data.get('SalaryMin', '')
            sal_max = json_data.get('SalaryMax', '')
            sal_curr = json_data.get('SalaryCurrency', '')
            sal_period = json_data.get('SalaryPeriod', '')
            salary_html = ChunkHelper._format_salary_display(
                sal_min, sal_max, sal_curr, sal_period, exchange_rates_df
            )

            # Main row
            score_str = f"{row['score']:.2f}".rstrip('0').rstrip('.')
            score_percentile_str = f"{row['score_percentile']:.2f}".rstrip('0').rstrip('.')
            escaped_data_countries = data_countries.replace('"', '&quot;')
            row_html = f"""            <tr class="main-row" data-countries="{escaped_data_countries}">
                <td>{country_str}</td>
                <td>{display_title}</td>
                <td>{score_str}</td>
                <td>{score_percentile_str}</td>
                <td>{row['vacancy_id']}</td>
                <td style="font-size: 11px; line-height: 1.4;">{salary_html}</td>
                <td><button class="collapse-btn" onclick="toggleSection(this)">[+]</button></td>
            </tr>
"""
            # Collapsible section
            row_html += """            <tr class="collapsible-section">
                <td colspan="7">
"""
            # Nested table with skills comparison
            estimation_data = row.get('estimation_data', {})
            if estimation_data:
                protocol = estimation_data.get('scoring_protocol', [])
                if protocol:
                    row_html += """                    <h3>Skills Comparison</h3>
                    <table class="nested-table">
                        <thead>
                            <tr>
                                <th>Vacancy</th>
                                <th>Vacancy Field</th>
                                <th>Score</th>
                                <th>Score Percentile</th>
                                <th>Resume</th>
                                <th>Resume Field</th>
                                <th style="width: 40%;">Message</th>
                            </tr>
                        </thead>
                        <tbody>
"""
                    for entry in protocol:
                        left = entry.get('left', '')
                        left_field = entry.get('left_field', '')
                        score = entry.get('score', 0)
                        score_pct = entry.get('score_percentile', 0.0)
                        right = entry.get('right', '')
                        right_field = entry.get('right_field', '')
                        msg = entry.get('msg', '')
                        row_html += f"""                            <tr>
                                <td>{left}</td>
                                <td>{left_field}</td>
                                <td>{score}</td>
                                <td>{score_pct:.2f}</td>
                                <td>{right}</td>
                                <td>{right_field}</td>
                                <td>{msg}</td>
                            </tr>
"""
                    row_html += """                        </tbody>
                    </table>
"""
                else:
                    row_html += """                    <h3>Skills Comparison</h3>
                    <p>No scoring protocol available.</p>
"""
            else:
                row_html += """                    <h3>Skills Comparison</h3>
                    <p>No estimation data available (both levels failed or missing).</p>
"""

            # File links
            row_html += """                    <h3>Files</h3>
                    <div>
"""
            if os.path.exists(row['json_path']):
                row_html += f'                        <a href="file:///{row["json_path"].replace(chr(92), "/")}" class="file-link">📄 JSON</a>\n'
            if os.path.exists(row['txt_path']):
                row_html += f'                        <a href="file:///{row["txt_path"].replace(chr(92), "/")}" class="file-link">📄 TXT</a>\n'
            if os.path.exists(row['mhtml_path']):
                row_html += f'                        <a href="file:///{row["mhtml_path"].replace(chr(92), "/")}" class="file-link">📄 MHTML</a>\n'
            if row.get('vacancy_url'):
                v_url = row['vacancy_url']
                row_html += f'                        <a href="{v_url}" class="file-link" target="_blank">🔗 Vacancy URL</a>\n'
            if row.get('apply_url'):
                a_url = row['apply_url']
                row_html += f'                        <a href="{a_url}" class="file-link" target="_blank">🔗 Apply URL</a>\n'
            row_html += """                    </div>
"""
            # Vacancy text (strip URLs)
            clean_vacancy_text = re.sub(r'https?://\S+', '', row['vacancy_text'])
            row_html += f"""                    <h3>Vacancy Text</h3>
                    <div class="vacancy-text">{clean_vacancy_text}</div>
                </td>
            </tr>
"""
            row_html_parts.append(row_html)
        html_parts.append("".join(row_html_parts))
        html_parts.append("""        </tbody>
</table>
</body>
</html>
""")
        return "".join(html_parts)