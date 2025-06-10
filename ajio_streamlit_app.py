import streamlit as st
import asyncio
import os
import json
import datetime
import random
import sys
from playwright.async_api import async_playwright
import nest_asyncio

# Patch event loop for Streamlit
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
nest_asyncio.apply()

# ----------------------------------------
# HEADERS / USER AGENTS
# ----------------------------------------
HEADERS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
]

# ----------------------------------------
# PDP SCRAPER FUNCTION
# ----------------------------------------
async def extract_pdp_details(product_url):
    try:
        async with async_playwright() as p:
            user_agent = random.choice(HEADERS_LIST)
            
            # Using WebKit browser to reduce chance of blocking
            browser = await p.webkit.launch(headless=False)
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="Asia/Kolkata",
            )
            page = await context.new_page()

            # Go to the product page
            await page.goto(product_url, timeout=30000)

            # Human-like wait & scroll
            await asyncio.sleep(random.uniform(2, 4))
            await page.mouse.move(200, 300)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(random.uniform(1, 2))

            # Wait for product container
            await page.wait_for_selector(".prod-container", timeout=10000)

            # Extract sizes
            sizes = [await s.locator("span").text_content() for s in await page.locator(".size-variant-item.size-instock").all()]
            sizes = [s.strip() for s in sizes if s]

            # Extract product details list
            details = [await d.text_content() for d in await page.locator("section.prod-desc ul.prod-list li.detail-list").all()]
            details = [d.strip() for d in details if d]

            # Extract structured data
            structured_data = {}
            for item in await page.locator("section.prod-desc ul.prod-list li div.mandatory-list").all():
                try:
                    label = await item.locator("div.info-label").text_content()
                    value = await item.locator("div.title").text_content()
                    if label and value:
                        structured_data[label.strip()] = value.strip()
                except:
                    continue

            await browser.close()

            return {
                "Product URL": product_url,
                "Sizes Available": ", ".join(sizes) if sizes else "N/A",
                "Product Details": " | ".join(details) if details else "N/A",
                **structured_data,
                "Date of Extraction": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    except Exception as e:
        return {"Product URL": product_url, "Error": str(e)}

# ----------------------------------------
# STREAMLIT UI
# ----------------------------------------
st.title("🛍️ Ajio PDP Scraper")

with st.form("pdp_scraper_form"):
    product_url = st.text_input("Enter Ajio Product Page URL (PDP)", placeholder="https://www.ajio.com/...")
    output_dir = st.text_input("Output Directory", value="ajio_pdp_output")
    submitted = st.form_submit_button("Scrape Product")

if submitted:
    if not product_url.strip():
        st.error("Please enter a valid Ajio product URL.")
    else:
        os.makedirs(output_dir, exist_ok=True)
        st.success("🔄 Scraping started...")

        data = asyncio.get_event_loop().run_until_complete(extract_pdp_details(product_url))

        file_path = os.path.join(output_dir, "ajio_pdp_data.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        st.success(f"✅ Scraping complete. Data saved to: `{file_path}`")
        st.download_button("Download JSON", data=json.dumps(data, indent=2), file_name="ajio_pdp_data.json", mime="application/json")
        st.write(data)
