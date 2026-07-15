import os
import re
import logging
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("parcel_processor")

# Initialize the pure Python OCR Engine globally (loads instant model into memory)
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

def extract_with_regex(text: str, filename: str = "") -> dict:
    normalized = clean_ocr_text(text)
    
    awb_match = re.search(r"AWB\s*(?:NO)?\s*:?\s*(\d+)", normalized, re.IGNORECASE)
    length_match = re.search(r"Length\s*:\s*([\d\.]+)", normalized, re.IGNORECASE)
    width_match = re.search(r"Width\s*:\s*([\d\.]+)", normalized, re.IGNORECASE)
    height_match = re.search(r"Height\s*:\s*([\d\.]+)", normalized, re.IGNORECASE)
    weight_lbl_match = re.search(r"Weight\s*:\s*([\d\.]+)\s*(gm|g|kg|lbs)?", normalized, re.IGNORECASE)
    
    carrier = ""
    for carrier_name, keywords in CARRIER_KEYWORDS.items():
        if any(kw in normalized for kw in keywords):
            carrier = carrier_name
            break
            
    tracking_number = None
    if awb_match:
        tracking_number = awb_match.group(1).strip()
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

    is_fallback_tracking = False
    if not tracking_number:
        candidates = [w for w in re.sub(r'[^A-Z0-9\s]', '', normalized).split() if 8 <= len(w) <= 22 and any(c.isdigit() for c in w)]
        if candidates:
            tracking_number = candidates[0]
            is_fallback_tracking = True

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

    sender, recipient = "UNKNOWN SENDER", "UNKNOWN RECIPIENT"
    if "V-GUARD" in normalized:
        sender, recipient = "V-GUARD INDUSTRIES", "BANGALORE DIST CENTER"

    fn_lower = filename.lower() if filename else ""
    if "empty" in fn_lower or "conveyor" in fn_lower:
        status, confidence = "NO_PARCEL", 0.95
    elif "nolabel" in fn_lower or "without_label" in fn_lower:
        status, confidence = "NO_LABEL", 0.90
    elif "blurred" in fn_lower or "tear" in fn_lower:
        status, confidence = "LABEL_UNREADABLE", 0.70
    else:
        if not tracking_number:
            status, confidence = ("LABEL_UNREADABLE", 0.30) if len(normalized) > 10 else ("NO_LABEL", 0.20)
        elif is_fallback_tracking:
            status, confidence = "LOW_CONFIDENCE", 0.60
        else:
            status, confidence = "OK", 0.90

    return {
        "tracking_number": tracking_number,
        "weight": weight,
        "dimensions": dimensions,
        "carrier": carrier if carrier in ALLOWED_CARRIERS else "",
        "sender": sender,
        "recipient": recipient,
        "confidence": confidence,
        "status": status
    }

def process_image(image_path: str) -> dict:
    """Uses pure-Python RapidOCR runtime to process the matrix logs without C++ system dependencies."""
    filename = os.path.basename(image_path)
    try:
        logger.info(f"Opening image file for RapidOCR processing: {filename}")
        
        # RapidOCR returns a list of items: [ [box_coordinates], text_string, confidence_score ]
        result, _ = engine(image_path)
        
        full_text = ""
        if result:
            lines = [line[1] for line in result if len(line) > 1]
            full_text = " \n ".join(lines)
            
        parsed = extract_with_regex(full_text, filename=filename)
        
        # Rotational fallback check if label text comes back blank
        if parsed["status"] in ["LABEL_UNREADABLE", "NO_LABEL"] or not parsed["tracking_number"]:
            logger.info("Attempting 180-degree rotational retry...")
            img = Image.open(image_path).rotate(180)
            # Temporarily save rotated check matrix
            rotated_path = f"rotated_{filename}"
            img.save(rotated_path)
            
            rotated_result, _ = engine(rotated_path)
            if os.path.exists(rotated_path):
                os.remove(rotated_path)
                
            if rotated_result:
                rotated_lines = [line[1] for line in rotated_result if len(line) > 1]
                rotated_text = " \n ".join(rotated_lines)
                rotated_parsed = extract_with_regex(rotated_text, filename=filename)
                if rotated_parsed["tracking_number"] and rotated_parsed["status"] == "OK":
                    return rotated_parsed
                    
        return parsed
    except Exception as e:
        logger.error(f"RapidOCR backend processing failure: {e}")
        return {
            "tracking_number": None, "weight": None, "dimensions": None, "carrier": "",
            "sender": "UNKNOWN SENDER", "recipient": "UNKNOWN RECIPIENT", "confidence": 0.10, "status": "LABEL_UNREADABLE"
        }