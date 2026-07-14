from project_to_file.project_to_file import project_to_file_main
if __name__ == "__main__":
    project_to_file_main()

import os
import sys
import json
import glob
from PIL import Image
import torch
from llama_cpp import llama_supports_gpu_offload

# ==========================================
# GPU SYSTEM CHECK
# ==========================================
print("=" * 60)
print("🔌 GPU SYSTEM CHECK")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Active GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version: {torch.version.cuda}")
    print('llama GPU Offload Supported:', llama_supports_gpu_offload())
else:
    print("⚠️ WARNING: CUDA is not available. Models will run on CPU.")
print("=" * 60)


# ==========================================
# CONFIGURATION
# ==========================================
INPUT_DIR = r"C:\Py\ScreenAI\screens"
OUTPUT_DIR = r"C:\Py\ScreenAI\parsed screens"

# IMPORTANT: Use lowercase 'omniparser' to exactly match your git clone command
OMNIPARSER_REPO_PATH = r"C:\Py\ScreenAI\omniparser"

# Add the cloned repo to your Python path
sys.path.append(OMNIPARSER_REPO_PATH)

# Ensure directories exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# IMPORT OMNIPARSER UTILITIES (v2.0 API)
# ==========================================
# In v2.0, utilities are located in util.utils, NOT utils
from omniparser.util.utils import (
    check_ocr_box,
    get_yolo_model,
    get_caption_model_processor,
    get_som_labeled_img
)


# ==========================================
# INITIALIZE MODELS
# ==========================================
print("\n🔄 Loading YOLO model... (this may take a moment on first run)")
# v2.0 uses a specific structure for weights downloaded via HF
yolo_model_path = os.path.join(OMNIPARSER_REPO_PATH, "weights", "icon_detect", "model.pt")
yolo_model = get_yolo_model(model_path=yolo_model_path)

print("🔄 Loading Caption model (Florence-2)...")
caption_model_path = os.path.join(OMNIPARSER_REPO_PATH, "weights", "icon_caption_florence")
caption_model_processor = get_caption_model_processor(
    model_name="florence2",
    model_name_or_path=caption_model_path
)


# ==========================================
# PARSING & SEMANTIC EXTRACTION LOGIC
# ==========================================
def parse_and_extract(image_path):
    filename = os.path.basename(image_path)
    print(f"\n--- Processing: {filename} ---")

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"  ⚠️ Could not open image: {e}")
        return

    # 1. Run OCR first (required by the v2.0 pipeline)
    # Note: use_paddleocr=False means it uses EasyOCR, bypassing PaddleOCR entirely
    ocr_bbox_rslt, _ = check_ocr_box(
        img,
        display_img=False,
        output_bb_format='xyxy',
        easyocr_args={'paragraph': False, 'text_threshold': 0.9},
        use_paddleocr=False
    )
    ocr_text, ocr_bbox = ocr_bbox_rslt

    # 2. Run the main OmniParser inference pipeline (v2.0 signature)
    print("  ⏳ Running OmniParser inference...")
    annotated_image_b64, label_coordinates, parsed_content_list = get_som_labeled_img(
        image_source=img,
        model=yolo_model,
        BOX_TRESHOLD=0.05,
        output_coord_in_ratio=True,
        ocr_bbox=ocr_bbox,
        caption_model_processor=caption_model_processor,
        ocr_text=ocr_text,
        use_local_semantics=True,
        iou_threshold=0.9
    )

    # 3. Print specific elements to console as requested
    found_items = False
    for el in parsed_content_list:
        el_type = str(el.get('type', '')).lower()
        bbox = el.get('bbox', [])
        content = str(el.get('content', '')).strip()
        is_interactive = el.get('interactivity', False)

        # Clickable Links
        if is_interactive and ('http' in content.lower() or 'link' in el_type):
            print(f"  🔗 [LINK] Text: '{content}' | BBox: {bbox}")
            found_items = True

        # Buttons (Interactive elements with text)
        elif is_interactive and ('button' in content.lower() or el_type == 'icon'):
            if content and content.lower() != "none":
                print(f"  🔘 [BUTTON] Text: '{content}' | BBox: {bbox}")
                found_items = True

        # Scrollbars
        elif 'scroll' in content.lower() or 'scroll' in el_type:
            print(f"  📜 [SCROLLBAR] BBox: {bbox} | Arrows: Up, Down, Left, Right")
            found_items = True

    if not found_items:
        print("  ℹ️ No specific links, buttons, or scrollbars detected.")

    # 4. Save the full parsed data to the output folder
    base_name = os.path.splitext(filename)[0]
    output_file = os.path.join(OUTPUT_DIR, f"{base_name}.json")

    save_data = {
        "filename": filename,
        "label_coordinates": label_coordinates,
        "parsed_elements": parsed_content_list
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4, ensure_ascii=False)

    print(f"  💾 Saved parsed data to: {output_file}")


# ==========================================
# MAIN EXECUTION LOOP
# ==========================================
if __name__ == "__main__":
    print(f"\n🔍 Scanning for PNG files in: {INPUT_DIR}")
    png_files = glob.glob(os.path.join(INPUT_DIR, "*.png"))

    if not png_files:
        print(f"⚠️ No PNG files found in {INPUT_DIR}.")
        print("💡 Please place your screenshot files (e.g., screen00001.png) in this folder and run again.")
    else:
        print(f"✅ Found {len(png_files)} screenshots to process.\n")
        for file_path in png_files:
            parse_and_extract(file_path)

    print("\n🎉 All screens processed successfully!")