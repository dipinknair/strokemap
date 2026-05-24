import io

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable


class ColorSwatch(Flowable):
    def __init__(self, index, rgb, hex_code, width=80, height=70):
        super().__init__()
        self.index = index
        self.rgb = rgb  # tuple (r, g, b)
        self.hex_code = hex_code
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        # Draw color box
        # Normalize color to 0.0 - 1.0 for reportlab
        r, g, b = (val / 255.0 for val in self.rgb)
        self.canv.setFillColorRGB(r, g, b)
        self.canv.setStrokeColorRGB(0.1, 0.1, 0.1)
        self.canv.setLineWidth(1)

        # Center square horizontally
        square_size = 36
        sq_x = (self.width - square_size) / 2
        sq_y = self.height - square_size - 2

        self.canv.rect(sq_x, sq_y, square_size, square_size, fill=1, stroke=1)

        # Draw color index number
        self.canv.setFont("Helvetica-Bold", 10)
        self.canv.setFillColorRGB(0.1, 0.1, 0.1)
        self.canv.drawCentredString(self.width / 2, sq_y - 12, str(self.index))

        # Draw Hex Code
        self.canv.setFont("Helvetica", 8)
        self.canv.setFillColorRGB(0.4, 0.4, 0.4)
        self.canv.drawCentredString(self.width / 2, sq_y - 24, self.hex_code)


def generate_pdf(
    output_pdf_path,
    numbered_img,
    clean_img,
    colorized_img,
    palette,
):
    # Margins and page size
    margin = 36  # 0.5 inch
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    page_w, page_h = A4
    max_w = page_w - 2 * margin
    max_h = page_h - 2 * margin

    story = []

    # ----------------------------------------------------
    # Page 1: Numbered Template Image
    # ----------------------------------------------------
    num_buf = io.BytesIO()
    numbered_img.save(num_buf, format="PNG")
    num_buf.seek(0)

    # Calculate dimensions to maintain aspect ratio
    img_w, img_h = numbered_img.size
    aspect_ratio = img_w / img_h

    if max_w / aspect_ratio <= max_h:
        draw_w = max_w
        draw_h = max_w / aspect_ratio
    else:
        draw_h = max_h
        draw_w = max_h * aspect_ratio

    # Spacer to vertically center the image on the page
    v_spacer_1 = (max_h - draw_h) / 2
    if v_spacer_1 > 0:
        story.append(Spacer(1, v_spacer_1))

    story.append(RLImage(num_buf, width=draw_w, height=draw_h))
    story.append(PageBreak())

    # ----------------------------------------------------
    # Page 2: Clean Outline Image
    # ----------------------------------------------------
    clean_buf = io.BytesIO()
    clean_img.save(clean_buf, format="PNG")
    clean_buf.seek(0)

    v_spacer_2 = (max_h - draw_h) / 2
    if v_spacer_2 > 0:
        story.append(Spacer(1, v_spacer_2))

    story.append(RLImage(clean_buf, width=draw_w, height=draw_h))
    story.append(PageBreak())

    # ----------------------------------------------------
    # Page 3: Color Preview Image (How it should look)
    # ----------------------------------------------------
    preview_buf = io.BytesIO()
    colorized_img.save(preview_buf, format="PNG")
    preview_buf.seek(0)

    v_spacer_3 = (max_h - draw_h) / 2
    if v_spacer_3 > 0:
        story.append(Spacer(1, v_spacer_3))

    story.append(RLImage(preview_buf, width=draw_w, height=draw_h))
    story.append(PageBreak())

    # ----------------------------------------------------
    # Page 4: Palette Sheet
    # ----------------------------------------------------
    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "PaletteTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        alignment=TA_CENTER,
        spaceAfter=6,
    )

    instruction_title_style = ParagraphStyle(
        "InstructionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        spaceAfter=6,
    )

    instruction_body_style = ParagraphStyle(
        "InstructionBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=HexColor("#333333"),
        spaceAfter=4,
    )

    # Title
    story.append(Paragraph("Strokemap", title_style))

    # Color palette grid
    num_cols = 6
    col_w = max_w / num_cols

    swatches = []
    for color in palette:
        swatches.append(
            ColorSwatch(
                index=color["index"],
                rgb=color["rgb"],
                hex_code=color["hex"],
                width=col_w,
                height=70,
            )
        )

    # Arrange into grid matrix
    table_data = []
    current_row = []
    for _, swatch in enumerate(swatches):
        current_row.append(swatch)
        if len(current_row) == num_cols:
            table_data.append(current_row)
            current_row = []
    if current_row:
        # Pad last row with empty flowables
        while len(current_row) < num_cols:
            current_row.append("")
        table_data.append(current_row)

    palette_table = Table(table_data, colWidths=[col_w] * num_cols)
    palette_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    story.append(palette_table)
    story.append(Spacer(1, 24))

    # Instructions at the bottom
    story.append(Paragraph("Instructions:", instruction_title_style))

    bullets = [
        "<b>Page 1 - Numbered template:</b> Find numbered areas and match to colors on page 4.",
        "<b>Page 2 - Clean borders:</b> For those who want a clean painting experience.",
        "<b>Page 3 - Colored preview:</b> A reference picture showing how the final painting looks.",
        "1. Choose your preferred template (numbered or clean borders).",
        "2. Match the numbers to the colors on the palette sheet (page 4).",
        "3. Paint each area with the corresponding color.",
        "4. Use the colored preview page as a reference.",
        "5. Take your time and enjoy the process!",
    ]

    for bullet in bullets:
        story.append(Paragraph(bullet, instruction_body_style))

    # Build Document
    doc.build(story)
