# scrapers/ajio_scraper.py

import asyncio
import random
import datetime
import urllib.parse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

HEADERS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
]

def get_ajio_urls(keywords: list[str]) -> list[str]:
    return [f"https://www.ajio.com/find/{urllib.parse.quote_plus(kw)}" for kw in keywords]

async def safe_text(locator, timeout=1500):
    try:
        text = await locator.text_content(timeout=timeout)
        return text.strip() if text else "N/A"
    except:
        return "N/A"

async def extract_product_details(product, index):
    try:
        data_id = await product.get_attribute("data-id") or f"AJIO_{index + 1}"
        brand_name = await safe_text(product.locator('.brand'))
        product_name = await safe_text(product.locator('.nameCls'))
        rating = await safe_text(product.locator('._1gIWf ._3I65V'))
        rating_count = await safe_text(product.locator('p[aria-label*="|"]'))
        price = await safe_text(product.locator('.price strong'))
        original_price = await safe_text(product.locator('.orginal-price'))
        discount = await safe_text(product.locator('.discount'))
        try:
            bestseller = "Yes" if await product.locator('.exclusive-new').is_visible(timeout=1000) else "No"
        except:
            bestseller = "No"
        product_url_raw = await product.locator("a").get_attribute("href")
        product_url = f"https://www.ajio.com{product_url_raw}" if product_url_raw and product_url_raw.startswith("/") else product_url_raw or "N/A"

        return {
            "Data ID": data_id,
            "Brand Name": brand_name,
            "Product Name": product_name,
            "Product URL": product_url,
            "Rating": rating,
            "Rating Count": rating_count,
            "Price": price,
            "Original Price": original_price,
            "Discount": discount,
            "Bestseller": bestseller,
            "Date of Extraction": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        print(f"⚠️ Error extracting product #{index + 1}: {e}")
        return None

async def scrape_ajio_from_link(page, url, product_limit):
    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    await page.wait_for_selector("#products", timeout=20000)

    all_data = []
    scroll_y, last_count, scroll_attempts = 0, 0, 0

    while len(all_data) < product_limit and scroll_attempts < 2:
        await asyncio.sleep(1)
        products = await page.locator('#products .item').all()
        new_products = products[last_count:]
        if not new_products:
            scroll_attempts += 1
            break

        tasks = [extract_product_details(p, i + last_count) for i, p in enumerate(new_products)]
        batch = await asyncio.gather(*tasks)
        all_data.extend(filter(None, batch))
        last_count = len(products)
        scroll_y += 2500
        await page.evaluate(f"window.scrollTo(0, {scroll_y})")

    return all_data[:product_limit]

async def extract_pdp_details(page, product_url, index):
    try:
        await page.goto(product_url, timeout=60000)
        await page.wait_for_selector(".prod-container", timeout=10000)

        sizes = [await s.locator("span").text_content() for s in await page.locator(".size-variant-item.size-instock").all()]
        sizes = [s.strip() for s in sizes if s]

        details = [await d.text_content() for d in await page.locator("section.prod-desc ul.prod-list li.detail-list").all()]
        details = [d.strip() for d in details if d]

        structured_data = {}
        for item in await page.locator("section.prod-desc ul.prod-list li div.mandatory-list").all():
            try:
                label = await item.locator("div.info-label").text_content()
                value = await item.locator("div.title").text_content()
                if label and value:
                    structured_data[label.strip()] = value.strip()
            except:
                continue

        return {
            "Product URL": product_url,
            "Sizes Available": ", ".join(sizes) if sizes else "N/A",
            "Product Details": " | ".join(details) if details else "N/A",
            **structured_data,
            "Date of Extraction": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        print(f"⚠️ PDP Error {index + 1}: {e}")
        return {"Product URL": product_url, "Error": str(e)}

# 🧠 MAIN EXPORTABLE FUNCTION
async def scrape(keywords: list[str], max_products: int = 10) -> list[dict]:
    urls = get_ajio_urls(keywords)
    all_listing_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=random.choice(HEADERS_LIST))

        for url in urls:
            page = await context.new_page()
            products = await scrape_ajio_from_link(page, url, max_products)
            all_listing_data.extend(products)
            await page.close()

        pdp_page = await context.new_page()
        pdp_results = []
        for idx, product in enumerate(all_listing_data):
            pdp = await extract_pdp_details(pdp_page, product["Product URL"], idx)
            pdp_results.append(pdp)
        await pdp_page.close()

        await browser.close()

    # Merge listings + PDP by URL
    pdp_map = {p["Product URL"]: p for p in pdp_results}
    merged = []
    seen = set()
    for item in all_listing_data:
        url = item["Product URL"]
        if url not in seen:
            item.update(pdp_map.get(url, {}))
            merged.append(item)
            seen.add(url)

    return merged
