import os
from PIL import Image, ImageDraw, ImageFont
from Screen.ScreenParser import ScreenParser


class HirifyMeScreenParser(ScreenParser):
    def __init__(self, omniparser_repo_path: str):
        super().__init__(omniparser_repo_path)
        self._more_options_buttons = []
        self._next_buttons = []
        self._triangle_down_candidates = []

    def transform_screen(self, image: Image.Image) -> Image.Image:
        """
        Override to apply specific transformations for Hirify screens.
        Using Otsu's method for binarization.
        """
        return super().transform_screen(image, method='otsu')

    def parse_screen(self, image: Image.Image):
        """
        Parse the screen and identify:
        - More options buttons (three dots menu for vacancies)
        - Triangle down buttons (for scrolling/expanding)
        - Next buttons (for pagination)
        """
        parsed_content_list = super().parse_screen(image)

        self._more_options_buttons = []
        self._next_buttons = []
        self._triangle_down_candidates = []

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

                # Detect "more options" or "more" buttons
                # These are typically three dots icons or text saying "more"
                if ('more' in content_lower or
                        'options' in content_lower or
                        '⋮' in content or
                        '...' in content):
                    # Adjust detection area - typically in job cards
                    # Look for buttons that are relatively small and positioned appropriately
                    if w <= 0.1 and h <= 0.1:  # Small icon/button
                        self._more_options_buttons.append(el)
                        print(f"Found 'more options' button: '{content}' | BBox: {bbox}")

                # Detect triangle_down buttons (for scrolling/expanding filters)
                if 'triangle_down' in content_lower or '▼' in content or 'down' in content_lower:
                    # Adjust detection area - typically in filter sections or pagination
                    if 0.0 <= cx <= 1.0 and 0.1 <= cy <= 0.95:  # Wider vertical range
                        if w <= 0.08 and h <= 0.08:  # Small icon
                            self._triangle_down_candidates.append(el)
                            print(f"Found triangle_down button: '{content}' | BBox: {bbox}")

                # Detect next button (for pagination)
                if 'next' in content_lower or '›' in content or '>' in content:
                    # Next button is typically at the bottom of the page
                    if 0.3 <= cy <= 0.95:  # Bottom half of screen
                        self._next_buttons.append(el)
                        print(f"Found Next button: '{content}' | BBox: {bbox}")

        # Sort more_options_buttons by Y coordinate (top to bottom)
        self._more_options_buttons.sort(key=lambda btn: (btn['bbox'][1] + btn['bbox'][3]) / 2.0)

        return parsed_content_list

    def draw_parsed_image(self) -> Image.Image:
        """
        Draw bounding boxes on the parsed image with different colors:
        - Red: All parsed elements (from base class)
        - Blue: More options buttons
        - Green: Triangle down buttons
        - Orange: Next buttons
        """
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

        # Draw all parsed elements in red (from base class)
        for el in self._parsed_content_list:
            el_type = str(el.get('type', '')).lower()
            content = str(el.get('content', '')).strip()
            label = f"{el_type}: {content}" if content else el_type
            self._draw_single_bbox(draw, el.get('bbox', []), label, font, new_width, new_height, outline_color="red")

        # Draw more options buttons in blue
        for more_btn in self._more_options_buttons:
            draw_colored_element(more_btn, "More Options", "blue")

        # Draw triangle down buttons in green
        for triangle_btn in self._triangle_down_candidates:
            draw_colored_element(triangle_btn, "Triangle Down", "green")

        # Draw next buttons in orange
        for next_btn in self._next_buttons:
            draw_colored_element(next_btn, "Next", "orange")

        self._expanded_image = expanded_img
        return self._expanded_image

    def draw_and_save_parsed_image(self, filename: str):
        img = self.draw_parsed_image()
        img.save(filename)