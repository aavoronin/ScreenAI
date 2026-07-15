import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch

# ==========================================
# PATH CONFIGURATION
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

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

        # Template matching for custom symbols
        self.custom_templates = {}  # symbol_name -> list of template images
        self._load_custom_templates()

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

    def _load_custom_templates(self):
        """Load custom symbol templates from custom_images folder."""
        custom_images_path = os.path.join(project_root, "custom_images")

        if not os.path.exists(custom_images_path):
            print(f"⚠️ custom_images folder not found at: {custom_images_path}")
            print(
                "   Please create this folder and add subfolders (named after the symbol) containing .png/.jpg images.")
            return

        print("🔄 Loading custom symbol templates...")
        symbol_count = 0

        for item in os.listdir(custom_images_path):
            symbol_path = os.path.join(custom_images_path, item)
            if os.path.isdir(symbol_path):
                templates = []
                for img_file in os.listdir(symbol_path):
                    # Added .webp to the supported extensions
                    if img_file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        img_path = os.path.join(symbol_path, img_file)
                        # Load and convert to grayscale
                        template = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if template is not None:
                            # Resize to 32x32 for consistency
                            template = cv2.resize(template, (32, 32))
                            templates.append(template)

                if templates:
                    self.custom_templates[item] = templates
                    symbol_count += 1
                    print(f"  ✓ Loaded {len(templates)} template(s) for '{item}'")
                else:
                    print(f"  ⚠️ No valid images (.png, .jpg, .jpeg) found in subfolder '{item}'")

        if symbol_count == 0:
            print(
                "⚠️ Loaded 0 symbol types. Please ensure 'custom_images' contains subfolders with actual image files.")
        else:
            print(f"✅ Loaded {symbol_count} symbol type(s) in total.")

    def _detect_custom_symbols(self, screenshot_np):
        """Detect custom symbols in the screenshot using template matching."""
        if not self.custom_templates:
            return []

        detected_symbols = []
        # Convert screenshot to grayscale
        if len(screenshot_np.shape) == 3:
            screenshot_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
        else:
            screenshot_gray = screenshot_np

        screenshot_h, screenshot_w = screenshot_gray.shape

        # Search for each custom symbol
        for symbol_name, templates in self.custom_templates.items():
            for template in templates:
                template_h, template_w = template.shape
                # Perform template matching
                result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
                threshold = 0.80  # 80% confidence
                locations = np.where(result >= threshold)

                # Group nearby detections to avoid duplicates
                points = list(zip(*locations[::-1]))
                used_points = set()

                for pt in points:
                    # Check if this point is too close to an already used point
                    is_duplicate = False
                    for used_pt in used_points:
                        distance = np.sqrt((pt[0] - used_pt[0]) ** 2 + (pt[1] - used_pt[1]) ** 2)
                        if distance < 10:  # Within 10 pixels
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        used_points.add(pt)
                        # Calculate normalized bounding box
                        x1 = pt[0] / screenshot_w
                        y1 = pt[1] / screenshot_h
                        x2 = (pt[0] + template_w) / screenshot_w
                        y2 = (pt[1] + template_h) / screenshot_h

                        detected_symbols.append({
                            'type': 'icon',
                            'bbox': [x1, y1, x2, y2],
                            'interactivity': True,
                            'content': symbol_name,
                            'source': 'template_match'
                        })
        return detected_symbols

    def cleanup(self):
        self._parsed_content_list = None
        self._label_coordinates = None
        self._original_image = None
        self._expanded_image = None

    def parse_screen(self, image: Image.Image):
        self.cleanup()
        self._original_image = image.convert("RGB")
        # Convert PIL Image to numpy array for template matching
        screenshot_np = np.array(self._original_image)

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

        # Detect custom symbols using template matching
        custom_symbols = self._detect_custom_symbols(screenshot_np)
        if custom_symbols:
            print(f" 🔍 Detected {len(custom_symbols)} custom symbol(s) via template matching")
            # Add custom symbols to parsed content list
            self._parsed_content_list.extend(custom_symbols)

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