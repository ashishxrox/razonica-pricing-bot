import os
import json
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from playwright.sync_api import sync_playwright

# Global variables
pdp_links = []
output_dir = ""

# === ORIGINAL extract_pdp_data FUNCTION (unchanged) ===
def extract_pdp_data(page):
    def get_all_facts():
        facts = {}
        try:
            fact_containers = page.query_selector_all("div.a-fixed-left-grid.product-facts-detail")
            for container in fact_containers:
                left = container.query_selector("div.a-col-left")
                right = container.query_selector("div.a-col-right")
                if left and right:
                    left_text = left.inner_text().strip().rstrip(":")
                    right_text = right.inner_text().strip()
                    if left_text and right_text:
                        facts[left_text] = right_text
        except:
            pass
        return facts

    def get_bullet_points():
        bullets = page.query_selector_all("div.a-expander-content ul.a-unordered-list li")
        return [li.inner_text().strip() for li in bullets if li.inner_text().strip()]

    def find_bullet_by_keywords(keywords):
        bullets = get_bullet_points()
        for text in bullets:
            lower_text = text.lower()
            for kw in keywords:
                if kw.lower().rstrip(":") in lower_text:
                    return text
        return ""

    keyword_map = {
        "Fabric Info": ["fabric", "kurta and bottom fabric"],
        "Color Info": ["color :-", "color"],
        "Style Info": ["style"],
        "Length Info": ["length"],
        "Sleeve Info": ["sleeves"],
        "Size Chart": ["size chart"],
        "Includes Info": ["this set includes"],
        "Work/Design Info": ["work :-", "work"],
        "Neck Style": ["neck style:-", "neck style"],
        "Color Disclaimer": ["colour declaration"],
        "Occasion / Usage": ["occasion", "ocassion"],
        "Brand Mention / CTA": ["click on brand name"]
    }

    about_this_item_dict = {}
    for label, keywords in keyword_map.items():
        val = find_bullet_by_keywords(keywords)
        if val:
            about_this_item_dict[label] = val

    full_bullets = get_bullet_points()

    def get_additional_details():
        additional_keys = [
            "Manufacturer", "Item Weight", "Product Dimensions", "Country of Origin",
            "Packer", "Importer", "Net Quantity", "Included Components"
        ]
        details = {}
        try:
            containers = page.query_selector_all("div.a-fixed-left-grid")
            for container in containers:
                left = container.query_selector("div.a-fixed-left-grid-col.a-col-left span")
                right = container.query_selector("div.a-fixed-left-grid-col.a-col-right span")
                if left and right:
                    key = left.inner_text().strip().rstrip(":")
                    value = right.inner_text().strip()
                    if key in additional_keys and value:
                        details[key] = value
        except:
            pass
        return details

    def get_brand_snapshot():
        brand_snapshot = {}
        try:
            brand_container = page.query_selector("div.a-cardui-body.brand-snapshot-card-content")
            if brand_container:
                brand_name_span = brand_container.query_selector("p > span.a-size-medium.a-text-bold")
                if brand_name_span:
                    brand_snapshot["Brand Name"] = brand_name_span.inner_text().strip()

            title_container = page.query_selector("div.a-section.a-text-center.brand-snapshot-title-container > p")
            if title_container:
                brand_snapshot["Top Brand Heading"] = title_container.inner_text().strip()

            list_items = page.query_selector_all("div.a-section.a-spacing-base.brand-snapshot-flex-row[role='listitem']")
            if list_items and len(list_items) >= 3:
                pos_rating = list_items[0].query_selector("p")
                if pos_rating:
                    brand_snapshot["Positive Ratings"] = pos_rating.inner_text().strip()

                recent_orders = list_items[1].query_selector("p")
                if recent_orders:
                    brand_snapshot["Recent Orders"] = recent_orders.inner_text().strip()

                years_amazon = list_items[2].query_selector("p")
                if years_amazon:
                    brand_snapshot["Years on Amazon"] = years_amazon.inner_text().strip()

                badge_images = []
                for item in list_items:
                    img = item.query_selector("img.brand-snapshot-item-image")
                    if img:
                        src = img.get_attribute("src")
                        if src:
                            badge_images.append(src)
                if badge_images:
                    brand_snapshot["Brand Badge Image URLs"] = badge_images

        except:
            pass
        return brand_snapshot

    def get_product_description():
        try:
            desc_div = page.query_selector("#productDescription_feature_div #productDescription.a-section.a-spacing-small p span")
            if desc_div:
                return desc_div.inner_text().strip()
        except:
            pass
        return ""

    def get_product_and_seller_details():
        details = {}
        try:
            li_elements = page.query_selector_all("li")
            for li in li_elements:
                key_span = li.query_selector("span.a-text-bold")
                if key_span:
                    key = key_span.inner_text().strip().rstrip(":")
                    required_keys = [
                        "Product Dimensions", "Date First Available", "Manufacturer", "ASIN",
                        "Item model number", "Country of Origin", "Department", "Packer",
                        "Importer", "Item Weight", "Item Dimensions LxWxH", "Net Quantity",
                        "Included Components", "Generic Name"
                    ]
                    if key in required_keys:
                        full_text = li.inner_text().strip()
                        value = full_text.replace(key_span.inner_text().strip(), "").strip(" :\n")
                        details[key] = value
        except:
            pass
        return details

    pdp_data = {
        "Product Details": get_all_facts(),
        "About This Item": about_this_item_dict,
        "All Bullet Points": full_bullets,
        "Additional Details": get_additional_details(),
        "Brand Snapshot": get_brand_snapshot(),
        "Product and Seller Details": get_product_and_seller_details(),
        "Product Description": get_product_description()
    }

    return pdp_data

