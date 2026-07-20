import os
from PIL import Image, ImageDraw, ImageFont
from Screen.ScreenParser import ScreenParser


class HirifyScreenParser(ScreenParser):
    def __init__(self, omniparser_repo_path: str):
        super().__init__(omniparser_repo_path)
        # Initialize attributes for BOTH screens
        self._more_options_buttons = []
        self._triangle_down_candidates = []
        self._next_buttons = []
        self._back_button = None

    def transform_screen(self, image: Image.Image) -> Image.Image:
        """Apply transformations optimized for Hirify screens."""
        return super().transform_screen(image, method='otsu')

    def parse_screen(self, image: Image.Image):
        """Parse screen and detect elements for BOTH List and Vacancy screens."""
        parsed_content_list = super().parse_screen(image)

        # Reset attributes for each parse
        self._more_options_buttons = []
        self._triangle_down_candidates = []
        self._next_buttons = []
        self._back_button = None

        for el in parsed_content_list:
            content = str(el.get('content', '')).strip()
            content_lower = content.lower()
            bbox = el.get('bbox', [])

            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                w = x2 - x1
                h = y2 - y1

                # 1. Detect "more options" or "more" buttons (List screen)
                if 'more options' in content_lower or content_lower == 'more':
                    if w <= 0.15 and h <= 0.15 and 0.1 <= cx <= 0.9 and 0.1 <= cy <= 0.9:
                        self._more_options_buttons.append(el)
                        print(f"📋 Found More Options button: '{content}' | BBox: {bbox}")

                # 2. Detect triangle_down buttons (List screen - for scrolling)
                if 'triangle_down' in content_lower:
                   if 0.8 <= cx <= 1.0 and 0.8 <= cy <= 1.0:
                        if w <= 0.1 and h <= 0.1:
                            self._triangle_down_candidates.append(el)
                            print(f"🔻 Found triangle_down button: '{content}' | BBox: {bbox}")

                # 3. Detect next button (List screen - for pagination)
                if 'next' in content_lower:
                    if 0.5 <= cx <= 0.97 and 0.1 <= cy <= 0.97:
                        self._next_buttons.append(el)
                        print(f"➡️ Found Next button: '{content}' | BBox: {bbox}")

                # 4. Detect back button (Vacancy screen)
                if 'back' in content_lower:
                    if cx <= 0.2 and cy <= 0.2:
                        self._back_button = el
                        print(f"🔙 Found back button: '{content}' | BBox: {bbox}")

        # Sort more_options_buttons by Y coordinate (top to bottom)
        self._more_options_buttons.sort(key=lambda btn: (btn['bbox'][1] + btn['bbox'][3]) / 2.0)

        return parsed_content_list

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

        def draw_colored_element(el, label_prefix, color):
            content = str(el.get('content', '')).strip()
            label = f"{label_prefix}: {content}" if content else label_prefix
            self._draw_single_bbox(draw, el.get('bbox', []), label, font, new_width, new_height, outline_color=color)

        # Draw all parsed elements in red
        for el in self._parsed_content_list:
            el_type = str(el.get('type', '')).lower()
            content = str(el.get('content', '')).strip()
            label = f"{el_type}: {content}" if content else el_type
            self._draw_single_bbox(draw, el.get('bbox', []), label, font, new_width, new_height, outline_color="red")

        # Draw specific elements in distinct colors
        for more_btn in self._more_options_buttons:
            draw_colored_element(more_btn, "More Options", "blue")
        for triangle_btn in self._triangle_down_candidates:
            draw_colored_element(triangle_btn, "Triangle Down", "green")
        for next_btn in self._next_buttons:
            draw_colored_element(next_btn, "Next", "orange")
        if self._back_button:
            draw_colored_element(self._back_button, "Back", "purple")

        self._expanded_image = expanded_img
        return self._expanded_image

    def draw_and_save_parsed_image(self, filename: str):
        img = self.draw_parsed_image()
        img.save(filename)