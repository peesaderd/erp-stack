"""
SAM3 Quality Gate — Rule-based Image Quality Checker (No Prodia)

Replaces Prodia SAM3 API calls with fast, free OpenCV+PIL-based image analysis.
Acts as a quality gate: filters out bad images BEFORE they reach Mistral vision analysis.

Checks performed:
  1. Blur detection (Laplacian variance)
  2. Minimum dimensions / resolution
  3. Image too small / too large in file size
  4. Low contrast / washed out
  5. Object occupies too little of frame (via edge+contour analysis)
  6. Mostly text / logo (edge density heuristic)
  7. Corrupted image detection
  8. Aspect ratio validation (extreme ratios are useless)

Cost: $0 (FREE — no API calls)
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

logger = logging.getLogger("sam3.quality_gate")

# ─── Default Thresholds (tunable) ──────────────────────────────────────────

class QualityThresholds:
    """Tunable thresholds for quality checks. Adjust based on product type."""
    
    # Blur: Laplacian variance threshold (lower = blurrier)
    #   < 80  → very blurry
    #   80-150 → somewhat blurry
    #   > 150 → sharp
    MIN_LAPLACIAN_VAR: float = 80.0
    
    # Minimum dimensions (pixels)
    MIN_WIDTH: int = 300
    MIN_HEIGHT: int = 300
    
    # File size range (bytes)
    MIN_FILE_SIZE: int = 5_000       # 5 KB
    MAX_FILE_SIZE: int = 10_000_000  # 10 MB
    
    # Minimum contrast (standard deviation of pixel values)
    #   < 20  → very low contrast (washed out)
    #   20-40 → moderate
    #   > 40  → good
    MIN_CONTRAST: float = 20.0
    
    # Minimum object coverage (% of image area that should be "interesting")
    # Uses edge density + contour area as proxy
    MIN_OBJECT_COVERAGE_PCT: float = 5.0
    
    # Edge density thresholds for "mostly text/logo" detection
    # High horizontal edge density + low vertical = likely text
    MAX_EDGE_DENSITY_FOR_TEXT: float = 0.35  # >35% edge pixels = suspect
    
    # Aspect ratio validation
    MIN_ASPECT_RATIO: float = 0.25  # e.g., 1:4 minimum
    MAX_ASPECT_RATIO: float = 4.0   # e.g., 4:1 maximum
    
    # JPEG quality estimate
    MIN_JPEG_QUALITY_ESTIMATE: float = 30.0


# ─── Individual Checks ─────────────────────────────────────────────────────

def check_corrupted(image_path: str) -> Tuple[bool, str]:
    """Check if image file is corrupted or unreadable.
    
    Returns: (is_ok, message)
    """
    path = Path(image_path)
    if not path.exists():
        return False, "File not found"
    if path.stat().st_size == 0:
        return False, "Empty file"
    
    try:
        img = cv2.imread(str(path))
        if img is None:
            return False, "OpenCV cannot decode (corrupted)"
        if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
            return False, "Zero-dimension image"
    except Exception as e:
        return False, f"Decode error: {e}"
    
    return True, "OK"


def check_blur(image_path: str, threshold: Optional[float] = None) -> Tuple[bool, float, str]:
    """Detect blur using Laplacian variance.
    
    Returns: (passes_threshold, variance_value, message)
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False, 0.0, "Cannot read image"
    
    lap_var = cv2.Laplacian(img, cv2.CV_64F).var()
    th = threshold if threshold is not None else QualityThresholds.MIN_LAPLACIAN_VAR
    
    if lap_var < th:
        return False, lap_var, f"Blurry (Laplacian var={lap_var:.1f} < {th})"
    
    return True, lap_var, f"Sharp (Laplacian var={lap_var:.1f})"


def check_dimensions(image_path: str) -> Tuple[bool, int, int, str]:
    """Check minimum image dimensions.
    
    Returns: (passes, width, height, message)
    """
    img = cv2.imread(image_path)
    if img is None:
        return False, 0, 0, "Cannot read image"
    
    h, w = img.shape[:2]
    
    if w < QualityThresholds.MIN_WIDTH:
        return False, w, h, f"Too narrow ({w}px < {QualityThresholds.MIN_WIDTH}px)"
    if h < QualityThresholds.MIN_HEIGHT:
        return False, w, h, f"Too short ({h}px < {QualityThresholds.MIN_HEIGHT}px)"
    
    return True, w, h, f"OK ({w}x{h})"


