# scrapers/flipkart_scraper.py

import asyncio
import os
import json
import csv
import random
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime as dt
from playwright.async_api import async_playwright

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"},
]

# ----------------------------- LISTING SCRAPER -----------------------------

async def scrape_flipkart_link(page, base_url, max_products):
    data = []
    page_num = 1
    while len(data) < max_products:
        url = f"{base_url}&page={page_num}"
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("[data-id]", timeout=20000)
            await asyncio.sleep(random.uniform(2.5, 4.5))
        except Exception:
            break

        products = await page.locator("[data-id]").all()
        for product in products:
            if len(data) >= max_products:
                break
            try:
                data_id = await product.get_attribute("data-id") or "N/A"
                container = product.locator('div._1sdMkc.LFEi7Z')
                if not await container.is_visible():
                    continue

                brand_name = await container.locator('div.hCKiGj div.syl9yP').text_content() or "N/A"
                name_element = container.locator('div.hCKiGj a.WKTcLC')
                product_name = await name_element.text_content() if await name_element.is_visible() else "N/A"
                product_url = "https://www.flipkart.com" + (await name_element.get_attribute("href") or "#") if product_name != "N/A" else "N/A"

                item = {
                    "Data ID": data_id,
                    "Brand Name": brand_name.strip(),
                    "Product Name": product_name.strip(),
                    "Product URL": product_url,
                }
                data.append(item)

            except Exception:
                continue
        page_num += 1
    return data


async def run_listing_scraper(keywords, products_per_keyword):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        all_data = []
        for keyword in keywords:
            search_query = keyword.replace(' ', '+')
            search_url = f"https://www.flipkart.com/search?q={search_query}"
            print(f"🔍 Scraping listings for keyword: {keyword}")
            data = await scrape_flipkart_link(page, search_url, max_products=products_per_keyword)
            all_data.extend(data)
            print(f"➡️ Found {len(data)} products for '{keyword}'.")

        await browser.close()
        return all_data

# ----------------------------- PDP SCRAPER -----------------------------

def extract_pdp_data(soup, url):
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
            "Seller Name": seller.text.strip() if seller else None,
            "Seller Rating": seller_rating.text.strip() if seller_rating else None,
            "Specifications": specs,
            "Description Cards": descriptions,
            "All Reviews Summary": review_summary,
            "All Reviews Link": review_link,
            "Date of Extraction": dt.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception:
        return None


def run_pdp_scraper(urls):
    scraped_data = []
    for idx, url in enumerate(urls):
        headers = random.choice(HEADERS_LIST)
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            data = extract_pdp_data(soup, url)
            if data:
                scraped_data.append(data)
            if (idx + 1) % 10 == 0:
                print(f"✅ Scraped {idx+1}/{len(urls)} PDPs")
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            continue
    return scraped_data

# ----------------------------- Unified Scraper Function -----------------------------

async def scrape(keywords, limit_per_keyword=100, output_dir=None):
    listing_data = await run_listing_scraper(keywords, limit_per_keyword)
    product_urls = list(set([
        item["Product URL"] for item in listing_data
        if item.get("Product URL") and item["Product URL"] != "N/A"
    ]))

    print(f"🔍 Found {len(product_urls)} product URLs. Starting PDP scrape...")
    pdp_data = run_pdp_scraper(product_urls)

    if output_dir:
        json_path = os.path.join(output_dir, "flipkart_combined_data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pdp_data, f, indent=4)

        csv_path = os.path.join(output_dir, "flipkart_combined_data.csv")
        if pdp_data:
            with open(csv_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=pdp_data[0].keys())
                writer.writeheader()
                writer.writerows(pdp_data)

    return pdp_data
