import os
import re
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
        ChunkHelper._create_mhtml_summary(chunk_filepath, chunk_data, selected_files, chunks_dir)

        return chunk_filepath

    @staticmethod
    def _create_mhtml_summary(chunk_filepath, chunk_data, selected_files, chunks_dir):
        """
        Create an MHTML file with a summary table of vacancies.
        """
        # Create MHTML filename (same as chunk but with .mhtml extension)
        mhtml_filepath = os.path.splitext(chunk_filepath)[0] + '.html'

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

            # Get vacancy title
            vacancy_title = ""
            if est1.get('json'):
                vacancy_title = est1['json'].get('Title', '')
            elif est2.get('json'):
                vacancy_title = est2['json'].get('Title', '')

            # Get file paths
            base_path = os.path.splitext(v['json_path'])[0]
            txt_path = base_path + '.txt'
            mhtml_path = base_path + '.mhtml'

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
                'vacancy_text': vacancy_text
            })

        # Sort by score_percentile desc, then by score desc
        vacancy_rows.sort(key=lambda x: (-x['score_percentile'], -x['score']))

        # Generate HTML
        html_content = ChunkHelper._generate_html_table(vacancy_rows)

        # Save as MHTML
        with open(mhtml_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Created MHTML summary: {mhtml_filepath}")

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
            html += """            <tr class="collapsible-section">
                <td colspan="5">
"""

            # Nested table with skills comparison
            estimation_data = row.get('estimation_data', {})

            if estimation_data:
                protocol = estimation_data.get('scoring_protocol', [])
                if protocol:
                    html += """                    <h3>Skills Comparison</h3>
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
                else:
                    html += """                    <h3>Skills Comparison</h3>
                    <p>No scoring protocol available.</p>
"""
            else:
                html += """                    <h3>Skills Comparison</h3>
                    <p>No estimation data available (both levels failed or missing).</p>
"""

            # File links
            html += """                    <h3>Files</h3>
                    <div>
"""
            if os.path.exists(row['json_path']):
                html += f'                        <a href="file:///{row["json_path"].replace("\\\\", "/")}" class="file-link">📄 JSON</a>\n'
            if os.path.exists(row['txt_path']):
                html += f'                        <a href="file:///{row["txt_path"].replace("\\\\", "/")}" class="file-link">📄 TXT</a>\n'
            if os.path.exists(row['mhtml_path']):
                html += f'                        <a href="file:///{row["mhtml_path"].replace("\\\\", "/")}" class="file-link">📄 MHTML</a>\n'

            html += """                    </div>
"""

            # Vacancy text (strip URLs)
            clean_vacancy_text = re.sub(r'https?://\S+', '', row['vacancy_text'])
            html += f"""                    <h3>Vacancy Text</h3>
        <div class="vacancy-text">{clean_vacancy_text}</div>
        </td>
        </tr>
        """

        html += """        </tbody>
    </table>
</body>
</html>
"""

        return html