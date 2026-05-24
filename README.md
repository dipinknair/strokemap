# Paint by Numbers Generator

A Python package and CLI tool to convert any image into a high-quality, print-ready "Paint by Numbers" PDF template.

The generated PDF matches premium standards, split into three cleanly laid-out pages:
1. **Page 1 - Numbered Template**: Light gray outlines with a small, centered index number in each region.
2. **Page 2 - Clean Borders**: Thick black outlines without any numbers, perfect for clean canvas painting.
3. **Page 3 - Color Palette Sheet**: A beautifully aligned grid of color swatches showing index numbers, hex codes, paint color blocks, and step-by-step instructions.

---

## Installation

Create a virtual environment and install the package locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Dependencies
The package relies on the following standard python packages:
- `numpy`
- `pillow`
- `opencv-python`
- `scikit-learn`
- `reportlab`

---

## Usage

### Command Line Interface

You can convert any image directly from your terminal:

```bash
strokemap input.jpg output.pdf --colors 20 --difficulty medium
```

#### CLI Options:
* `image_path` (required): Path to the input image file.
* `output_pdf` (required): Path where the final PDF should be saved.
* `-c`, `--colors` (optional): Target number of colors (default: 20).
* `-d`, `--difficulty` (optional): Level of region detail (`easy`, `medium`, `hard`) (default: `medium`).

### Python API

You can also use the package programmatically:

```python
from strokemap import PaintByNumbersGenerator, generate_pdf

# 1. Initialize generator with difficulty settings
generator = PaintByNumbersGenerator(difficulty="medium")

# 2. Process image to get templates and palette
numbered_img, clean_img, colorized_img, palette = generator.process("input.jpg", n_colors=20)

# 3. Compile everything into a 4-page A4 PDF
generate_pdf(
    output_pdf_path="output.pdf",
    numbered_img=numbered_img,
    clean_img=clean_img,
    colorized_img=colorized_img,
    palette=palette,
)
```

---

## Algorithms Used

1. **Color Quantization**: Performs K-Means clustering in the CIELAB color space. CIELAB Euclidean distance matches human color perception, resulting in a highly accurate color representation.
2. **Detail Reduction & Region Merging**: To avoid micro-regions that are impossible to paint, the package runs connected components analysis and merges small regions into their dominant neighbor. The threshold is controlled by the chosen difficulty level.
3. **Outline Extraction**: Computes a pixel-wise transition grid to produce clean, single-pixel borders.
4. **Optimal Label Placement**: Uses a distance transform (`cv2.distanceTransform`) to find the center of the largest inscribed circle inside each region, placing the text at the most readable point.
