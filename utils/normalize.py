from datetime import datetime
import re

def normalize_product_data(raw_data, product_url, extraction_date=None):
    # print(raw_data["Discount"])
    if extraction_date is None:
        extraction_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    offer_details = raw_data.get("Offer Details", "")
    best_price = extract_best_price(offer_details)

    original_price = clean_price(raw_data.get("Original Price (INR)", ""))
    if not original_price:
        original_price = clean_price(raw_data.get("Price (INR)", ""))

    price_inr = clean_price(best_price) if best_price else clean_price(raw_data.get("Price (INR)", ""))

    # FIX: Use discount from raw data if present; otherwise, calculate
    discount = raw_data.get("Discount", "")
    if not discount:
        try:
            orig_price_val = float(original_price) if original_price else 0
            price_val = float(price_inr) if price_inr else 0
            if orig_price_val > 0 and price_val > 0 and price_val < orig_price_val:
                discount = f"{round(((orig_price_val - price_val) / orig_price_val) * 100)}%"
        except Exception:
            discount = ""

    product_details = extract_product_details(raw_data)
    additional_details = extract_additional_details(raw_data)

    about_this_item = raw_data.get("About This Item", {})
    if isinstance(about_this_item, list):
        about_this_item = "\n".join(about_this_item)
    elif isinstance(about_this_item, dict):
        about_this_item = about_this_item
    else:
        about_this_item = str(about_this_item)

    all_bullet_points = raw_data.get("All Bullet Points", [])
    if isinstance(all_bullet_points, dict):
        all_bullet_points = "\n".join([f"{k}: {v}" for k, v in all_bullet_points.items()])
    elif isinstance(all_bullet_points, list):
        all_bullet_points = all_bullet_points
    else:
        all_bullet_points = [str(all_bullet_points)]

    normalized = {
        "Data ID": raw_data.get("Data ID", ""),
        "Product URL": raw_data.get("Product URL", product_url),
        "Brand Name": raw_data.get("Brand Name", ""),
        "Product Name": raw_data.get("Product Name", raw_data.get("Product Name (PDP)", "")),
        "Rating": extract_numeric_rating(raw_data.get("Rating", "")),
        "Rating Count": extract_numeric_count(raw_data.get("Rating Count", "")),
        "Price (INR)": price_inr,
        "Original Price (INR)": original_price,
        "Discount": discount,
        "Badge": raw_data.get("Badge", ""),
        "Date of Extraction": extraction_date,
        "Product Details": product_details,
        "About This Item": about_this_item,
        "All Bullet Points": all_bullet_points,
        "Additional Details": additional_details,
        "Brand Snapshot": raw_data.get("Brand Snapshot", {}),
        "Product and Seller Details": raw_data.get("Product and Seller Details", {}),
        "Product Description": raw_data.get("Product Description", "")
    }

    for key, value in normalized.items():
        if value is None:
            normalized[key] = "" if not isinstance(value, (dict, list)) else {} if isinstance(value, dict) else []

    return normalized


def clean_price(price_str):
    """Clean ₹ symbols and commas; return as string."""
    if not price_str:
        return ""
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    return cleaned

def extract_best_price(offer_details):
    """
    Extract 'Best Price: Rs. xxxx' from offer details if present.
    """
    if not offer_details:
        return ""
    match = re.search(r'Best Price:\s*Rs\.\s*(\d+)', offer_details)
    return match.group(1) if match else ""

def extract_product_details(raw_data):
    """
    Extract product details which might be a string, list, or dict depending on source.
    """
    details = raw_data.get("Product Details", "")
    if isinstance(details, list):
        return "\n".join(details)
    elif isinstance(details, dict):
        return "\n".join([f"{k}: {v}" for k, v in details.items()])
    return str(details)

def extract_additional_details(raw_data):
    """
    Collect extra details like Size & Fit, Material & Care, etc.
    """
    keys_to_extract = [
        "Size & Fit", "Material & Care", "Collar", "Fit",
        "Sleeve Length", "Bottom Closure", "Front Styling", "Type"
    ]
    additional = {}
    for key in keys_to_extract:
        value = raw_data.get(key, "")
        if value:
            additional[key] = value
    return additional

def extract_numeric_rating(rating_str):
    """
    Extract numeric rating from strings like '3.9 out of 5 stars'.
    """
    if not rating_str or rating_str.strip().upper() == "N/A":
        return ""
    match = re.search(r'([\d.]+)', str(rating_str))
    return match.group(1) if match else ""

def extract_numeric_count(count_str):
    """
    Extract numeric count from strings like '769 ratings'.
    """
    if not count_str or count_str.strip().upper() == "N/A":
        return ""
    match = re.search(r'(\d+)', str(count_str.replace(",", "")))
    return match.group(1) if match else ""
