import argparse
import os
import sys
import traceback

from .generator import PaintByNumbersGenerator
from .pdf_generator import generate_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Convert any image to a print-ready Paint by Numbers PDF."
    )
    parser.add_argument("image_path", help="Path to the input image file (JPEG, PNG, etc.)")
    parser.add_argument("output_pdf", help="Path where the output PDF should be saved")
    parser.add_argument(
        "-c",
        "--colors",
        type=int,
        default=20,
        help="Number of colors to use for the painting (default: 20)",
    )
    parser.add_argument(
        "-d",
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="Difficulty level which controls region sizes and details (default: medium)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.image_path):
        print(f"Error: Input image file '{args.image_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing image: {args.image_path}")
    print(f"Difficulty level: {args.difficulty}")
    print(f"Target colors: {args.colors}")

    # Run the generator pipeline
    generator = PaintByNumbersGenerator(difficulty=args.difficulty)
    try:
        numbered_img, clean_img, colorized_img, palette = generator.process(
            args.image_path, args.colors
        )

        print(f"Generated outlines with {len(palette)} final colors.")
        print(f"Compiling PDF to: {args.output_pdf}")

        generate_pdf(
            output_pdf_path=args.output_pdf,
            numbered_img=numbered_img,
            clean_img=clean_img,
            colorized_img=colorized_img,
            palette=palette,
        )
        print("Success! Paint by Numbers PDF generated successfully.")

    except Exception as e:
        print(f"Error generating Paint by Numbers: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
