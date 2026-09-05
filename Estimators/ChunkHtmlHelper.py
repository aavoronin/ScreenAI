import os
import re
import json
from Estimators.ChunkHelper import ChunkHelper
from Estimators.ExchangeRates import ExchangeRates


class ChunkHtmlHelper:
    @staticmethod
    def _format_salary_display(sal_min, sal_max, sal_curr, sal_period, exchange_rates_df):
        """
        Format salary display.
        Line 1: Original values and period (e.g., per month, per hour).
        Line 2: Converted to per year in USD.
        Line 3: Converted to per year in EUR.
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
    def _calculate_salary_stats(vacancy_rows, exchange_rates_df):
        """
        Calculate qualified salaries for average calculation.
        Returns a list of dictionaries containing salary data and associated countries.
        """
        qualified_salaries = []
        synonym_map, valid_canonical_names = ChunkHelper._build_country_synonym_map()

        for idx, row in enumerate(vacancy_rows):
            json_data = row.get('estimation_data', {}).get('json', {})
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
            usd_min = ChunkHelper._convert_currency(ann_min, curr, 'USD', exchange_rates_df)
            usd_max = ChunkHelper._convert_currency(ann_max, curr, 'USD', exchange_rates_df)
            if usd_min is None or usd_max is None:
                continue

            # Filter: min >= 15000 and max < 300000
            if usd_min >= 15000 and usd_max < 300000:
                eur_min = ChunkHelper._convert_currency(ann_min, curr, 'EUR', exchange_rates_df)
                eur_max = ChunkHelper._convert_currency(ann_max, curr, 'EUR', exchange_rates_df)

                country_val = json_data.get('CandidateCountry') or json_data.get('EmployerCountry')
                raw_str = ChunkHelper._extract_country_str(country_val)
                row_countries = []
                if raw_str:
                    for c in raw_str.split(','):
                        c = c.strip()
                        if not c:
                            continue
                        canonical = synonym_map.get(c.lower(), c)
                        if canonical.lower() in valid_canonical_names:
                            if canonical not in row_countries:
                                row_countries.append(canonical)

                qualified_salaries.append({
                    'rowId': idx,
                    'usdMin': usd_min,
                    'usdMax': usd_max,
                    'eurMin': eur_min if eur_min is not None else 0,
                    'eurMax': eur_max if eur_max is not None else 0,
                    'countries': row_countries
                })

        return qualified_salaries

    @staticmethod
    def create_html_summary(chunk_filepath, chunk_data, selected_files, chunks_dir):
        """
        Create an MHTML file with a summary table of vacancies.
        Also creates per-country summary files.
        """
        # Create MHTML filename (same as chunk but with .html extension)
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
            if not vacancy_url:
                if "LinkedIn" in v['json_path']:
                    vacancy_url = f"https://www.linkedin.com/jobs/view/{vid}/"
                elif "Hirify" in v['json_path']:
                    vacancy_url = f"https://hirify.me/jobs/{vid}"
            if not apply_url:
                if "LinkedIn" in v['json_path']:
                    apply_url = f"https://www.linkedin.com/jobs/view/{vid}/"
                elif "Hirify" in v['json_path']:
                    apply_url = f"https://hirify.me/jobs/{vid}"
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

        # Sort by Score * abs(score_percentile) descending
        vacancy_rows.sort(key=lambda x: -(x['score'] * abs(x['score_percentile'])))

        # Generate main HTML
        html_content = ChunkHtmlHelper._generate_html_table(vacancy_rows, exchange_rates_df, stats_title="Global")
        # Save main file
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Created MHTML summary: {html_filepath}")
        # Generate per-country summary files
        synonym_map, valid_canonical_names = ChunkHelper._build_country_synonym_map()
        country_to_rows = {}
        for row in vacancy_rows:
            json_data = row.get('estimation_data', {}).get('json', {})
            country_val = json_data.get('CandidateCountry') or json_data.get('EmployerCountry')
            raw_str = ChunkHelper._extract_country_str(country_val)
            if raw_str:
                for c in raw_str.split(','):
                    c = c.strip()
                    if not c:
                        continue
                    canonical = synonym_map.get(c.lower(), c)
                    if canonical.lower() in valid_canonical_names:
                        if canonical not in country_to_rows:
                            country_to_rows[canonical] = []
                        country_to_rows[canonical].append(row)
        # Extract date range from filename for country file naming
        basename = os.path.basename(html_filepath)
        date_part = basename.replace("vacancies_", "").replace(".html", "")
        output_dir = os.path.dirname(html_filepath)
        for country, country_rows in country_to_rows.items():
            country_filename = f"vacancies_{date_part}_{country}.html"
            country_filepath = os.path.join(output_dir, country_filename)
            country_html = ChunkHtmlHelper._generate_html_table(country_rows, exchange_rates_df, stats_title=country)
            with open(country_filepath, 'w', encoding='utf-8') as f:
                f.write(country_html)
            print(f"✅ Created country summary: {country_filepath}")

    @staticmethod
    def _generate_html_table(vacancy_rows, exchange_rates_df, stats_title="Global"):
        """Generate HTML table with collapsible sections and country filter."""
        synonym_map, valid_canonical_names = ChunkHelper._build_country_synonym_map()

        # Calculate salary statistics and get qualified salaries
        qualified_salaries = ChunkHtmlHelper._calculate_salary_stats(vacancy_rows, exchange_rates_df)

        count = len(qualified_salaries)
        sum_usd_min = sum(q['usdMin'] for q in qualified_salaries)
        sum_usd_max = sum(q['usdMax'] for q in qualified_salaries)
        sum_eur_min = sum(q['eurMin'] for q in qualified_salaries)
        sum_eur_max = sum(q['eurMax'] for q in qualified_salaries)

        avg_usd_min = sum_usd_min / count if count > 0 else 0
        avg_usd_max = sum_usd_max / count if count > 0 else 0
        avg_eur_min = sum_eur_min / count if count > 0 else 0
        avg_eur_max = sum_eur_max / count if count > 0 else 0

        stats_html = f"""
