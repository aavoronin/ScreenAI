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
    def generate_salary_summary_html(
        filepath,
        country_rows,
        total_data,
        period_start_str,
        period_end_str
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

        period_text = f"Period: {period_start_str} - {period_end_str}"
        html_parts.append(
            f'<p>{HtmlHelper._escape_html(period_text)}</p>\n'
        )

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

                html_parts.append(
                    '            <tr>\n'
                    f'                <td>{rownum}</td>\n'
                    f'                <td>'
                    f'{HtmlHelper._escape_html(row["country"])}'
                    f'</td>\n'
                    f'                <td>{row["count"]}</td>\n'
                    f'                <td>{usd_range}</td>\n'
                    f'                <td>{eur_range}</td>\n'
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
    def generate_missing_skills_html(
        filepath,
        skill_rows,
        required_language_rows,
        period_start_str,
        period_end_str
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

        period_text = f"Period: {period_start_str} - {period_end_str}"
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