def check_file_size(image_path: str) -> Tuple[bool, int, str]:
    """Check if file size is in acceptable range.
    
    Returns: (passes, size_bytes, message)
    """
    size = Path(image_path).stat().st_size
    
    if size < QualityThresholds.MIN_FILE_SIZE:
        return False, size, f"Too small ({size / 1024:.1f} KB)"
    if size > QualityThresholds.MAX_FILE_SIZE:
        return False, size, f"Too large ({size / 1024 / 1024:.1f} MB)"
    
    return True, size, f"OK ({size / 1024:.1f} KB)"


def check_contrast(image_path: str) -> Tuple[bool, float, str]:
    """Detect washed-out / low-contrast images.
    
    Uses standard deviation of pixel intensities as a proxy for contrast.
    
    Returns: (passes, std_dev, message)
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False, 0.0, "Cannot read image"
    
    std = img.std()
    
    if std < QualityThresholds.MIN_CONTRAST:
        return False, std, f"Low contrast / washed out (std={std:.1f} < {QualityThresholds.MIN_CONTRAST})"
    
    return True, std, f"Good contrast (std={std:.1f})"


def check_underexposed_overexposed(image_path: str) -> Tuple[str, float, str]:
    """Check if image is underexposed or overexposed.
    
    Returns: (status, mean_brightness, message)
        status: "ok" | "underexposed" | "overexposed"
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return "ok", 0.0, "Cannot read image"
    
    mean_brightness = img.mean()
    
    if mean_brightness < 30:
        return "underexposed", mean_brightness, f"Underexposed (mean={mean_brightness:.1f} / 255)"
    elif mean_brightness > 225:
        return "overexposed", mean_brightness, f"Overexposed (mean={mean_brightness:.1f} / 255)"
    
    return "ok", mean_brightness, f"Good exposure (mean={mean_brightness:.1f})"


def check_aspect_ratio(image_path: str) -> Tuple[bool, float, str]:
    """Check if aspect ratio is within acceptable range.
    
    Extreme ratios (e.g., 1:20 banners, very tall phone screenshots) 
    are not useful for product video backgrounds.
    
    Returns: (passes, ratio, message)
    """
    img = cv2.imread(image_path)
    if img is None:
        return False, 0.0, "Cannot read image"
    
    h, w = img.shape[:2]
    ratio = w / h if h > 0 else 1.0
    
    if ratio < QualityThresholds.MIN_ASPECT_RATIO:
        return False, ratio, f"Extreme tall ratio ({ratio:.2f} < {QualityThresholds.MIN_ASPECT_RATIO})"
    if ratio > QualityThresholds.MAX_ASPECT_RATIO:
        return False, ratio, f"Extreme wide ratio ({ratio:.2f} > {QualityThresholds.MAX_ASPECT_RATIO})"
    
    return True, ratio, f"OK (ratio={ratio:.2f})"


