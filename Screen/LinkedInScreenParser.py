import os
from PIL import Image, ImageDraw, ImageFont
from Screen.ScreenParser import ScreenParser


class LinkedInScreenParser(ScreenParser):
    def __init__(self, omniparser_repo_path: str):
        super().__init__(omniparser_repo_path)
        self._close_pairs = []

    def parse_screen(self, image: Image.Image):
        parsed_content_list = super().parse_screen(image)

        self._close_pairs = []
        for el in parsed_content_list:
            content = str(el.get('content', '')).strip().lower()
            if 'close' in content:
                close_bbox = el.get('bbox', [])
                if len(close_bbox) == 4:
                    close_x1, close_y1, close_x2, close_y2 = close_bbox

                    best_match = None
                    min_distance = float('inf')

                    for other_el in parsed_content_list:
                        if other_el is el:
                            continue
                        other_bbox = other_el.get('bbox', [])
                        if len(other_bbox) == 4:
                            other_x1, other_y1, other_x2, other_y2 = other_bbox

                            # Check if it's to the left and within 20% width (0.2 in ratio)
                            if other_x2 <= close_x1 and (close_x1 - other_x2) <= 0.2:
                                # Check vertical overlap to ensure it's the corresponding button
                                if not (other_y2 <= close_y1 or other_y1 >= close_y2):
                                    distance = close_x1 - other_x2
                                    if distance < min_distance:
                                        min_distance = distance
                                        best_match = other_el

                    if best_match:
                        self._close_pairs.append({
                            'close_button': el,
                            'left_button': best_match
                        })
                        print(f"Found pair: Close='{el.get('content')}', Left='{best_match.get('content')}'")

        self._original_image = image
        return parsed_content_list

    def draw_parsed_image(self) -> Image.Image:
        if self._original_image is None or not self._close_pairs:
            raise ValueError("No screen parsed yet or no close pairs found.")

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

        for pair in self._close_pairs:
            close_el = pair['close_button']
            left_el = pair['left_button']

            self._draw_single_bbox(
                draw,
                close_el.get('bbox', []),
                f"Close: {close_el.get('content')}",
                font,
                new_width,
                new_height
            )
            self._draw_single_bbox(
                draw,
                left_el.get('bbox', []),
                f"Left: {left_el.get('content')}",
                font,
                new_width,
                new_height
            )

        self._expanded_image = expanded_img
        return self._expanded_image

    def draw_and_save_parsed_image(self, filename: str):
        img = self.draw_parsed_image()
        img.save(filename)