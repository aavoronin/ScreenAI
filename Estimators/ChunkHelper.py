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
        return chunk_filepath