def check_object_coverage(image_path: str) -> Tuple[bool, float, str]:
    """Estimate whether the object fills enough of the frame.
    
    Uses Canny edge detection + contour analysis to find the main subject.
    A product photo where the object is tiny in a large frame is not useful.
    
    Returns: (passes, coverage_pct, message)
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        return False, 0.0, "Cannot read image"
    
    h, w = img.shape[:2]
    total_area = h * w
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Edge detection
    edges = cv2.Canny(gray, 50, 150)
    
    # Edge density as a quick check
    edge_density = edges.sum() / 255 / total_area
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return False, edge_density * 100, "No contours detected (maybe solid background)"
    
    # Sort contours by area (largest first)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    # Sum of top 5 contour areas
    top_contours_area = sum(cv2.contourArea(c) for c in contours[:5])
    coverage_pct = (top_contours_area / total_area) * 100
    
    # Also consider edge density: even without large contours,
    # if there's significant edge activity, something is there
    effective_coverage = max(coverage_pct, edge_density * 100)
    
    if effective_coverage < QualityThresholds.MIN_OBJECT_COVERAGE_PCT:
        return False, effective_coverage, (
            f"Object too small / scene too empty "
            f"(coverage={effective_coverage:.1f}% < {QualityThresholds.MIN_OBJECT_COVERAGE_PCT}%)"
        )
    
    return True, effective_coverage, f"Good coverage ({effective_coverage:.1f}%)"


def check_text_logo(image_path: str) -> Tuple[bool, float, str]:
    """Detect if image is mostly text/logo (bad for product video).
    
    Strategy: 
    - High horizontal edge density → likely text lines
    - Many small connected components → likely text characters
    - Low color variance → likely text on solid background
    
    Returns: (is_product_photo, text_score, message)
        is_product_photo: True if it looks like a product photo (not mostly text)
        text_score: 0.0-1.0 (higher = more text-like)
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        return True, 0.0, "Cannot read image"
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Horizontal edges (text lines create strong horizontal gradients)
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_x_mag = np.abs(sobel_x)
    
    # Vertical edges
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel_y_mag = np.abs(sobel_y)
    
    total_pixels = h * w
    
    # Ratio of horizontal to vertical edge strength
    # Text has strong horizontal edges (baselines, tops of letters)
    h_edge_ratio = sobel_x_mag.sum() / (sobel_y_mag.sum() + 1)
    
    # Normalize ratio: text typically has h_edge_ratio > 2.0
    h_edge_score = min(1.0, h_edge_ratio / 4.0)
    
    # Edge density
    edges = cv2.Canny(gray, 100, 200)
    edge_density = edges.sum() / 255 / total_pixels
    
    # High edge density + high horizontal bias = text
    edge_density_score = min(1.0, edge_density / QualityThresholds.MAX_EDGE_DENSITY_FOR_TEXT)
    
    # Color variance — text screenshots often have low color variance
    color_std = img.std()
    color_score = 1.0 - min(1.0, color_std / 80.0)  # lower std = more text-like
    
    # Connected components analysis — text has many small separate blobs
    # Choose the optimal binary direction: Otsu gives threshold value
    otsu_thresh, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)
    
    # For text detection, we want the FOREGROUND to be text characters
    # If threshold < 128, foreground is likely dark (text on light bg) — use inverted
    # If threshold >= 128, foreground is likely light (text on dark bg) — use standard
    if otsu_thresh < 128:
        # Text is dark on light background — use inverted binary
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        # Text is light on dark background — use standard binary
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    
    # Filter out background (label 0) and count components by size
    if num_labels > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        small_components = (areas > 3) & (areas < 500)  # text characters are usually small (lower min area to catch thin text)
        
        # Text-heavy images have many small connected components
        small_count = np.sum(small_components)
        
        # Text ratio: high proportion of small components relative to total area
        small_area = np.sum(areas[small_components]) if np.any(small_components) else 0
        small_area_ratio = small_area / total_pixels if total_pixels > 0 else 0
        
        # Product photos typically have fewer, larger connected components
        # Text images have many small components
        component_text_score = min(1.0, small_count / 50.0)  # >50 small components = likely text
    else:
        component_text_score = 0.0
        small_area_ratio = 0.0
    
    # Also detect if image has very few unique colors — typical of text overlays
    unique_colors = len(np.unique(gray)) if gray.size > 0 else 0
    color_uniqueness = unique_colors / 256.0  # 0.0-1.0
    low_color_score = 1.0 - color_uniqueness  # higher = fewer colors = more text-like
    
    # Text line detection via horizontal projection profile
    # Text lines create periodic peaks in horizontal projection
    horizontal_profile = cv2.reduce(binary, 1, cv2.REDUCE_AVG).flatten() / 255.0
    
    # Detect peaks in horizontal profile (text lines)
    from scipy.signal import find_peaks
    try:
        peaks, peak_props = find_peaks(horizontal_profile, height=0.1, distance=15)
        num_text_lines = len(peaks)
        text_line_score = min(1.0, num_text_lines / 10.0)  # >10 text lines = very text-heavy
    except ImportError:
        # Fallback: simple threshold
        line_transitions = np.sum(np.abs(np.diff(horizontal_profile > 0.1)))
        text_line_score = min(1.0, line_transitions / 20.0)
    
    # Combined text score — weighted average
    text_score = (
        h_edge_score * 0.10 +
        edge_density_score * 0.10 +
        color_score * 0.05 +
        low_color_score * 0.10 +
        component_text_score * 0.25 +
        text_line_score * 0.20 +
        small_area_ratio * 0.20
    )
    
    # === COMBINED RULES ===
    # High edge density + low color uniqueness + many small components = text
    if edge_density > 0.3 and color_uniqueness < 0.4 and component_text_score > 0.5:
        text_score = max(text_score, 0.7)
    
    # Many small blobs + text line profile + strong edges = text
    if component_text_score > 0.6 and text_line_score > 0.6 and edge_density > 0.1:
        text_score = max(text_score, 0.7)
    
    # Very high small area ratio = many tiny blobs = text characters
    if small_area_ratio > 0.3:
        text_score = max(text_score, 0.7)
    
    # Clean/solid bg + text lines + components = text overlay
    if text_line_score > 0.6 and component_text_score > 0.4 and color_uniqueness < 0.5:
        text_score = max(text_score, 0.7)
    
    if text_score > 0.6:
        return False, text_score, f"Likely text/logo (text_score={text_score:.2f})"
    
    return True, text_score, f"Looks like product photo (text_score={text_score:.2f})"


