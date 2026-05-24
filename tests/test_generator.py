"""
Unit and integration tests for strokemap.generator.

The Lenna (Lena) standard test image (512×512) is used as the canonical sample input.
Source: USC SIPI Image Database – http://sipi.usc.edu/database/
Image:  assets/lenna.png
"""

from pathlib import Path

import numpy as np
import pytest

from strokemap.generator import PaintByNumbersGenerator

# Path to the canonical test asset – lives in tests/assets/
ASSETS_DIR = Path(__file__).parent / "assets"
LENNA_PATH = ASSETS_DIR / "lenna.png"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lenna_rgb():
    """Load Lenna once per test module."""
    gen = PaintByNumbersGenerator()
    return gen.load_image(str(LENNA_PATH))


@pytest.fixture(scope="module")
def generator_medium():
    return PaintByNumbersGenerator(difficulty="medium")


# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------


class TestPaintByNumbersGeneratorInit:
    """Tests for correct initialization of PaintByNumbersGenerator."""

    def test_default_difficulty_is_medium(self):
        gen = PaintByNumbersGenerator()
        assert gen.difficulty == "medium"

    @pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
    def test_valid_difficulties_accepted(self, difficulty):
        gen = PaintByNumbersGenerator(difficulty=difficulty)
        assert gen.difficulty == difficulty

    def test_slic_params_set_for_medium(self):
        gen = PaintByNumbersGenerator(difficulty="medium")
        assert gen.n_segments_base > 0
        assert gen.slic_compactness > 0
        assert gen.slic_sigma > 0

    def test_slic_params_set_for_easy(self):
        gen = PaintByNumbersGenerator(difficulty="easy")
        gen_medium = PaintByNumbersGenerator(difficulty="medium")
        # Easy should produce fewer superpixels (simpler output)
        assert gen.n_segments_base < gen_medium.n_segments_base

    def test_slic_params_set_for_hard(self):
        gen = PaintByNumbersGenerator(difficulty="hard")
        gen_medium = PaintByNumbersGenerator(difficulty="medium")
        # Hard should produce more superpixels (more detailed output)
        assert gen.n_segments_base > gen_medium.n_segments_base


# ---------------------------------------------------------------------------
# load_image tests
# ---------------------------------------------------------------------------


class TestLoadImage:
    def test_lenna_loads_correctly(self, lenna_rgb):
        assert lenna_rgb.shape == (512, 512, 3)
        assert lenna_rgb.dtype == np.uint8

    def test_raises_on_missing_file(self):
        gen = PaintByNumbersGenerator()
        with pytest.raises(FileNotFoundError):
            gen.load_image("does_not_exist.jpg")


# ---------------------------------------------------------------------------
# preprocess_image tests
# ---------------------------------------------------------------------------


class TestPreprocessImage:
    def test_returns_same_shape(self, lenna_rgb, generator_medium):
        result = generator_medium.preprocess_image(lenna_rgb)
        assert result.shape == lenna_rgb.shape

    def test_returns_uint8(self, lenna_rgb, generator_medium):
        result = generator_medium.preprocess_image(lenna_rgb)
        assert result.dtype == np.uint8

    def test_output_differs_from_input(self, lenna_rgb, generator_medium):
        """Median blur should change at least some pixel values."""
        result = generator_medium.preprocess_image(lenna_rgb)
        assert not np.array_equal(result, lenna_rgb)
