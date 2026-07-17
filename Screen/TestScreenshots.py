import os
import sys
import json
import glob
from PIL import Image
from Screen.LinkedInScreenParser import LinkedInScreenParser
from Screen.ScreenParser import ScreenParser
from cfg.cfg import Config

# ==========================================
# CONFIGURATION
# ==========================================
config = Config()
INPUT_DIR = config.get_path('input_dir')
OUTPUT_DIR = config.get_path('output_dir')
OMNIPARSER_REPO_PATH = config.get_path('omniparser_repo_path')


def test_screenshots():
    # Ensure directories exist
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n🔍 Scanning for PNG files in: {INPUT_DIR}")
    png_files = glob.glob(os.path.join(INPUT_DIR, "*.png"))

    if not png_files:
        print(f"⚠️ No PNG files found in {INPUT_DIR}.")
        print("💡 Please place your screenshot files (e.g., screen00001.png) "
              "in this folder and run again.")
    else:
        print(f"✅ Found {len(png_files)} screenshots to process.\n")

        # Initialize the parser once
        parser = LinkedInScreenParser(OMNIPARSER_REPO_PATH)

        for file_path in png_files:
            filename = os.path.basename(file_path)
            print(f"--- Processing: {filename} ---")

            try:
                img = Image.open(file_path).convert("RGB")
            except Exception as e:
                print(f"  ⚠️ Could not open image: {e}")
                continue

            # Parse the screen
            print("  ⏳ Running OmniParser inference...")
            parser.parse_screen(img)

            parsed_content_list = parser.get_bboxes()
            label_coordinates = parser.get_label_coordinates()

            # Print specific elements to console as requested
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

            # Save the full parsed data to the output folder
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

            # Draw and save the expanded parsed image
            parsed_image_path = os.path.join(OUTPUT_DIR, f"{base_name}_parsed.png")
            parser.draw_and_save_parsed_image(parsed_image_path)
            print(f"  🖼️ Saved parsed image to: {parsed_image_path}")

        print("\n🎉 All screens processed successfully!")