import asyncio
import os
import random
import json
import re
import datetime
from playwright.async_api import async_playwright

async def extract_product_data(product):
    try:
        data_id = await product.get_attribute("id")
        a_tag = product.locator('a[data-refreshpage="true"]')
        product_url = "N/A"
        if await a_tag.count() > 0:
            href = await a_tag.get_attribute("href")
            if href:
                product_url = f"https://www.myntra.com/{href}"
                if not data_id:
                    match = re.search(r'/(\d+)/buy$', href)
                    if match:
                        data_id = match.group(1)

        if not data_id:
            # Skipping product with missing ID
            return None

        async def get_text(selector):
            try:
                element = product.locator(selector)
                return await element.inner_text() if await element.count() > 0 else "N/A"
            except:
                return "N/A"

        brand_name = await get_text("h3")
        product_name = await get_text("h4.product-product")

        rating_element = product.locator(".product-ratingsContainer span").first
        rating = await rating_element.inner_text() if await rating_element.count() > 0 else "N/A"

        rating_count_element = product.locator(".product-ratingsContainer .product-ratingsCount")
        if await rating_count_element.count() > 0:
            raw_text = await rating_count_element.inner_text()
            rating_count = re.sub(r"[^\d]", "", raw_text)
        else:
            rating_count = "N/A"

        return {
            "Data ID": data_id,
            "Brand Name": brand_name,
            "Product Name": product_name,
            "Product URL": product_url,
            "Rating": rating,
            "Rating Count": rating_count,
            "Date of Extraction": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        # Log or handle extraction error
        return None

async def scrape_myntra_listing(page, base_url, product_limit):
    all_data, seen_ids = [], set()
    page_num, extracted = 1, 0
    prev_ids = set()

    while extracted < product_limit:
        url = f"{base_url}{'&' if '?' in base_url else '?'}p={page_num}"
        # print(f"Scraping listing page: {url} (Page {page_num})")

        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("#desktopSearchResults .results-base li", timeout=15000)
            await asyncio.sleep(random.uniform(2.5, 4))
        except Exception:
            break

        products = await page.locator("#desktopSearchResults .results-base li").all()
        if not products:
            break

        results = await asyncio.gather(*(extract_product_data(p) for p in products))
        current_ids = set()

        for item in results:
            if item and item["Data ID"] not in seen_ids and extracted < product_limit:
                seen_ids.add(item["Data ID"])
                current_ids.add(item["Data ID"])
                all_data.append(item)
                extracted += 1

        if not current_ids or current_ids == prev_ids:
            break

        prev_ids = current_ids
        page_num += 1

    return all_data

async def extract_pdp_data(page, url):
    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_selector("#mountRoot", timeout=20000)
        await asyncio.sleep(2)

        async def safe_text(selector):
            try:
                el = page.locator(selector)
                return await el.first.inner_text() if await el.count() > 0 else ""
            except:
                return ""

        product_name = await safe_text("h1.pdp-name")
        raw_details_text = await safe_text("p.pdp-product-description-content")
        parsed_details = [raw_details_text] if raw_details_text else []

        material_care = size_fit = ""
        desc_blocks = await page.locator("div.pdp-sizeFitDesc").all()
        for block in desc_blocks:
            try:
                title = await block.locator("h4.pdp-sizeFitDescTitle").text_content()
                content = await block.locator("p.pdp-sizeFitDescContent").text_content()
                if "Material & Care" in title:
                    material_care = content
                elif "Size & Fit" in title:
                    size_fit = content
            except:
                continue

        try:
            see_more_button = page.locator("div.index-showMoreText")
            if await see_more_button.count() > 0:
                await see_more_button.click()
                await asyncio.sleep(1)
        except:
            pass

        specs = {}
        spec_rows = await page.locator("div.index-tableContainer > div.index-row").all()
        for row in spec_rows:
            try:
                key = await row.locator("div.index-rowKey").text_content()
                value = await row.locator("div.index-rowValue").text_content()
                if key and value:
                    specs[key.strip()] = value.strip()
            except:
                continue

        best_price = ""
        try:
            offer_container = page.locator("div.pdp-offers-offer")
            if await offer_container.count() > 0:
                best_price = await offer_container.inner_text()
        except:
            pass

        price = await safe_text("span.pdp-price strong")
        original_price = await safe_text("span.pdp-mrp s")
        discount = await safe_text("span.pdp-discount")

        price = price.replace("Rs.", "₹").replace("₹", "").strip()
        price = f"₹{price}" if price else "N/A"

        original_price = original_price.replace("Rs.", "₹").replace("₹", "").strip()
        original_price = f"₹{original_price}" if original_price else "N/A"

        discount = discount.strip() if discount else "N/A"

        return {
            "Product URL": url,
            "Product Name (PDP)": product_name,
            "Product Details": parsed_details,
            "Size & Fit": size_fit,
            "Material & Care": material_care,
            "Offer Details": best_price,
            "Price (INR)": price,
            "Original Price (INR)": original_price,
            "Discount": discount,
            **specs
        }
    except Exception:
        return {}

async def scrape(keywords, products_per_keyword):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        all_listing_data = []

        for keyword in keywords:
            search_query = keyword.replace(" ", "+")
            search_url = f"https://www.myntra.com/{search_query}"
            # print(f"Searching keyword: {keyword}")
            data = await scrape_myntra_listing(page, search_url, products_per_keyword)
            all_listing_data.extend(data)

        if not all_listing_data:
            return []

        # Enrich with PDP data
        enriched_data = []
        for i, item in enumerate(all_listing_data):
            pdp = await extract_pdp_data(page, item["Product URL"])
            item.update(pdp)
            enriched_data.append(item)
            # Small delay to avoid overload
            await asyncio.sleep(1)

        await browser.close()
        return enriched_data
