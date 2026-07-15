import os
from PIL import Image, ImageDraw, ImageFont
from Screen.ScreenParser import ScreenParser


class LinkedInScreenParser(ScreenParser):
    def __init__(self, omniparser_repo_path: str):
        super().__init__(omniparser_repo_path)
        self._close_pairs = []
        self._next_buttons = []
        self._linkedin_buttons = []
        self._scroll_down_candidates = []

    def parse_screen(self, image: Image.Image):
        parsed_content_list = super().parse_screen(image)

        self._close_pairs = []
        self._next_buttons = []
        self._linkedin_buttons = []
        self._scroll_down_candidates = []

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

                if 'downward-pointing triangle' in content_lower:
                    if 0.25 <= cx <= 0.5 and 0.8 <= cy <= 0.95 and w <= 0.05 and h <= 0.05:
                        self._scroll_down_candidates.append(el)
                        print(f"Found Scroll Down button: '{el.get('content')}' | BBox: {el.get('bbox')}")

                if 'next' in content_lower:
                    if 0.25 <= cx <= 0.5 and 0.6 <= cy <= 0.95:
                        self._next_buttons.append(el)
                        print(f"Found Next button: '{el.get('content')}' | BBox: {el.get('bbox')}")

                if ('linkedin' in content_lower):
                    if ('jobs' in content_lower and 'com' in content_lower and 'search-results' in content_lower):
                        if 0.1 <= cx <= 0.9 and 0.05 <= cy <= 0.25:
                            self._linkedin_buttons.append(el)
                            print(f"Found LinkedIn Jobs button: '{el.get('content')}' | BBox: {el.get('bbox')}")

        for close_el in parsed_content_list:
            content_lower = str(close_el.get('content', '')).strip().lower()
            bbox = close_el.get('bbox', [])
            if len(bbox) == 4 and 'close' in content_lower:
                x1, y1, x2, y2 = bbox
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                w = x2 - x1
                h = y2 - y1
                if 0.25 <= cx <= 0.5 and 0.3 <= cy <= 0.8 and w <= 0.05 and h <= 0.05:
                    close_x1, close_y1, close_x2, close_y2 = bbox
                    best_match = None
                    min_distance = float('inf')

                    for other_el in parsed_content_list:
                        if other_el is close_el:
                            continue
                        other_content = str(other_el.get('content', '')).strip().lower()
                        if (
                                'horton security' in other_content or 'more options' in other_content or 'shield' in other_content):
                            continue
                        other_bbox = other_el.get('bbox', [])
                        if len(other_bbox) == 4:
                            other_x1, other_y1, other_x2, other_y2 = other_bbox
                            if other_x2 <= close_x1:
                                if not (other_y2 <= close_y1 or other_y1 >= close_y2):
                                    distance = close_x1 - other_x2
                                    if distance < min_distance:
                                        min_distance = distance
                                        best_match = other_el

                    if best_match:
                        self._close_pairs.append({
                            'close_button': close_el,
                            'left_button': best_match
                        })
                        print(
                            f"Found Close pair: Close='{close_el.get('content')}', Left='{best_match.get('content')}'")
                    else:
                        print(f"Found Close button but no valid left partner: '{close_el.get('content')}'")

        self._original_image = image
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

        def draw_blue_element(el, label_prefix):
            content = str(el.get('content', '')).strip()
            label = f"{label_prefix}: {content}" if content else label_prefix
            # Now this will work because outline_color is supported in the base class
            self._draw_single_bbox(draw, el.get('bbox', []), label, font, new_width, new_height, outline_color="blue")

        # Draw all elements with red boxes
        for el in self._parsed_content_list:
            el_type = str(el.get('type', '')).lower()
            content = str(el.get('content', '')).strip()
            label = f"{el_type}: {content}" if content else el_type
            self._draw_single_bbox(draw, el.get('bbox', []), label, font, new_width, new_height, outline_color="red")

        # Draw specific pairs with blue boxes
        for pair in self._close_pairs:
            draw_blue_element(pair['close_button'], "Close")
            draw_blue_element(pair['left_button'], "Left")

        for next_el in self._next_buttons:
            draw_blue_element(next_el, "Next")

        for li_el in self._linkedin_buttons:
            draw_blue_element(li_el, "LinkedIn")

        for scroll_el in self._scroll_down_candidates:
            draw_blue_element(scroll_el, "Scroll Down")

        self._expanded_image = expanded_img
        return self._expanded_image

    def draw_and_save_parsed_image(self, filename: str):
        img = self.draw_parsed_image()
        img.save(filename)