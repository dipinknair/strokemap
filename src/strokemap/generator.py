import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.segmentation import slic
from sklearn.cluster import KMeans


class PaintByNumbersGenerator:
    def __init__(
        self,
        difficulty="medium",
        outline_color=(180, 185, 200),
        number_color=(100, 105, 115),
        clean_outline_color=(0, 0, 0),
    ):
        self.difficulty = difficulty.lower()
        self.outline_color = outline_color
        self.number_color = number_color
        self.clean_outline_color = clean_outline_color

        # Difficulty parameters
        if self.difficulty == "easy":
            self.n_segments_base = 800
            self.slic_compactness = 5.0
            self.slic_sigma = 3.0
            self.min_area_fraction = 0.0005
        elif self.difficulty == "hard":
            self.n_segments_base = 4000
            self.slic_compactness = 10.0
            self.slic_sigma = 1.0
            self.min_area_fraction = 0.00005
        else:  # medium
            self.n_segments_base = 2000
            self.slic_compactness = 8.0
            self.slic_sigma = 2.0
            self.min_area_fraction = 0.0002

    def load_image(self, image_path):
        """Loads image, handles transparency, and returns RGB numpy array."""
        # Read with cv2 (BGR)
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Could not load image from {image_path}")

        # Convert BGR/BGRA to RGB
        if len(img.shape) == 3 and img.shape[2] == 4:
            # BGRA to BGR blending with white background
            alpha = img[:, :, 3:] / 255.0
            img = (img[:, :, :3] * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            # Grayscale to RGB
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        return img

    def preprocess_image(self, img):
        """Applies median filtering to remove noise before segmentation."""
        # Using a small median filter, cv2.medianBlur is very fast
        ksize = 5 if self.difficulty == "easy" else 3
        return cv2.medianBlur(img, ksize)

    def quantize_colors(self, img, n_colors):
        """Segments image using SLIC superpixels and clusters their mean colors."""
        h, w, c = img.shape

        # Calculate number of segments based on image resolution
        scale_factor = (h * w) / 1000000.0
        n_segments = int(self.n_segments_base * max(0.5, scale_factor))

        # 1. SLIC Superpixels
        segments = slic(
            img,
            n_segments=n_segments,
            compactness=self.slic_compactness,
            sigma=self.slic_sigma,
            start_label=0,
        )

        num_segments = np.max(segments) + 1

        # Convert to LAB space for perceptual operations
        lab_img = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)

        # 2. Compute mean color for each segment
        segment_means = np.zeros((num_segments, 3), dtype=np.float32)

        # Fast mean computation using bincount
        for channel in range(3):
            channel_sums = np.bincount(
                segments.ravel(), weights=lab_img[:, :, channel].ravel(), minlength=num_segments
            )
            pixel_counts = np.bincount(segments.ravel(), minlength=num_segments)
            pixel_counts[pixel_counts == 0] = 1  # Avoid division by zero
            segment_means[:, channel] = channel_sums / pixel_counts

        # 3. KMeans clustering on the segment means
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init="auto")
        segment_labels = kmeans.fit_predict(segment_means)
        centers_lab = kmeans.cluster_centers_

        # 4. Map superpixel labels back to image
        labels_2d = segment_labels[segments]

        # Build palette
        palette = []
        for i, center in enumerate(centers_lab):
            center_pixel = center.reshape(1, 1, 3).astype(np.uint8)
            rgb_pixel = cv2.cvtColor(center_pixel, cv2.COLOR_LAB2RGB)[0, 0]
            rgb = (int(rgb_pixel[0]), int(rgb_pixel[1]), int(rgb_pixel[2]))
            hex_code = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
            palette.append({"old_index": i, "rgb": rgb, "hex": hex_code})

        # Sort palette by perceived brightness (luminance)
        palette.sort(key=lambda x: 0.299 * x["rgb"][0] + 0.587 * x["rgb"][1] + 0.114 * x["rgb"][2])

        # Create a remapping array for speed
        remap_arr = np.zeros(n_colors, dtype=np.int32)
        for new_idx, item in enumerate(palette):
            remap_arr[item["old_index"]] = new_idx

        labels_2d_sorted = remap_arr[labels_2d]

        # Clean palette data structure
        sorted_palette = [{"rgb": item["rgb"], "hex": item["hex"]} for item in palette]

        return labels_2d_sorted, sorted_palette

    def merge_small_regions(self, labels_2d, n_colors, min_area):
        """Iteratively merges components smaller than min_area into their largest neighbors."""
        h, w = labels_2d.shape
        result = labels_2d.copy()

        iteration = 0
        max_iterations = 10

        while iteration < max_iterations:
            changed = False
            small_components = []

            # Find connected components for each color index
            unique_colors = np.unique(result)
            for c in unique_colors:
                mask = (result == c).astype(np.uint8)
                num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                    mask, connectivity=4
                )

                for label_idx in range(1, num_labels):
                    area = stats[label_idx, cv2.CC_STAT_AREA]
                    if area < min_area:
                        comp_mask = labels == label_idx
                        small_components.append({"color": c, "area": area, "mask": comp_mask})

            if not small_components:
                break

            # Sort by area ascending to merge smallest first
            small_components.sort(key=lambda x: x["area"])

            for comp in small_components:
                comp_mask = comp["mask"]
                current_vals = result[comp_mask]
                if len(current_vals) == 0:
                    continue

                val = current_vals[0]
                if not np.all(current_vals == val):
                    # Component has already been modified in this iteration, skip
                    continue

                # Dilate mask to find neighbor pixels
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                dilated = cv2.dilate(comp_mask.astype(np.uint8), kernel)
                border = (dilated == 1) & (~comp_mask)

                neighbor_colors = result[border]
                if len(neighbor_colors) == 0:
                    continue

                # Count frequencies of neighboring colors
                counts = np.bincount(neighbor_colors, minlength=val + 1)
                counts[val] = 0  # Ignore current color to force merge with a neighbor

                if np.max(counts) == 0:
                    continue

                best_neighbor = np.argmax(counts)
                result[comp_mask] = best_neighbor
                changed = True

            if not changed:
                break

            iteration += 1

        # Re-index remaining colors to start from 1 to N without gaps
        unique_remaining = sorted(np.unique(result).tolist())
        label_map = {old_lbl: new_lbl + 1 for new_lbl, old_lbl in enumerate(unique_remaining)}

        final_labels = np.vectorize(label_map.get)(result)

        return final_labels, unique_remaining

    def get_outlines(self, final_labels):
        """Generates 1-pixel boundary edge map."""
        h, w = final_labels.shape
        edges = np.zeros((h, w), dtype=bool)

        # Compare each pixel with its right and bottom neighbors
        edges[:-1, :] |= final_labels[:-1, :] != final_labels[1:, :]
        edges[:, :-1] |= final_labels[:, :-1] != final_labels[:, 1:]

        # Add outer canvas border
        edges[0, :] = True
        edges[-1, :] = True
        edges[:, 0] = True
        edges[:, -1] = True

        return edges

    def generate_templates(self, final_labels, edges, num_colors):
        """Creates the numbered template and the clean outlines template images."""
        h, w = final_labels.shape

        # Determine scaling for drawing (lines, fonts)
        max_dim = max(h, w)
        outline_thickness = max(1, int(max_dim / 1500))
        font_size = max(8, int(max_dim * 0.0055))

        # Build dilated edges for template drawing
        if outline_thickness > 1:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (outline_thickness, outline_thickness)
            )
            edges_drawn = cv2.dilate(edges.astype(np.uint8), kernel) > 0
        else:
            edges_drawn = edges

        # 1. Clean outline image (solid black lines on white)
        clean_np = np.ones((h, w, 3), dtype=np.uint8) * 255
        clean_np[edges_drawn] = self.clean_outline_color
        clean_img = Image.fromarray(clean_np)

        # 2. Numbered outline image (gray lines on white)
        numbered_np = np.ones((h, w, 3), dtype=np.uint8) * 255
        numbered_np[edges_drawn] = self.outline_color
        numbered_img = Image.fromarray(numbered_np)

        draw = ImageDraw.Draw(numbered_img)

        # Load clean sans-serif font
        font = None
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNS.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, size=font_size)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()

        min_dist_to_draw = font_size * 0.45

        # Place numbers using distance transform on connected components
        for v in range(1, num_colors + 1):
            mask = (final_labels == v).astype(np.uint8)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                mask, connectivity=8
            )

            for i in range(1, num_labels):
                comp_mask = (labels == i).astype(np.uint8)

                # Compute distance transform of component mask
                dist_transform = cv2.distanceTransform(comp_mask, cv2.DIST_L2, 5)
                _, max_val, _, max_loc = cv2.minMaxLoc(dist_transform)

                # Only write number if it fits nicely inside the region
                if max_val >= min_dist_to_draw:
                    cx, cy = max_loc
                    text_str = str(v)

                    # Center the text
                    bbox = draw.textbbox((0, 0), text_str, font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]

                    text_x = cx - text_w / 2
                    text_y = cy - text_h / 2

                    draw.text((text_x, text_y), text_str, fill=self.number_color, font=font)

        return numbered_img, clean_img

    def process(self, image_path, n_colors):
        """Runs the entire pipeline on the input image and returns output images and palette."""
        # 1. Load & preprocess
        img = self.load_image(image_path)
        smoothed = self.preprocess_image(img)

        # 2. Quantize
        labels_2d, sorted_palette = self.quantize_colors(smoothed, n_colors)

        # Smooth the initial labels to create curvy, organic boundaries
        h, w = labels_2d.shape
        k_size = max(5, int(max(h, w) * 0.005))
        if k_size % 2 == 0:
            k_size += 1
        labels_2d = cv2.medianBlur(labels_2d.astype(np.uint8), k_size).astype(np.int32)

        # 3. Merge small regions
        min_area = int(h * w * self.min_area_fraction)
        final_labels, unique_remaining = self.merge_small_regions(labels_2d, n_colors, min_area)

        # 4. Filter palette to remaining colors
        final_palette = []
        for i, old_idx in enumerate(unique_remaining):
            color_info = sorted_palette[old_idx]
            final_palette.append(
                {"index": i + 1, "rgb": color_info["rgb"], "hex": color_info["hex"]}
            )

        num_final_colors = len(final_palette)

        # 5. Extract outlines and draw templates
        edges = self.get_outlines(final_labels)
        numbered_img, clean_img = self.generate_templates(final_labels, edges, num_final_colors)

        # 6. Build colorized preview image
        colorized_np = np.zeros((h, w, 3), dtype=np.uint8)
        for color_info in final_palette:
            idx = color_info["index"]
            rgb = color_info["rgb"]
            colorized_np[final_labels == idx] = rgb
        colorized_img = Image.fromarray(colorized_np)

        return numbered_img, clean_img, colorized_img, final_palette
