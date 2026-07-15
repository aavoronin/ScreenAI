import os
import sys
import glob
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch

# ==========================================
# PATH CONFIGURATION
# ==========================================
# Get the project root directory (C:\Py\ScreenAI)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# Add project root to sys.path to allow 'import omniparser'
if project_root not in sys.path:
    sys.path.append(project_root)

# Add omniparser directory to sys.path to satisfy internal imports
omniparser_path = os.path.join(project_root, "omniparser")
if omniparser_path not in sys.path:
    sys.path.append(omniparser_path)

from omniparser.util.utils import (
    check_ocr_box,
    get_yolo_model,
    get_caption_model_processor,
    get_som_labeled_img
)


class ScreenParser:
    def __init__(self, omniparser_repo_path: str):
        self.omniparser_repo_path = omniparser_repo_path
        self._parsed_content_list = None
        self._label_coordinates = None
        self._original_image = None
        self._expanded_image = None

        # --- Custom Symbol Recognition Setup ---
        self._custom_templates = {}
        custom_images_dir = os.path.join(project_root, "custom_images")
        if os.path.exists(custom_images_dir):
            print("🔄 Loading custom symbol templates...")
            for folder_name in os.listdir(custom_images_dir):
                folder_path = os.path.join(custom_images_dir, folder_name)
                if os.path.isdir(folder_path):
                    self._custom_templates[folder_name] = []
                    for img_file in os.listdir(folder_path):
                        img_path = os.path.join(folder_path, img_file)
                        # Load as grayscale for better matching performance
                        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if img is not None:
                            # Resize to 32x32 as requested
                            img_resized = cv2.resize(img, (32, 32))
                            self._custom_templates[folder_name].append(img_resized)
            print(f"   Loaded {len(self._custom_templates)} symbol types.")
        else:
            print("⚠️ custom_images folder not found. Custom symbol detection disabled.")
        # -------------------------------------

        print("🔄 Loading YOLO model...")
        yolo_model_path = os.path.join(
            self.omniparser_repo_path, "weights", "icon_detect", "model.pt"
        )
        self.yolo_model = get_yolo_model(model_path=yolo_model_path)

        print("🔄 Loading Caption model (Florence-2)...")
        caption_model_path = os.path.join(
            self.omniparser_repo_path, "weights", "icon_caption_florence"
        )
        self.caption_model_processor = get_caption_model_processor(
            model_name="florence2",
            model_name_or_path=caption_model_path
        )

    def cleanup(self):
        self._parsed_content_list = None
        self._label_coordinates = None
        self._original_image = None
        self._expanded_image = None

    def _detect_custom_symbols(self):
        """
        Scans the current image for custom templates and appends matches
        to self._parsed_content_list.
        """
        if not self._custom_templates or self._original_image is None:
            return

        # Convert PIL image to OpenCV format (Grayscale)
        screen_np = np.array(self._original_image.convert('L'))
        h, w = screen_np.shape

        # We use a threshold of 0.8 (80% match confidence)
        threshold = 0.8

        for symbol_name, templates in self._custom_templates.items():
            for template in templates:
                # Perform template matching
                res = cv2.matchTemplate(screen_np, template, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= threshold)

                # Iterate through all matches
                for pt in zip(*loc[::-1]):
                    x1, y1 = pt
                    # Template is 32x32
                    x2, y2 = x1 + 32, y1 + 32

                    # Normalize coordinates to 0.0 - 1.0 range for OmniParser compatibility
                    norm_box = [x1 / w, y1 / h, x2 / w, y2 / h]

                    # Add to the parsed list
                    self._parsed_content_list.append({
                        'type': 'icon',
                        'bbox': norm_box,
                        'content': symbol_name,
                        'interactivity': True,
                        'source': 'custom_template_match'
                    })

    def parse_screen(self, image: Image.Image):
        self.cleanup()
        self._original_image = image.convert("RGB")

        ocr_bbox_rslt, _ = check_ocr_box(
            self._original_image,
            display_img=False,
            output_bb_format='xyxy',
            easyocr_args={'paragraph': False, 'text_threshold': 0.9},
            use_paddleocr=False
        )
        ocr_text, ocr_bbox = ocr_bbox_rslt

        _, self._label_coordinates, self._parsed_content_list = get_som_labeled_img(
            image_source=self._original_image,
            model=self.yolo_model,
            BOX_TRESHOLD=0.05,
            output_coord_in_ratio=True,
            ocr_bbox=ocr_bbox,
            caption_model_processor=self.caption_model_processor,
            ocr_text=ocr_text,
            use_local_semantics=True,
            iou_threshold=0.9
        )

        # Run custom symbol detection after standard parsing
        self._detect_custom_symbols()

        return self._parsed_content_list

    def get_bboxes(self):
        return self._parsed_content_list

    def get_label_coordinates(self):
        return self._label_coordinates

    def _draw_single_bbox(self, draw: ImageDraw.ImageDraw, bbox: list, label: str, font, new_width: int,
                          new_height: int, outline_color: str = "red"):
        if len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            abs_x1 = int(x1 * new_width)
            abs_y1 = int(y1 * new_height)
            abs_x2 = int(x2 * new_width)
            abs_y2 = int(y2 * new_height)

            draw.rectangle(
                [abs_x1, abs_y1, abs_x2, abs_y2],
                outline=outline_color,
                width=12
            )

            text_bbox = draw.textbbox((abs_x1, abs_y1), label, font=font)
            draw.rectangle(
                [text_bbox[0], text_bbox[1], text_bbox[2], text_bbox[3]],
                fill="black"
            )
            draw.text((abs_x1, abs_y1), label, fill="white", font=font)

    def draw_parsed_image(self) -> Image.Image:
        if self._original_image is None or self._parsed_content_list is None:
            raise ValueError("No screen parsed yet. Call parse_screen first.")

        orig_width, orig_height = self._original_image.size
        new_width = orig_width * 4
        new_height = orig_height * 4

        expanded_img = self._original_image.resize(
            (new_width, new_height), Image.Resampling.LANCZOS
        )
        draw = ImageDraw.Draw(expanded_img)

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 16)
            except IOError:
                font = ImageFont.load_default()

        for el in self._parsed_content_list:
            el_type = str(el.get('type', '')).lower()
            content = str(el.get('content', '')).strip()
            label = f"{el_type}: {content}" if content else el_type
            self._draw_single_bbox(draw, el.get('bbox', []), label, font, new_width, new_height)

        self._expanded_image = expanded_img
        return self._expanded_image

    def draw_and_save_parsed_image(self, filename: str):
        img = self.draw_parsed_image()
        img.save(filename)