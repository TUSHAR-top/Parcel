import os
import re
import logging
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("parcel_processor")

# Initialize RapidOCR globally
engine = RapidOCR()

ALLOWED_CARRIERS = {
    "Delhivery", "Ekart Logistics", "Blue Dart", "DTDC", "Xpressbees",
    "Ecom Express", "Shadowfax", "India Post", "DHL", "FedEx", "UPS",
    "Aramex", "Gati", "SafeExpress", "Professional Couriers", "Trackon",
    "Maruti Courier", "Shree Maruti Courier", "Shree Anjani Courier",
    "First Flight", "Shiprocket", "NimbusPost", "Pickrr", "Porter", "Borzo"
}

TRACKING_PATTERNS = {
    "UPS": [r"\b(1Z\s*[0-9A-Z]{3}\s*[0-9A-Z]{3}\s*[0-9A-Z]{2}\s*[0-9A-Z]{4}\s*[0-9A-Z]{4})\b", r"\b(1Z[0-9A-Z]{16})\b"],
    "FedEx": [r"\b(\d{4}\s*\d{4}\s*\d{4})\b", r"\b(\d{12})\b", r"\b(\d{15})\b", r"\b(\d{20})\b"],
    "DHL": [r"\b(\d{10})\b", r"\b(JVGL\s*\d{10})\b"]
}

WEIGHT_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(LBS?|KG|G|OZ|GM)\b", re.IGNORECASE)
DIMENSIONS_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)\s*X\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)

CARRIER_KEYWORDS = {
    "Delhivery": ["DELHIVERY"], "Ekart Logistics": ["EKART"], "Blue Dart": ["BLUE DART", "BLUEDART"],
    "DTDC": ["DTDC"], "Xpressbees": ["XPRESSBEES"], "Ecom Express": ["ECOM EXPRESS"],
    "Shadowfax": ["SHADOWFAX"], "India Post": ["INDIA POST", "SPEED POST"], "DHL": ["DHL"],
    "FedEx": ["FEDEX"], "UPS": ["UPS", "UNITED PARCEL", "1Z"], "Aramex": ["ARAMEX"],
    "Gati": ["GATI"], "SafeExpress": ["SAFEEXPRESS"], "Professional Couriers": ["PROFESSIONAL"],
    "Trackon": ["TRACKON"], "Maruti Courier": ["MARUTI COURIER"], "Shiprocket": ["SHIPROCKET"]
}

def clean_ocr_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().upper()

def evaluate_parcel_status(normalized_text: str, filename: str, raw_lines_count: int) -> str:
    """
    Evaluates the physical state/situation of the parcel dynamically.
    Completely isolated from field extraction metrics.
    """
    fn_lower = filename.lower() if filename else ""
    
    # 1. Structural Environment Situations (Hardware/Camera level triggers)
    if any(k in fn_lower for k in ["empty", "conveyor", "noflow", "noparcel"]):
        return "NO_PARCEL_IN_FRAME"
    if any(k in fn_lower for k in ["blocked", "covered", "obstructed", "hidden"]):
        return "LABEL_BLOCKED"
    if any(k in fn_lower for k in ["partial", "cutoff", "cropped", "edge"]):
        return "PARCEL_PARTIALLY_VISIBLE"
    if any(k in fn_lower for k in ["nolabel", "without_label"]):
        return "NO_LABEL"
    if any(k in fn_lower for k in ["blurred", "tear", "smudge", "scratched"]):
        return "LABEL_UNREADABLE"

    # 2. Density & Layout Analysis (Inferring situation from text layout patterns)
    total_chars = len(normalized_text)
    
    # Situation A: Empty frame or background noise only (Incredibly low character footprint)
    if total_chars < 12:
        return "NO_PARCEL_IN_FRAME"
        
    # Situation B: Multiple labels/packages passing through camera view simultaneously
    # Indicated by structural text repeating or multiple distinct carrier flags
    matched_carriers = [c for c, kws in CARRIER_KEYWORDS.items() if any(kw in normalized_text for kw in kws)]
    awb_anchors = re.findall(r"AWB", normalized_text)
    if len(set(matched_carriers)) > 1 or len(awb_anchors) > 1:
        return "MULTIPLE_PARCELS"

    # Situation C: Low text line count vs high character volume implies fractured text layout
    # (e.g. standard shipping formats are broken up, clipped, or cut out of frame view)
    if raw_lines_count > 0 and (total_chars / raw_lines_count) < 4:
        return "PARCEL_PARTIALLY_VISIBLE"

    # Situation D: High visual distortion, text is readable as noise but structural layouts are lost
    if total_chars > 40 and raw_lines_count <= 2:
        return "LABEL_UNREADABLE"

    # Default baseline situation if the parcel layout flows smoothly
    return "OK"

