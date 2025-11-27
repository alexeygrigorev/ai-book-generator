"""
Generate Amazon KDP print cover PDF.

Creates a PDF cover with:
- Back cover (LEFT side) with description text
- Front cover (RIGHT side) with cover image or generated design
- Optional spine in the middle

The script reads book metadata from plan.yaml and creates a KDP-complaint cover.
"""

import yaml
from pathlib import Path
from typing import Optional
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os


class KDPCoverGenerator:
    def __init__(self, book_folder: str, page_count: int = 300):
        """
        Initialize KDP cover generator.

        Args:
            book_folder: Name of the book folder in 'books/'
            page_count: Total page count for spine width calculation
        """
        self.book_folder = book_folder
        self.book_path = Path("books") / book_folder
        self.page_count = page_count

        # Register Unicode fonts for Cyrillic support
        self._register_fonts()

        # Load book metadata
        self.metadata = self._load_metadata()

        # KDP cover dimensions (for 6x9 inch book)
        self.trim_width = 6 * inch
        self.trim_height = 9 * inch
        self.bleed = 0.125 * inch  # Standard bleed

        # Calculate spine width (approximate formula)
        # For cream paper: spine = (page_count * 0.002252) inches
        # For white paper: spine = (page_count * 0.0025) inches
        # Defaulting to white paper based on user feedback (0.175" for 70 pages)
        self.spine_width = page_count * 0.0025 * inch

        # Total cover width = front + back + spine + 2*bleed
        # KDP requires the spine width to be included in the total width regardless of thickness
        self.total_width = 2 * self.trim_width + self.spine_width + 2 * self.bleed
        self.total_height = self.trim_height + 2 * self.bleed

    def _register_fonts(self):
        """Register Unicode-compatible fonts for Cyrillic support."""
        try:
            # Try to find DejaVu fonts in common Windows locations
            windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"

            # Register DejaVuSans (supports Cyrillic)
            dejavu_path = windows_fonts / "DejaVuSans.ttf"
            dejavu_bold_path = windows_fonts / "DejaVuSans-Bold.ttf"

            if dejavu_path.exists():
                pdfmetrics.registerFont(TTFont("DejaVu", str(dejavu_path)))
                self.font_regular = "DejaVu"
            else:
                # Fallback to Arial which has some Cyrillic support
                arial_path = windows_fonts / "arial.ttf"
                if arial_path.exists():
                    pdfmetrics.registerFont(TTFont("Arial-Unicode", str(arial_path)))
                    self.font_regular = "Arial-Unicode"
                else:
                    # Last fallback to Helvetica (won't show Cyrillic properly)
                    self.font_regular = "Helvetica"
                    print(
                        "Warning: Unicode font not found. Cyrillic text may not display correctly."
                    )

            if dejavu_bold_path.exists():
                pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(dejavu_bold_path)))
                self.font_bold = "DejaVu-Bold"
            else:
                # Fallback to Arial Bold
                arial_bold_path = windows_fonts / "arialbd.ttf"
                if arial_bold_path.exists():
                    pdfmetrics.registerFont(
                        TTFont("Arial-Bold-Unicode", str(arial_bold_path))
                    )
                    self.font_bold = "Arial-Bold-Unicode"
                else:
                    self.font_bold = "Helvetica-Bold"

        except Exception as e:
            print(f"Warning: Could not register Unicode fonts: {e}")
            self.font_regular = "Helvetica"
            self.font_bold = "Helvetica-Bold"

    def _load_metadata(self) -> dict:
        """Load book metadata from plan.yaml."""
        plan_path = self.book_path / "plan.yaml"
        if not plan_path.exists():
            raise FileNotFoundError(f"plan.yaml not found in {self.book_path}")

        with open(plan_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _find_cover_image(self) -> Optional[Path]:
        """Find cover image in book folder."""
        for ext in [".png", ".jpg", ".jpeg"]:
            cover_path = self.book_path / f"cover{ext}"
            if cover_path.exists():
                return cover_path
        return None

    def _get_back_cover_text(self) -> str:
        """Get back cover text from metadata or file."""
        # Try plan.yaml first
        if "back_cover_description" in self.metadata:
            return self.metadata["back_cover_description"]

        # Try back_cover.md file
        back_cover_path = self.book_path / "back_cover.md"
        if back_cover_path.exists():
            return back_cover_path.read_text(encoding="utf-8").strip()

        return "Book description not available."

    def _draw_back_cover(self, c: canvas.Canvas, x: float, y: float):
        """
        Draw back cover on the left side.

        Args:
            c: ReportLab canvas
            x: X position of back cover area
            y: Y position of back cover area
        """
        # Background color
        c.setFillColor(HexColor("#1a1a2e"))
        c.rect(x, y, self.trim_width, self.trim_height, fill=1, stroke=0)

        # Get back cover text
        back_text = self._get_back_cover_text()
        book_title = self.metadata.get("name", "Book Title")

        # Create text area with margins
        margin = 0.5 * inch
        text_width = self.trim_width - 2 * margin
        text_x = x + margin
        text_y_top = y + self.trim_height - margin

        # Title at top
        c.setFillColor(white)
        c.setFont(self.font_bold, 18)

        # Wrap title if needed
        title_lines = self._wrap_text(c, book_title, text_width, self.font_bold, 18)
        title_y = text_y_top
        for line in title_lines:
            c.drawString(text_x, title_y, line)
            title_y -= 22

        # Separator line
        c.setStrokeColor(HexColor("#e94560"))
        c.setLineWidth(2)
        c.line(text_x, title_y - 10, text_x + text_width, title_y - 10)

        # Description text
        desc_y = title_y - 30
        c.setFont(self.font_regular, 11)
        c.setFillColor(HexColor("#e8e8e8"))

        # Wrap description text
        desc_lines = self._wrap_text(c, back_text, text_width, self.font_regular, 11)
        for line in desc_lines:
            if desc_y < y + margin:
                break
            c.drawString(text_x, desc_y, line)
            desc_y -= 14

    def _wrap_text(
        self, c: canvas.Canvas, text: str, max_width: float, font: str, font_size: int
    ) -> list:
        """Wrap text to fit within max_width."""
        c.setFont(font, font_size)
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            if c.stringWidth(test_line, font, font_size) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def _draw_front_cover(self, c: canvas.Canvas, x: float, y: float):
        """
        Draw front cover on the right side.

        Args:
            c: ReportLab canvas
            x: X position of front cover area
            y: Y position of front cover area
        """
        cover_image = self._find_cover_image()

        if cover_image:
            # Use existing cover image
            try:
                img = ImageReader(str(cover_image))
                c.drawImage(
                    img,
                    x,
                    y,
                    width=self.trim_width,
                    height=self.trim_height,
                    preserveAspectRatio=False,
                )
            except Exception as e:
                print(f"Warning: Could not load cover image: {e}")
                self._draw_generated_front_cover(c, x, y)
        else:
            # Generate a simple front cover
            self._draw_generated_front_cover(c, x, y)

    def _draw_generated_front_cover(self, c: canvas.Canvas, x: float, y: float):
        """Generate a simple front cover design."""
        # Background gradient (simulated with rectangles)
        c.setFillColor(HexColor("#0f3460"))
        c.rect(x, y, self.trim_width, self.trim_height, fill=1, stroke=0)

        # Accent color overlay
        c.setFillColorRGB(0.91, 0.27, 0.38, alpha=0.3)
        c.rect(x, y, self.trim_width, self.trim_height / 2, fill=1, stroke=0)

        # Book title
        book_title = self.metadata.get("name", "Book Title")
        margin = 0.75 * inch

        # Title positioning (center)
        title_y = y + self.trim_height - 2 * inch

        c.setFillColor(white)
        c.setFont(self.font_bold, 24)

        # Wrap and center title
        title_lines = self._wrap_text(
            c, book_title, self.trim_width - 2 * margin, self.font_bold, 24
        )

        for line in title_lines:
            line_width = c.stringWidth(line, self.font_bold, 24)
            line_x = x + (self.trim_width - line_width) / 2
            c.drawString(line_x, title_y, line)
            title_y -= 30

    def _draw_spine(self, c: canvas.Canvas, x: float, y: float):
        """
        Draw spine in the middle.

        Args:
            c: ReportLab canvas
            x: X position of spine area
            y: Y position of spine area
        """
        # Background
        c.setFillColor(HexColor("#16213e"))
        c.rect(x, y, self.spine_width, self.trim_height, fill=1, stroke=0)

        # Title on spine (rotated)
        book_title = self.metadata.get("name", "Book Title")

        c.saveState()
        c.translate(x + self.spine_width / 2, y + self.trim_height / 2)
        c.rotate(270)  # Rotate for spine text

        c.setFillColor(white)
        c.setFont(self.font_bold, 14)

        # Truncate title if too long for spine
        max_spine_text_width = self.trim_height - inch
        while (
            c.stringWidth(book_title, self.font_bold, 14) > max_spine_text_width
            and len(book_title) > 10
        ):
            book_title = book_title[: len(book_title) - 4] + "..."

        title_width = c.stringWidth(book_title, self.font_bold, 14)
        c.drawString(-title_width / 2, 0, book_title)

        c.restoreState()

    def generate_cover(self, output_path: Optional[Path] = None) -> Path:
        """
        Generate the KDP cover PDF.

        Args:
            output_path: Optional output path. Defaults to books/[book_folder]/kdp_cover.pdf

        Returns:
            Path to generated PDF
        """
        if output_path is None:
            output_path = self.book_path / "kdp_cover.pdf"

        # Determine if spine is too small for text (< 0.5 inches)
        # But we MUST include the spine space in the PDF regardless
        min_spine_text_width = 0.5 * inch
        draw_spine_text = self.spine_width >= min_spine_text_width

        # Create PDF canvas with full width (including spine)
        c = canvas.Canvas(
            str(output_path), pagesize=(self.total_width, self.total_height)
        )

        # Starting positions (accounting for bleed)
        start_x = self.bleed
        start_y = self.bleed

        # Draw back cover (LEFT)
        self._draw_back_cover(c, start_x, start_y)

        # Draw spine (MIDDLE) - always draw background, conditionally draw text
        spine_x = start_x + self.trim_width

        # Draw spine background
        c.setFillColor(HexColor("#16213e"))
        c.rect(spine_x, start_y, self.spine_width, self.trim_height, fill=1, stroke=0)

        if draw_spine_text:
            self._draw_spine(c, spine_x, start_y)

        # Draw front cover (RIGHT)
        front_x = spine_x + self.spine_width
        self._draw_front_cover(c, front_x, start_y)

        # Add crop marks (optional)
        self._draw_crop_marks(c)

        # Save PDF
        c.save()

        print(f"[OK] KDP cover generated: {output_path}")
        print(
            f'  Total dimensions: {self.total_width / inch:.2f}" x {self.total_height / inch:.2f}"'
        )
        print(f'  Trim size: {self.trim_width / inch}" x {self.trim_height / inch}"')
        print(
            f'  Spine width: {self.spine_width / inch:.4f}" ({self.page_count} pages)'
        )
        if not draw_spine_text:
            print(f'  (Spine text skipped as width < 0.5")')

        return output_path

    def _draw_crop_marks(self, c: canvas.Canvas):
        """Draw crop marks at corners of trim area."""
        # Note: Crop marks are optional - KDP usually doesn't require them
        pass


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate Amazon KDP print cover PDF")
    parser.add_argument(
        "book",
        type=str,
        help="Book folder name (e.g., 'sirens')",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=300,
        help="Total page count for spine width calculation (default: 300)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output PDF path (default: books/[book]/kdp_cover.pdf)",
    )

    args = parser.parse_args()

    generator = KDPCoverGenerator(book_folder=args.book, page_count=args.pages)

    output_path = Path(args.output) if args.output else None
    generator.generate_cover(output_path)


if __name__ == "__main__":
    main()
