import os
import csv
from Estimators.ChunkHelper import ChunkHelper
from Estimators.ExchangeRates import ExchangeRates


class HtmlHelper:
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
    def _format_income_or_savings(val_min, val_max, currency_symbol):
        if val_min is None or val_max is None:
            return "-"
        return f"{currency_symbol}{val_min:,.2f} - {currency_symbol}{val_max:,.2f}"

    @staticmethod
    def _load_country_taxes_and_expenses():
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            r'data\country_taxes_and_expenses.csv'
        )
        data = {}
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    country = row.get('country', '').strip()
                    try:
                        tax = float(row.get('tax', 0))
                        expenses = float(row.get('expenses', 0))
                        data[country] = {'tax': tax, 'expenses': expenses}
                    except ValueError:
                        continue
        return data

    @staticmethod
    def generate_salary_summary_html(
            filepath,
            country_rows,
            total_data,
            period_end_str,
            days_covered
    ):
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
        period_text = f"Period end: {period_end_str} ({days_covered} days covered)"
        html_parts.append(
            f'<p>{HtmlHelper._escape_html(period_text)}</p>\n'
        )

        tax_expenses_data = HtmlHelper._load_country_taxes_and_expenses()
        exchange_rates_df = ExchangeRates.get_currencies()

        total_count = 0
        if total_data:
            total_count = total_data.get('count', 0)

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
                '    <th>Tax (%)</th>\n'
                '    <th>Income (USD/EUR)</th>\n'
                '    <th>Expenses (Month/Year USD)</th>\n'
                '    <th>Savings (USD/EUR)</th>\n'
                '</tr>\n'
                '</thead>\n'
                '<tbody>\n'
            )

            rownum = 1
            for row in country_rows:
                usd_range = HtmlHelper._format_salary_range(
                    row.get('avg_usd_min'),
                    row.get('avg_usd_max'),
                    '$'
                )
                eur_range = HtmlHelper._format_salary_range(
                    row.get('avg_eur_min'),
                    row.get('avg_eur_max'),
                    '€'
                )

                count_val = row.get('count', 0)
                vacancy_count_val = row.get('vacancy_count', int(count_val))
                count_str = f"{count_val:.2f} ({vacancy_count_val})"

                country_name = row.get('country', '')
                te = tax_expenses_data.get(country_name, {})
                is_mapped = country_name in tax_expenses_data

                tax_val = te.get('tax', 0)
                expenses_month_usd = te.get('expenses', 0)
                expenses_year_usd = expenses_month_usd * 12

                if is_mapped:
                    tax_str = f"{tax_val}%"
                    expenses_str = (
                        f"${expenses_month_usd:,.0f} / "
                        f"${expenses_year_usd:,.0f}"
                    )
                else:
                    tax_str = "-"
                    expenses_str = "-"

                avg_usd_min = row.get('avg_usd_min')
                avg_usd_max = row.get('avg_usd_max')
                avg_eur_min = row.get('avg_eur_min')
                avg_eur_max = row.get('avg_eur_max')

                if is_mapped and avg_usd_min is not None and avg_usd_max is not None:
                    tax_pct = tax_val / 100.0
                    inc_usd_min = round(avg_usd_min * (1 - tax_pct), 2)
                    inc_usd_max = round(avg_usd_max * (1 - tax_pct), 2)
                    inc_eur_min = (
                        round(avg_eur_min * (1 - tax_pct), 2)
                        if avg_eur_min is not None else None
                    )
                    inc_eur_max = (
                        round(avg_eur_max * (1 - tax_pct), 2)
                        if avg_eur_max is not None else None
                    )

                    if inc_usd_min < 0:
                        inc_usd_min = 0
                    if inc_usd_max < 0:
                        inc_usd_max = 0
                    if inc_eur_min is not None and inc_eur_min < 0:
                        inc_eur_min = 0
                    if inc_eur_max is not None and inc_eur_max < 0:
                        inc_eur_max = 0

                    expenses_eur = ChunkHelper._convert_currency(
                        expenses_year_usd, 'USD', 'EUR', exchange_rates_df
                    )
                    if expenses_eur is None:
                        expenses_eur = 0.0
                    else:
                        expenses_eur = round(expenses_eur, 2)

                    sav_usd_min = round(inc_usd_min - expenses_year_usd, 2)
                    sav_usd_max = round(inc_usd_max - expenses_year_usd, 2)
                    sav_eur_min = (
                        round(inc_eur_min - expenses_eur, 2)
                        if inc_eur_min is not None else None
                    )
                    sav_eur_max = (
                        round(inc_eur_max - expenses_eur, 2)
                        if inc_eur_max is not None else None
                    )

                    if sav_usd_min < 0:
                        sav_usd_min = 0
                    if sav_usd_max < 0:
                        sav_usd_max = 0
                    if sav_eur_min is not None and sav_eur_min < 0:
                        sav_eur_min = 0
                    if sav_eur_max is not None and sav_eur_max < 0:
                        sav_eur_max = 0

                    inc_usd_str = HtmlHelper._format_income_or_savings(
                        inc_usd_min, inc_usd_max, '$'
                    )
                    inc_eur_str = HtmlHelper._format_income_or_savings(
                        inc_eur_min, inc_eur_max, '€'
                    )
                    income_str = f"{inc_usd_str}<br>{inc_eur_str}"

                    sav_usd_str = HtmlHelper._format_income_or_savings(
                        sav_usd_min, sav_usd_max, '$'
                    )
                    sav_eur_str = HtmlHelper._format_income_or_savings(
                        sav_eur_min, sav_eur_max, '€'
                    )
                    savings_str = f"{sav_usd_str}<br>{sav_eur_str}"
                else:
                    income_str = "-"
                    savings_str = "-"

                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{rownum}</td>\n'
                    f'                <td>'
                    f'{HtmlHelper._escape_html(country_name)}'
                    f'</td>\n'
                    f'                <td>{count_str}</td>\n'
                    f'                <td>{usd_range}</td>\n'
                    f'                <td>{eur_range}</td>\n'
                    f'                <td>{tax_str}</td>\n'
                    f'                <td style="font-size: 12px; '
                    f'line-height: 1.4;">{income_str}</td>\n'
                    f'                <td>{expenses_str}</td>\n'
                    f'                <td style="font-size: 12px; '
                    f'line-height: 1.4;">{savings_str}</td>\n'
                    '            </tr>\n'
                )
                rownum += 1

            if total_count > 0:
                total_usd_range = HtmlHelper._format_salary_range(
                    total_data.get('avg_usd_min'),
                    total_data.get('avg_usd_max'),
                    '$'
                )
                total_eur_range = HtmlHelper._format_salary_range(
                    total_data.get('avg_eur_min'),
                    total_data.get('avg_eur_max'),
                    '€'
                )
            else:
                total_usd_range = "-"
                total_eur_range = "-"

            total_vacancy_count_val = (
                total_data.get('vacancy_count', int(total_count))
                if total_data else 0
            )
            total_count_str = f"{total_count:.2f} ({total_vacancy_count_val})"

            html_parts.append(
                '            <tr class="total-row">\n'
                '                <td></td>\n'
                '                <td>Total</td>\n'
                f'                <td>{total_count_str}</td>\n'
                f'                <td>{total_usd_range}</td>\n'
                f'                <td>{total_eur_range}</td>\n'
                '                <td>-</td>\n'
                '                <td>-</td>\n'
                '                <td>-</td>\n'
                '                <td>-</td>\n'
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
    def generate_missing_skills_html(
            filepath,
            skill_rows,
            required_language_rows,
            period_end_str,
            days_covered
    ):
        skill_rows = skill_rows or []
        required_language_rows = required_language_rows or []

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
h2 {
    margin-top: 30px;
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
        period_text = f"Period end: {period_end_str} ({days_covered} days covered)"
        html_parts.append(
            f'<p>{HtmlHelper._escape_html(period_text)}</p>\n'
        )

        html_parts.append('<h2>Required Languages</h2>\n')
        if required_language_rows:
            html_parts.append(
                f'<p>Total required languages: '
                f'{len(required_language_rows)}</p>\n'
                '<table>\n'
                '<thead>\n'
                '<tr>\n'
                '    <th>#</th>\n'
                '    <th>Required Language</th>\n'
                '    <th>Vacancies</th>\n'
                '</tr>\n'
                '</thead>\n'
                '<tbody>\n'
            )
            for i, row in enumerate(required_language_rows, start=1):
                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{i}</td>\n'
                    f'                <td>'
                    f'{HtmlHelper._escape_html(row["language"])}'
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
                '<p>No required languages found for the period.</p>\n'
            )

        html_parts.append('<h2>Missing Skills</h2>\n')
        if skill_rows:
            html_parts.append(
                f'<p>Total unique missing skills: {len(skill_rows)}</p>\n'
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
            for i, row in enumerate(skill_rows, start=1):
                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{i}</td>\n'
                    f'                <td>'
                    f'{HtmlHelper._escape_html(row["skill"])}'
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

    @staticmethod
    def generate_all_skills_html(
            filepath,
            skill_rows,
            period_end_str,
            days_covered
    ):
        skill_rows = skill_rows or []

        html_parts = []
        html_parts.append("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>All Skills Summary</title>
<style>
body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background-color: #f5f5f5;
}
h2 {
    margin-top: 30px;
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
<h1>All Skills Summary</h1>
""")
        period_text = f"Period end: {period_end_str} ({days_covered} days covered)"
        html_parts.append(
            f'<p>{HtmlHelper._escape_html(period_text)}</p>\n'
        )

        html_parts.append('<h2>All Skills</h2>\n')
        if skill_rows:
            html_parts.append(
                f'<p>Total unique skills: {len(skill_rows)}</p>\n'
                '<table>\n'
                '<thead>\n'
                '<tr>\n'
                '    <th>#</th>\n'
                '    <th>Skill</th>\n'
                '    <th>Vacancies</th>\n'
                '</tr>\n'
                '</thead>\n'
                '<tbody>\n'
            )
            for i, row in enumerate(skill_rows, start=1):
                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{i}</td>\n'
                    f'                <td>'
                    f'{HtmlHelper._escape_html(row["skill"])}'
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
                '<p>No skills found for the period.</p>\n'
            )

        html_parts.append(
            '</body>\n'
            '</html>\n'
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(''.join(html_parts))