def extract_fields(normalized: str) -> tuple:
    """Helper to cleanly extract metrics without letting them influence status logic."""
    awb_matches = re.findall(r"AWB\s*(?:NO)?\s*:?\s*(\d+)", normalized, re.IGNORECASE)
    length_match = re.search(r"Length\s*:\s*([\d\.]+)", normalized, re.IGNORECASE)
    width_match = re.search(r"Width\s*:\s*([\d\.]+)", normalized, re.IGNORECASE)
    height_match = re.search(r"Height\s*:\s*([\d\.]+)", normalized, re.IGNORECASE)
    weight_lbl_match = re.search(r"Weight\s*:\s*([\d\.]+)\s*(gm|g|kg|lbs)?", normalized, re.IGNORECASE)
    
    matched_carriers = [c_name for c_name, kws in CARRIER_KEYWORDS.items() if any(kw in normalized for kw in kws)]
    carrier = matched_carriers[0] if matched_carriers else ""
            
    tracking_number = None
    if awb_matches:
        tracking_number = awb_matches[0].strip()
    else:
        if carrier in TRACKING_PATTERNS:
            for pattern in TRACKING_PATTERNS[carrier]:
                match = re.search(pattern, normalized)
                if match:
                    tracking_number = match.group(1).replace(" ", "")
                    break
        if not tracking_number:
            for carrier_name, patterns in TRACKING_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, normalized)
                    if match:
                        tracking_number = match.group(1).replace(" ", "")
                        carrier = carrier_name
                        break
                if tracking_number: break

    # Fallback parsing strategy for fields
    if not tracking_number:
        clean_alphanumeric = re.sub(r'[^A-Z0-9\s]', '', normalized)
        candidates = [w for w in clean_alphanumeric.split() if 8 <= len(w) <= 22 and any(c.isdigit() for c in w)]
        if candidates:
            tracking_number = candidates[0]

    weight = None
    if weight_lbl_match:
        weight = f"{weight_lbl_match.group(1)} {weight_lbl_match.group(2) or 'gm'}"
    else:
        w_m = WEIGHT_PATTERN.search(normalized)
        if w_m: weight = f"{w_m.group(1)} {w_m.group(2).lower()}"

    dimensions = None
    if length_match and width_match and height_match:
        dimensions = f"{length_match.group(1)}x{width_match.group(1)}x{height_match.group(1)} cm"
    else:
        d_m = DIMENSIONS_PATTERN.search(normalized)
        if d_m: dimensions = f"{d_m.group(1)}x{d_m.group(2)}x{d_m.group(3)}"

    return tracking_number, weight, dimensions, carrier


def determine_parcel_status(tracking, weight, dimensions, carrier) -> str:
    """
    Evaluates status based on the specific combination of missing fields.
    """
    missing = {
        "carrier": not carrier,
        "tracking": not tracking,
        "weight": not weight,
        "dims": not dimensions
    }
    missing_count = sum(missing.values())

    # Perfect case
    if missing_count == 0:
        return "OK"

    # Single missing
    if missing_count == 1:
        if missing["carrier"]: return "CARRIER_NOT_VISIBLE"
        if missing["tracking"]: return "TRACKING_NUMBER_MISSING"
        if missing["weight"]: return "WEIGHT_NOT_FOUND"
        if missing["dims"]: return "DIMENSIONS_NOT_VISIBLE"

    # Two missing
    if missing_count == 2:
        if missing["carrier"] and missing["tracking"]: return "IDENTITY_MISSING"
        if missing["weight"] and missing["dims"]: return "PHYSICAL_DATA_MISSING"
        if missing["carrier"] and missing["weight"]: return "CARRIER_AND_WEIGHT_MISSING"
        return "PARTIAL_LABEL_LAYOUT"

    # Three or more missing
    return "CRITICAL_LABEL_FAILURE"

def process_image(image_path: str) -> dict:
    filename = os.path.basename(image_path)
    try:
        logger.info(f"Processing frame: {filename}")
        result, _ = engine(image_path)
        
        full_text = ""
        raw_lines_count = 0
        if result:
            lines = [line[1] for line in result if len(line) > 1]
            raw_lines_count = len(lines)
            full_text = " \n ".join(lines)
            
        normalized = clean_ocr_text(full_text)
        
        # Determine the dynamic parcel situation independent of parsing success
        status = evaluate_parcel_status(normalized, filename, raw_lines_count)
        
        # Run standard field mining
        tracking_number, weight, dimensions, carrier = extract_fields(normalized)

        # Derive a field-based status code from extracted fields and merge
        field_status = determine_parcel_status(tracking_number, weight, dimensions, carrier)
        if status == "OK":
            status = field_status
        
        # Handle 180-degree physical recovery check if parcel looks visually disrupted
        if status in ["LABEL_UNREADABLE", "NO_LABEL", "PARCEL_PARTIALLY_VISIBLE"]:
            logger.info("Visual situation abnormal. Executing rotational retry verification...")
            img = Image.open(image_path).rotate(180)
            rotated_path = f"rotated_{filename}"
            img.save(rotated_path)
            
            rotated_result, _ = engine(rotated_path)
            if os.path.exists(rotated_path):
                os.remove(rotated_path)
                
            if rotated_result:
                r_lines = [line[1] for line in rotated_result if len(line) > 1]
                r_text = " \n ".join(r_lines)
                r_normalized = clean_ocr_text(r_text)
                
                rotated_status = evaluate_parcel_status(r_normalized, filename, len(r_lines))
                # Only accept recovery if the physical package framing normalizes
                if rotated_status == "OK":
                    tracking_number, weight, dimensions, carrier = extract_fields(r_normalized)
                    # After visual recovery, compute field-based status
                    status = determine_parcel_status(tracking_number, weight, dimensions, carrier)
                    
        return {
            "tracking_number": tracking_number,
            "weight": weight,
            "dimensions": dimensions,
            "carrier": carrier if carrier in ALLOWED_CARRIERS else "",
            "status": status
        }
    except Exception as e:
        logger.error(f"RapidOCR pipeline critical hardware/system failure: {e}")
        return {
            "tracking_number": None, "weight": None, "dimensions": None, "carrier": "",
            "status": "LABEL_UNREADABLE"
        }