<div id="salaryStatsBlock" style="margin: 10px 0 20px 0; padding: 15px; background-color: #e7f3fe; border-left: 6px solid #2196F3; font-family: Arial, sans-serif;">
<h3 style="margin-top: 0; color: #2196F3;">Salary Statistics ({stats_title})</h3>
"""
        if count == 0:
            stats_html += '<p style="margin: 5px 0;"><strong>No data</strong></p>\n'
        else:
            stats_html += f"""<p style="margin: 5px 0;"><strong>Vacancies in range (15k - 300k USD/year):</strong> {count}</p>
<p style="margin: 5px 0;"><strong>Avg USD Min:</strong> ${avg_usd_min:,.0f} | <strong>Avg USD Max:</strong> ${avg_usd_max:,.0f}</p>
<p style="margin: 5px 0;"><strong>Avg EUR Min:</strong> €{avg_eur_min:,.0f} | <strong>Avg EUR Max:</strong> €{avg_eur_max:,.0f}</p>
"""
        stats_html += "</div>\n"

        # Collect distinct countries for filter
        distinct_countries = set()
        for row in vacancy_rows:
            json_data = row.get('estimation_data', {}).get('json', {})
            country_val = json_data.get('CandidateCountry') or json_data.get('EmployerCountry')
            raw_str = ChunkHelper._extract_country_str(country_val)
            if raw_str:
                for c in raw_str.split(','):
                    c = c.strip()
                    if not c:
                        continue
                    canonical = synonym_map.get(c.lower(), c)
                    if canonical.lower() in valid_canonical_names:
                        distinct_countries.add(canonical)
        sorted_countries = sorted(list(distinct_countries))

        escaped_stats_title = stats_title.replace('"', '\\"').replace("'", "\\'")
        qualified_salaries_json = json.dumps(qualified_salaries)

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
border-bottom: 1px solid #ddd;
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
var currentStatsTitle = \"""" + escaped_stats_title + """\";
var qualifiedSalaries = """ + qualified_salaries_json + """;

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

function recalculateSalary(selectedCountries) {
var count = 0;
var sumUsdMin = 0, sumUsdMax = 0, sumEurMin = 0, sumEurMax = 0;

var checkboxes = document.querySelectorAll('#countryDropdown input[type="checkbox"][data-country]');
var useAll = selectedCountries.length === 0 || selectedCountries.length === checkboxes.length;

qualifiedSalaries.forEach(function(q) {
    var match = false;
    if (useAll) {
        match = true;
    } else {
        for (var i = 0; i < selectedCountries.length; i++) {
            if (q.countries.indexOf(selectedCountries[i]) !== -1) {
                match = true;
                break;
            }
        }
    }

    if (match) {
        count++;
        sumUsdMin += q.usdMin;
        sumUsdMax += q.usdMax;
        sumEurMin += q.eurMin;
        sumEurMax += q.eurMax;
    }
});

var statsDiv = document.getElementById('salaryStatsBlock');
var html = '<h3 style="margin-top: 0; color: #2196F3;">Salary Statistics (' + currentStatsTitle + ')</h3>';
if (count === 0) {
    html += '<p style="margin: 5px 0;"><strong>No data</strong></p>';
} else {
    var avgUsdMin = sumUsdMin / count;
    var avgUsdMax = sumUsdMax / count;
    var avgEurMin = sumEurMin / count;
    var avgEurMax = sumEurMax / count;

    html += '<p style="margin: 5px 0;"><strong>Vacancies in range (15k - 300k USD/year):</strong> ' + count + '</p>';
    html += '<p style="margin: 5px 0;"><strong>Avg USD Min:</strong> $' + avgUsdMin.toLocaleString('en-US', {maximumFractionDigits: 0}) + 
            ' | <strong>Avg USD Max:</strong> $' + avgUsdMax.toLocaleString('en-US', {maximumFractionDigits: 0}) + '</p>';
    html += '<p style="margin: 5px 0;"><strong>Avg EUR Min:</strong> €' + avgEurMin.toLocaleString('en-US', {maximumFractionDigits: 0}) + 
            ' | <strong>Avg EUR Max:</strong> €' + avgEurMax.toLocaleString('en-US', {maximumFractionDigits: 0}) + '</p>';
}
statsDiv.innerHTML = html;
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
if (nextRow && nextRow.classList.contains('collapsible-section')) {
nextRow.style.display = '';
}
} else {
row.style.display = 'none';
if (nextRow && nextRow.classList.contains('collapsible-section')) {
nextRow.style.display = 'none';
nextRow.classList.remove('show');
}
}
});

recalculateSalary(selected);
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
        # Insert stats block
        html_parts.append(stats_html)
        # Country filter dropdown with Check All/Uncheck All at the top
        html_parts.append(
            '<div class="country-filter-container">\n'
            '    <button class="country-filter-btn" onclick="toggleCountryDropdown()">\n'
            f'        <span id="countryFilterLabel">All Countries ({len(sorted_countries)})</span> ▼\n'
            '    </button>\n'
            '    <div id="countryDropdown" class="country-dropdown">\n'
            '        <div class="filter-actions">\n'
            '            <button onclick="selectAllCountries()">Check All</button>\n'
            '            <button onclick="deselectAllCountries()">Uncheck All</button>\n'
            '        </div>\n'
        )
        for country in sorted_countries:
            escaped_country = country.replace('"', '&quot;').replace("'", '&#39;')
            html_parts.append(
                f'        <label><input type="checkbox" data-country="{escaped_country}" '
                f'checked onchange="filterByCountry()"> {country}</label>\n'
            )
        html_parts.append(
            '    </div>\n'
            '</div>\n'
        )
        html_parts.append(
            '<table>\n'
            '<thead>\n'
            '<tr>\n'
            '    <th style="width: 13%;">Country</th>\n'
            '    <th style="width: 30%;">VacancyTitle</th>\n'
            '    <th style="width: 13%;">Score</th>\n'
            '    <th style="width: 13%;">Score Percentile</th>\n'
            '    <th style="width: 13%;">VacancyId</th>\n'
            '    <th style="width: 13%;">Salary</th>\n'
            '    <th style="width: 5%;"></th>\n'
            '</tr>\n'
            '</thead>\n'
            '<tbody>\n'
        )
        row_html_parts = []
        for row in vacancy_rows:
            # Extract country separately
            json_data = row.get('estimation_data', {}).get('json', {})
            country_val = json_data.get('CandidateCountry') or json_data.get('EmployerCountry')
            raw_str = ChunkHelper._extract_country_str(country_val)
            mapped_countries = []
            if raw_str:
                for c in raw_str.split(','):
                    c = c.strip()
                    if not c:
                        continue
                    canonical = synonym_map.get(c.lower(), c)
                    if canonical.lower() in valid_canonical_names:
                        if canonical not in mapped_countries:
                            mapped_countries.append(canonical)
            country_str = ", ".join(mapped_countries)
            # Build data-countries attribute for filtering (pipe-separated)
            data_countries = '|'.join(mapped_countries)
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
            salary_html = ChunkHtmlHelper._format_salary_display(
                sal_min, sal_max, sal_curr, sal_period, exchange_rates_df
            )
            # Main row
            score_str = f"{row['score']:.2f}".rstrip('0').rstrip('.')
            score_percentile_str = f"{row['score_percentile']:.2f}".rstrip('0').rstrip('.')
            escaped_data_countries = data_countries.replace('"', '&quot;')
            row_html = (
                f'            <tr class="main-row" data-countries="{escaped_data_countries}">\n'
                f'                <td>{country_str}</td>\n'
                f'                <td>{display_title}</td>\n'
                f'                <td>{score_str}</td>\n'
                f'                <td>{score_percentile_str}</td>\n'
                f'                <td>{row["vacancy_id"]}</td>\n'
                f'                <td style="font-size: 11px; line-height: 1.4;">{salary_html}</td>\n'
                '                <td><button class="collapse-btn" onclick="toggleSection(this)">[+]</button></td>\n'
                '            </tr>\n'
            )
            # Collapsible section
            row_html += (
                '            <tr class="collapsible-section">\n'
                '                <td colspan="7">\n'
            )
            # Nested table with skills comparison
            estimation_data = row.get('estimation_data', {})
            if estimation_data:
                protocol = estimation_data.get('scoring_protocol', [])
                if protocol:
                    row_html += (
                        '                    <h3>Skills Comparison</h3>\n'
                        '                    <table class="nested-table">\n'
                        '                        <thead>\n'
                        '                            <tr>\n'
                        '                                <th>Vacancy</th>\n'
                        '                                <th>Vacancy Field</th>\n'
                        '                                <th>Score</th>\n'
                        '                                <th>Score Percentile</th>\n'
                        '                                <th>Resume</th>\n'
                        '                                <th>Resume Field</th>\n'
                        '                                <th style="width: 40%;">Message</th>\n'
                        '                            </tr>\n'
                        '                        </thead>\n'
                        '                        <tbody>\n'
                    )
                    for entry in protocol:
                        left = entry.get('left', '')
                        left_field = entry.get('left_field', '')
                        score = entry.get('score', 0)
                        score_pct = entry.get('score_percentile', 0.0)
                        right = entry.get('right', '')
                        right_field = entry.get('right_field', '')
                        msg = entry.get('msg', '')
                        row_html += (
                            '                            <tr>\n'
                            f'                                <td>{left}</td>\n'
                            f'                                <td>{left_field}</td>\n'
                            f'                                <td>{score}</td>\n'
                            f'                                <td>{score_pct:.2f}</td>\n'
                            f'                                <td>{right}</td>\n'
                            f'                                <td>{right_field}</td>\n'
                            f'                                <td>{msg}</td>\n'
                            '                            </tr>\n'
                        )
                    row_html += (
                        '                        </tbody>\n'
                        '                    </table>\n'
                    )
                else:
                    row_html += (
                        '                    <h3>Skills Comparison</h3>\n'
                        '                    <p>No scoring protocol available.</p>\n'
                    )
            else:
                row_html += (
                    '                    <h3>Skills Comparison</h3>\n'
                    '                    <p>No estimation data available (both levels failed or missing).</p>\n'
                )
            # File links
            row_html += (
                '                    <h3>Files</h3>\n'
                '                    <div>\n'
            )
            if os.path.exists(row['json_path']):
                p = row["json_path"].replace(chr(92), "/")
                row_html += f'                        <a href="file:///{p}" class="file-link">📄 JSON</a>\n'
            if os.path.exists(row['txt_path']):
                p = row["txt_path"].replace(chr(92), "/")
                row_html += f'                        <a href="file:///{p}" class="file-link">📄 TXT</a>\n'
            if os.path.exists(row['mhtml_path']):
                p = row["mhtml_path"].replace(chr(92), "/")
                row_html += f'                        <a href="file:///{p}" class="file-link">📄 MHTML</a>\n'
            if row.get('vacancy_url'):
                v_url = row['vacancy_url']
                row_html += f'                        <a href="{v_url}" class="file-link" target="_blank">🔗 Vacancy URL</a>\n'
            if row.get('apply_url'):
                a_url = row['apply_url']
                row_html += f'                        <a href="{a_url}" class="file-link" target="_blank">🔗 Apply URL</a>\n'
            row_html += (
                '                    </div>\n'
            )
            # Vacancy text (strip URLs)
            clean_vacancy_text = re.sub(r'https?://\S+', '', row['vacancy_text'])
            row_html += (
                '                    <h3>Vacancy Text</h3>\n'
                f'                    <div class="vacancy-text">{clean_vacancy_text}</div>\n'
                '                </td>\n'
                '            </tr>\n'
            )
            row_html_parts.append(row_html)
        html_parts.append("".join(row_html_parts))
        html_parts.append(
            '        </tbody>\n'
            '</table>\n'
            '</body>\n'
            '</html>\n'
        )
        return "".join(html_parts)