# === GUI ===
def start_gui():
    def add_link():
        link = link_entry.get().strip()
        if link:
            links_listbox.insert(tk.END, link)
            link_entry.delete(0, tk.END)

    def browse_dir():
        global output_dir
        output_dir = filedialog.askdirectory()
        if output_dir:
            dir_label.config(text=output_dir)

    def start_scraping():
        global pdp_links
        pdp_links = list(links_listbox.get(0, tk.END))
        if not pdp_links or not output_dir:
            messagebox.showerror("Error", "Please add PDP links and select an output directory.")
            return
        root.destroy()

    root = tk.Tk()
    root.title("🧬 Amazon PDP Scraper")
    root.geometry("620x420")

    tk.Label(root, text="🔗 Enter Amazon PDP Links:").pack(pady=(10, 2))
    link_entry = tk.Entry(root, width=65)
    link_entry.pack()
    tk.Button(root, text="➕ Add Link", command=add_link).pack(pady=4)
    links_listbox = tk.Listbox(root, width=80, height=6)
    links_listbox.pack()

    tk.Button(root, text="📁 Choose Output Directory", command=browse_dir).pack(pady=8)
    dir_label = tk.Label(root, text="")
    dir_label.pack()

    tk.Button(root, text="🚀 Start PDP Scraping", command=start_scraping).pack(pady=15)
    root.mainloop()

# === PDP Scraper ===
def scrape_pdps():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        extracted_data = []

        for url in pdp_links:
            try:
                print(f"🔍 Scraping: {url}")
                page = context.new_page()
                page.goto(url, timeout=60000)
                page.wait_for_timeout(3000)

                pdp_info = extract_pdp_data(page)
                pdp_info["Product URL"] = url
                pdp_info["Date of Extraction"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                extracted_data.append(pdp_info)

                page.close()
                print("✅ Done")
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")

        file_path = os.path.join(output_dir, "amazon_pdp_data.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=2)
        print(f"\n🧾 Scraping complete. Saved to: {file_path}")
        browser.close()

# === Main Execution ===
if __name__ == "__main__":
    start_gui()
    scrape_pdps()