# ─── Composite Quality Score ───────────────────────────────────────────────

def compute_quality_score(image_path: str) -> Dict[str, Any]:
    """Run ALL quality checks and compute a composite score.
    
    This is the main entry point — replaces SAM3 Prodia calls.
    
    Returns dict with:
      - passed: bool — overall pass/fail
      - score: float — composite quality score (0-100)
      - checks: dict — per-check results
      - summary: str — human-readable summary
      - recommended: bool — whether to use this image
    """
    result = {
        "passed": True,
        "score": 100.0,
        "checks": {},
        "summary": "OK",
        "recommended": True,
    }
    
    # ─── Weighted checks ─────────────────────────────────────────────
    # Each check returns (passed, score_contrib, message)
    # score_contrib = the actual measured value
    
    # 1. Corrupted check (FATAL — 0 score if failed)
    is_ok, msg = check_corrupted(image_path)
    result["checks"]["corrupted"] = {"passed": is_ok, "value": msg}
    if not is_ok:
        result["passed"] = False
        result["score"] = 0
        result["summary"] = msg
        result["recommended"] = False
        return result
    
    # 2. File size check
    size_ok, size_bytes, size_msg = check_file_size(image_path)
    result["checks"]["file_size"] = {"passed": size_ok, "value": size_bytes, "message": size_msg}
    
    # 3. Blur check (weight: 25%)
    blur_ok, lap_var, blur_msg = check_blur(image_path)
    result["checks"]["blur"] = {"passed": blur_ok, "value": round(lap_var, 1), "message": blur_msg}
    blur_score = min(25.0, (lap_var / 200.0) * 25.0) if lap_var > 0 else 0
    
    # 4. Dimensions check (weight: 15%)
    dim_ok, w, h, dim_msg = check_dimensions(image_path)
    result["checks"]["dimensions"] = {"passed": dim_ok, "width": w, "height": h, "message": dim_msg}
    dim_score = 15.0 if dim_ok else 0
    
    # Bonus for high resolution
    if w > 1000 and h > 1000:
        dim_score = 20.0
    
    # 5. Contrast check (weight: 15%)
    contrast_ok, std, contrast_msg = check_contrast(image_path)
    result["checks"]["contrast"] = {"passed": contrast_ok, "value": round(std, 1), "message": contrast_msg}
    contrast_score = min(15.0, (std / 60.0) * 15.0) if std > 0 else 0
    
    # 6. Exposure check (weight: 10%)
    exp_status, mean_brightness, exp_msg = check_underexposed_overexposed(image_path)
    result["checks"]["exposure"] = {"status": exp_status, "value": round(mean_brightness, 1), "message": exp_msg}
    if exp_status == "ok":
        exp_score = 10.0
    elif exp_status in ("underexposed", "overexposed"):
        exp_score = 3.0  # penalty but not fatal
    else:
        exp_score = 10.0
    
    # 7. Aspect ratio check (weight: 5%)
    ratio_ok, ratio, ratio_msg = check_aspect_ratio(image_path)
    result["checks"]["aspect_ratio"] = {"passed": ratio_ok, "value": round(ratio, 2), "message": ratio_msg}
    ratio_score = 5.0 if ratio_ok else 0
    
    # 8. Object coverage check (weight: 20%)
    coverage_ok, coverage_pct, coverage_msg = check_object_coverage(image_path)
    result["checks"]["object_coverage"] = {
        "passed": coverage_ok,
        "value": round(coverage_pct, 1),
        "message": coverage_msg,
    }
    coverage_score = min(20.0, (coverage_pct / 30.0) * 20.0) if coverage_pct > 0 else 0
    
    # 9. Text/logo detection (weight: 20% total — max penalty if clearly text)
    is_product, text_score, text_msg = check_text_logo(image_path)
    result["checks"]["text_logo"] = {"passed": is_product, "value": round(text_score, 2), "message": text_msg}
    if not is_product:
        # Heavy penalty for text-y images — they're useless for product video
        text_score_penalty = text_score * -25.0  # up to -25 points
    else:
        # Mild bonus for clearly non-text images
        text_score_penalty = (1.0 - text_score) * 5.0
    
    # ─── Composite score (0-100) ──────────────────────────────────────
    total = blur_score + dim_score + contrast_score + exp_score + ratio_score + coverage_score + text_score_penalty
    total = max(0, min(100, total))
    
    result["score"] = round(total, 1)
    
    # ─── Overall pass/fail ─────────────────────────────────────────────
    fatal_fails = [
        not size_ok,
        not dim_ok,
    ]
    
    if any(fatal_fails):
        result["passed"] = False
        result["recommended"] = False
        result["summary"] = f"Failed: {[k for k, v in result['checks'].items() if not v.get('passed', True)]}"
    elif total < 30:
        result["passed"] = True
        result["recommended"] = False
        result["summary"] = f"Low quality (score={total:.0f}/100)"
    elif total < 55:
        result["passed"] = True
        result["recommended"] = True
        result["summary"] = f"Acceptable quality (score={total:.0f}/100)"
    else:
        result["passed"] = True
        result["recommended"] = True
        result["summary"] = f"Good quality (score={total:.0f}/100)"
    
    return result


