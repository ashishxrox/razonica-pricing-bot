from datetime import datetime as dt
def extract_flipkart_pdp_data(soup, url):
    try:
        brand = soup.select_one("span.mEh187")
        name = soup.select_one("span.VU-ZEz")
        price = soup.select_one("div.Nx9bqj")
        original_price = soup.select_one("div.yRaY8j")
        discount = soup.select_one("div.UkUFwK span")
        rating_div = soup.select_one("span.Y1HWO0 div.XQDdHH")
        rating_text = rating_div.text.strip() if rating_div else None
        rating_count = soup.select_one("span.Wphh3N span")

        sizes = []
        size_blocks = soup.select("ul.hSEbzK li")
        for li in size_blocks:
            size_text = li.select_one("a")
            detail = li.select_one("div.V3Zflw")
            if size_text and detail:
                sizes.append(f"{size_text.text.strip()}: {detail.text.strip()}")

        seller = soup.select_one("div#sellerName span span")
        seller_rating = soup.select_one("div.XQDdHH.uuhqql")
        seller_name = seller.text.strip() if seller else None
        seller_rating_text = seller_rating.text.strip() if seller_rating else None

        specs = {}
        spec_rows = soup.select("div.Cnl9Jt div._5Pmv5S div.row")
        for row in spec_rows:
            key_div = row.select_one("div.col.col-3-12")
            val_div = row.select_one("div.col.col-9-12")
            if key_div and val_div:
                specs[key_div.text.strip()] = val_div.text.strip()

        descriptions = []
        desc_blocks = soup.select("div.pqHCzB > div")
        for block in desc_blocks:
            img_div = block.select_one("div._0B07y7 img")
            img_url = img_div["src"].strip() if img_div and "src" in img_div.attrs else None
            title_div = block.select_one("div._9GQWrZ")
            para = block.select_one("div.AoD2-N p")
            descriptions.append({
                "Image URL": img_url,
                "Title": title_div.text.strip() if title_div else None,
                "Text": para.text.strip() if para else None
            })

        flat_blocks = soup.select("div._9GQWrZ")
        for title_div in flat_blocks:
            parent = title_div.find_parent()
            para = parent.select_one("div.AoD2-N p") if parent else None
            if title_div and para:
                descriptions.append({
                    "Image URL": None,
                    "Title": title_div.text.strip(),
                    "Text": para.text.strip()
                })

        reviews_section = soup.select_one("a[href*='/product-reviews/'] div._23J90q.iIbIvC span._6n9Uuq")
        review_summary = reviews_section.text.strip() if reviews_section else None
        review_link_tag = soup.select_one("a[href*='/product-reviews/']:has(div._23J90q.iIbIvC)")
        review_link = f"https://www.flipkart.com{review_link_tag['href'].strip()}" if review_link_tag and 'href' in review_link_tag.attrs else None

        return {
            "Product URL": url,
            "Brand Name": brand.text.strip() if brand else None,
            "Product Name": name.text.strip() if name else None,
            "Price (INR)": price.text.strip() if price else None,
            "Original Price (INR)": original_price.text.strip() if original_price else None,
            "Discount": discount.text.strip() if discount else None,
            "Rating": rating_text,
            "Rating Count": rating_count.text.strip() if rating_count else None,
            "Sizes": sizes,
            "Seller Name": seller_name,
            "Seller Rating": seller_rating_text,
            "Specifications": specs,
            "Description Cards": descriptions,
            "All Reviews Summary": review_summary,
            "All Reviews Link": review_link,
            "Date of Extraction": dt.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Error extracting {url}: {e}")
        return None
