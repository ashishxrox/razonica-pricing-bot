import sys
import asyncio
import nest_asyncio
import streamlit as st
import json
import datetime
import random
from playwright.async_api import async_playwright

# Fix for Windows subprocess event loop issue with Playwright + Streamlit
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

nest_asyncio.apply()

HEADERS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
]

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
            "Product Name": product_name,
            "Product Details": parsed_details,
            "Size & Fit": size_fit,
            "Material & Care": material_care,
            "Offer Details": best_price,
            "Price (INR)": price,
            "Original Price (INR)": original_price,
            "Discount": discount,
            **specs,
            "Date of Extraction": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {"error": f"Failed to extract data: {str(e)}"}

async def run_pdp_scraper(pdp_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        user_agent = random.choice(HEADERS_LIST)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=user_agent,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = await context.new_page()
        result = await extract_pdp_data(page, pdp_url)
        await browser.close()
        return result

# --- Streamlit UI ---
st.title("🛍️ Myntra PDP Scraper")

with st.form("pdp_scraper_form"):
    pdp_url = st.text_input("Enter the Myntra Product Page URL")
    submitted = st.form_submit_button("Scrape Product Page")

if submitted:
    if not pdp_url.strip():
        st.error("Please enter a valid product URL.")
    else:
        st.info("🔍 Scraping product data...")
        data = asyncio.get_event_loop().run_until_complete(run_pdp_scraper(pdp_url.strip()))

        if "error" not in data:
            st.success("✅ Scraping complete.")
            st.json(data)
            st.download_button(
                label="Download JSON",
                data=json.dumps(data, indent=2),
                file_name="myntra_pdp_data.json",
                mime="application/json"
            )
        else:
            st.error(data["error"])