# ─── Batch Runner ──────────────────────────────────────────────────────────

def batch_check(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run quality gate on multiple images and return filtered + scored list.
    
    Args:
        images: List of dicts with at least {"local_path": str, "url": str, "filename": str}
    
    Returns:
        Same list but enriched with quality results and sorted by score descending.
        Images that fail critical checks are marked "recommended": False.
    """
    results = []
    
    for img in images:
        local_path = img.get("local_path", "")
        if not local_path or not Path(local_path).exists():
            # Try the filename-based path
            fname = img.get("filename", "")
            alt_path = str(Path(img.get("local_path", "")) / fname)
            if Path(alt_path).exists():
                local_path = alt_path
            else:
                # Try looking in PRODUCT_IMAGE_DIR
                product_dir = Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images")
                possible = product_dir / fname
                if possible.exists():
                    local_path = str(possible)
        
        if not local_path or not Path(local_path).exists():
            logger.warning(f"  Quality gate: cannot find {img.get('filename', '?')} at {local_path} — skipping check")
            results.append({
                **img,
                "quality_score": 50.0,
                "quality_recommended": True,
                "quality_passed": True,
                "quality_summary": "No local file to check",
            })
            continue
        
        try:
            q = compute_quality_score(local_path)
            logger.info(f"  Quality gate [{img.get('filename', '?')}]: score={q['score']}/100, recommended={q.get('recommended')}")
            results.append({
                **img,
                "quality_score": q["score"],
                "quality_recommended": q.get("recommended", True),
                "quality_passed": q.get("passed", True),
                "quality_summary": q.get("summary", "OK"),
                "quality_checks": q.get("checks", {}),
            })
        except Exception as e:
            logger.warning(f"  Quality gate error for {img.get('filename', '?')}: {e}")
            results.append({
                **img,
                "quality_score": 50.0,
                "quality_recommended": True,
                "quality_passed": True,
                "quality_summary": f"Check error: {e}",
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    
    return results


# ─── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys, json
    
    parser = argparse.ArgumentParser(description="SAM3 Quality Gate — Rule-based Image Checker")
    parser.add_argument("image", nargs="+", help="Image path(s)")
    parser.add_argument("--thresholds", help="JSON file with custom thresholds")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    for img_path in args.image:
        if not Path(img_path).exists():
            print(f"NOT FOUND: {img_path}")
            continue
        
        result = compute_quality_score(img_path)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            score = result["score"]
            rec = "✅" if result.get("recommended") else "❌"
            print(f"\n{'='*50}")
            print(f"{rec} {img_path}")
            print(f"  Score: {score}/100  |  Passed: {result.get('passed')}")
            print(f"  Summary: {result.get('summary')}")
            print(f"  Checks:")
            for name, check in result.get("checks", {}).items():
                status = "✅" if check.get("passed", check.get("status") in (None, "ok")) else "❌"
                print(f"    {status} {name}: {check.get('message', check.get('value', '?'))}")
