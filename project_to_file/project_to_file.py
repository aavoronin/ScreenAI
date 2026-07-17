import os
from pathlib import Path
from charset_normalizer import from_path
from cfg.cfg import Config


def detect_and_read_file(file_path: Path) -> str:
    """
    Detect file encoding using charset-normalizer and return content as string.
    Normalizes all line endings to Unix-style (\n) for consistent output.
    """
    try:
        # Use charset-normalizer for automatic encoding detection
        result = from_path(file_path).best()
        if result:
            content = str(result)
            # Normalize line endings: \r\n → \n, \r → \n
            return content.replace('\r\n', '\n').replace('\r', '\n')
    except Exception:
        pass

    # Fallback: try common encodings with explicit newline handling
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'ascii']:
        try:
            with open(file_path, 'r', encoding=encoding, errors='strict', newline='') as f:
                content = f.read()
                return content.replace('\r\n', '\n').replace('\r', '\n')
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort: read with utf-8 and ignore errors
    with open(file_path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
        content = f.read()
        return content.replace('\r\n', '\n').replace('\r', '\n')


PROMPT = """
INPUT FORMAT:
The input contains concatenated files delimited by:
'========== START FileName.py =========='
...code...
'========== END FileName.py =========='
These markers are for parsing only and must NEVER appear in the output.

OUTPUT FORMAT:
- Return ONLY modified or newly created files.
- Each file must be in a separate markdown code block with the correct language identifier.
- Precede each block with the exact filename (e.g., ### 📄 FileName.py).
- Output complete, runnable file contents. No diffs, no partial snippets.
- Omit unchanged files entirely.

CODING STANDARDS:
1. All comments and user-facing strings must be in English.
2. DO NOT translate technical identifiers, tag names, file paths, API keys, or environment variables.
3. Keep lines ≤80 characters where practical, without breaking syntax or readability.
4. Preserve all existing comments verbatim. Do not delete, rephrase, or move them unless they directly contradict the new logic.
5. Apply ONLY the requested changes. Do not refactor, optimize, reformat, or touch unrelated code.
6. Do NOT add "change log", "modified", or "TODO" comments. Comments must only explain logic, behavior, or business rules.
7. Update imports, dependencies, or configuration if required by the changes.
8. If requirements are ambiguous or conflicting, pause and ask for clarification instead of guessing.
9. Do not add or delete empty lines in the places where code was not changed.
"""


def concatenate_project_files(project_path, output_filename='combined_output.txt'):
    root = Path(project_path)
    output_path = root / output_filename

    # Supported file extensions
    IMAGE_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif",
        ".webp", ".ico", ".svg", ".raw", ".heic", ".heif", ".jfif",
        ".pjpeg", ".pjp", ".apng", ".avif"
    }

    DOCUMENT_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".rtf", ".odt", ".ods", ".odp", ".csv", ".xml",
        ".json", ".md", ".html", ".htm", ".epub", ".mobi"
    }

    exclude_dirs = {'weights', '.idea', '__pycache__', '.venv',
                    '.git', 'premsql', "TestCases", "out"}
    exclude_extensions = {'.pyc', '.pyo', '.pyd', '.mhtml',
                          '.cmd', '.ipynb', '.ipynb_checkpoints',
                          '.ipynb_media', '.sh',
                          ".safetensors"} | set(IMAGE_EXTENSIONS) | set(DOCUMENT_EXTENSIONS)
    exclude_filenames = {'.env', '.DS_Store', output_filename, ".gitignore"}
    exclude_specific_paths = {'download/my_token.py', 'README.md', 'combined_output.txt'}

    # Write with newline='' to prevent double-conversion of \n on Windows
    with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
        outfile.write(PROMPT)
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue

            if any(part in exclude_dirs for part in path.parts):
                continue
            if path.suffix in exclude_extensions:
                continue
            if path.name in exclude_filenames:
                continue

            relative_path = path.relative_to(root)
            if relative_path.as_posix() in exclude_specific_paths:
                continue

            outfile.write(f"=====START {relative_path} =====\n")
            try:
                content = detect_and_read_file(path)
                outfile.write(content)
            except Exception as e:
                outfile.write(f"\n[Error reading file: {e}]\n")
            outfile.write(f"\n=====END {relative_path} =====\n")
            print(relative_path)


def project_to_file_main():
    config = Config()
    PROJECT_PATH = config.get_path('project_path')
    concatenate_project_files(PROJECT_PATH)
    print(f"Done: {PROJECT_PATH}\\combined_output.txt")

    #PROJECT_PATH = r'C:\Py\ImageGeneration'
    #concatenate_project_files(PROJECT_PATH)
    #print(f"Done: {PROJECT_PATH}\\combined_output.txt")