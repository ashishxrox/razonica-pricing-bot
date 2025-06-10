def preprocess_flipkart_data(raw_data):
    """
    Reorganizes Flipkart product data into a uniform format with the specified columns.
    No data is deleted; all relevant fields are placed into the defined columns.
    """

    processed_data = {
        "Product Details": "",
        "About This Item": "",
        "All Bullet Points": "",
        "Additional Details": "",
        "Brand Snapshot": "",
        "Product and Seller Details": "",
        "Product Description": "",
        "Source URL": raw_data.get("Product URL", "")
    }

    # 1️⃣ Product details
    product_details = []
    if raw_data.get("Product Name"):
        product_details.append(f"Product Name: {raw_data['Product Name']}")
    if raw_data.get("Price (INR)"):
        product_details.append(f"Price: {raw_data['Price (INR)']}")
    if raw_data.get("Original Price (INR)"):
        product_details.append(f"Original Price: {raw_data['Original Price (INR)']}")
    if raw_data.get("Discount"):
        product_details.append(f"Discount: {raw_data['Discount']}")
    if raw_data.get("Rating"):
        product_details.append(f"Rating: {raw_data['Rating']}")
    if raw_data.get("Rating Count"):
        product_details.append(f"Rating Count: {raw_data['Rating Count']}")
    processed_data["Product Details"] = "\n".join(product_details)

    # 2️⃣ About this item
    if raw_data.get("Specifications"):
        processed_data["About This Item"] = str(raw_data["Specifications"])

    # 3️⃣ All bullet points
    # Flipkart scraper doesn’t provide bullet points separately, so we leave this empty.

    # 4️⃣ Additional details
    additional_details = []
    if raw_data.get("Sizes"):
        additional_details.append(f"Sizes: {raw_data['Sizes']}")
    if raw_data.get("All Reviews Summary"):
        additional_details.append(f"Reviews Summary: {raw_data['All Reviews Summary']}")
    if raw_data.get("All Reviews Link"):
        additional_details.append(f"Reviews Link: {raw_data['All Reviews Link']}")
    if raw_data.get("Date of Extraction"):
        additional_details.append(f"Date of Extraction: {raw_data['Date of Extraction']}")
    processed_data["Additional Details"] = "\n".join(additional_details)

    # 5️⃣ Brand Snap shot
    if raw_data.get("Brand Name"):
        processed_data["Brand Snapshot"] = raw_data["Brand Name"]

    # 6️⃣ Product and Seller details
    seller_details = []
    if raw_data.get("Seller Name"):
        seller_details.append(f"Seller Name: {raw_data['Seller Name']}")
    if raw_data.get("Seller Rating"):
        seller_details.append(f"Seller Rating: {raw_data['Seller Rating']}")
    processed_data["Product and Seller Details"] = "\n".join(seller_details)

    # 7️⃣ Product Description
    if raw_data.get("Description Cards"):
        processed_data["Product Description"] = str(raw_data["Description Cards"])

    # 8️⃣ Source URL — already handled

    return processed_data
