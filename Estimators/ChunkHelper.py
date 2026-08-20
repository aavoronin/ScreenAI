import os
import json
from datetime import datetime


class ChunkHelper:
    """
    Helper class for creating and saving bulk JSON chunks of vacancy data.
    """

    @staticmethod
    def save_bulk_json_chunk(folder, selected_files):
        """
        Save a bulk JSON chunk containing the parsed vacancy data.
        The chunk is saved in the 'Chunks' directory relative to the folder.
        Vacancies are sorted by score before saving.
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

                # Ensure file paths are included in the chunk data
                data['json_path'] = v.get('json_path')
                data['txt_path'] = v.get('txt_path')
                data['html_path'] = v.get('html_path')

                chunk_data[vid] = data
            except Exception as e:
                chunk_data[vid] = {
                    "error": f"json for vacancy {os.path.basename(json_path)} was faulty: {str(e)}"
                }

        # Sort chunk_data by score_percentile desc, then by score desc
        def get_sort_key(item):
            vid, data = item
            score = 0
            pct = 0.0
            if 'estimation2' in data and data['estimation2'].get('score') is not None:
                score = data['estimation2']['score']
                pct = data['estimation2'].get('score_percentile', 0.0)
            elif 'estimation1' in data and data['estimation1'].get('score') is not None:
                score = data['estimation1']['score']
                pct = data['estimation1'].get('score_percentile', 0.0)
            return (-pct, -score)

        sorted_items = sorted(chunk_data.items(), key=get_sort_key)
        chunk_data = dict(sorted_items)

        with open(chunk_filepath, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved bulk JSON chunk to: {chunk_filepath}")

        # Create HTML summary file
        ChunkHelper._create_html_summary(chunk_filepath)
        return chunk_filepath

    @staticmethod
    def _create_html_summary(chunk_filepath):
        """
        Create an HTML file with a summary table of vacancies.
        Reads the chunk JSON file directly and can be called separately.
        """
        with open(chunk_filepath, 'r', encoding='utf-8') as f:
            chunk_data = json.load(f)

        html_filepath = os.path.splitext(chunk_filepath)[0] + '.html'

        vacancy_rows = []
        for vid, vacancy_data in chunk_data.items():
            if "error" in vacancy_data:
                continue

            score = 0
            score_percentile = 0.0
            estimation_data = {}
            if 'estimation2' in vacancy_data and vacancy_data['estimation2'].get('score') is not None:
                score = vacancy_data['estimation2']['score']
                score_percentile = vacancy_data['estimation2'].get('score_percentile', 0.0)
                estimation_data = vacancy_data['estimation2']
            elif 'estimation1' in vacancy_data and vacancy_data['estimation1'].get('score') is not None:
                score = vacancy_data['estimation1']['score']
                score_percentile = vacancy_data['estimation1'].get('score_percentile', 0.0)
                estimation_data = vacancy_data['estimation1']

            vacancy_title = ""
            if estimation_data.get('json'):
                vacancy_title = estimation_data['json'].get('Title', '')

            # Get file paths directly from the vacancy JSON data
            json_path = vacancy_data.get('json_path')
            txt_path = vacancy_data.get('txt_path')
            html_path = vacancy_data.get('html_path')

            vacancy_text = ""
            if txt_path and os.path.exists(txt_path):
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
                'json_path': json_path,
                'txt_path': txt_path,
                'html_path': html_path,
                'vacancy_text': vacancy_text
            })

        html_content = ChunkHelper._generate_html_table(vacancy_rows)

        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ Created HTML summary: {html_filepath}")

    @staticmethod
    def _generate_html_table(vacancy_rows):
        """Generate HTML table with collapsible sections."""
        html = """<!DOCTYPE html>
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
</script>
</head>
<body>
<h1>Vacancy Estimation Summary</h1>
<table>
<thead>
<tr>
<th>Score</th>
<th>Score Percentile</th>
<th>VacancyId</th>
<th>VacancyTitle</th>
<th></th>
</tr>
</thead>
<tbody>
"""
        for row in vacancy_rows:
            # Main row
            html += f"""            <tr>
<td>{row['score']}</td>
<td>{row['score_percentile']:.2f}</td>
<td>{row['vacancy_id']}</td>
<td>{row['title']}</td>
<td><button class="collapse-btn" onclick="toggleSection(this)">[+]</button></td>
</tr>
"""
            # Collapsible section
            html += f"""            <tr class="collapsible-section">
<td colspan="5">
"""
            # Nested table with skills comparison
            estimation_data = row.get('estimation_data', {})
            protocol = estimation_data.get('scoring_protocol', [])
            if protocol:
                html += """                    <h3>Skills Comparison</h3>
<table class="nested-table">
<thead>
<tr>
<th>Left</th>
<th>Left Field</th>
<th>Score</th>
<th>Score Percentile</th>
<th>Right</th>
<th>Right Field</th>
<th>Message</th>
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
                    html += f"""                            <tr>
<td>{left}</td>
<td>{left_field}</td>
<td>{score}</td>
<td>{score_pct:.2f}</td>
<td>{right}</td>
<td>{right_field}</td>
<td>{msg}</td>
</tr>
"""
                html += """                        </tbody>
</table>
"""
            # File links
            html += """                    <h3>Files</h3>
<div>
"""

            def make_link(path, label):
                if path and os.path.exists(path):
                    safe_path = path.replace(os.sep, "/")
                    return f'                        <a href="file:///{safe_path}" class="file-link">{label}</a>\n'
                else:
                    return f'                        <span class="disabled-link">{label}</span>\n'

            html += make_link(row.get('json_path'), '📄 JSON')
            html += make_link(row.get('txt_path'), '📄 TXT')
            html += make_link(row.get('html_path'), '📄 HTML')

            html += """                    </div>
"""
            # Vacancy text
            html += f"""                    <h3>Vacancy Text</h3>
<div class="vacancy-text">{row['vacancy_text']}</div>
</td>
</tr>
"""
        html += """        </tbody>
</table>
</body>
</html>
"""
        return html