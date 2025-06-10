import streamlit as st
import pandas as pd
import requests
import sys
import asyncio
import nest_asyncio
from bs4 import BeautifulSoup
from datetime import datetime as dt
from utils.amazon_scraper import extract_pdp_data as extract_amazon_data
from utils.myntra_scraper import run_myntra_pdp_scraper
from utils.flipkart_scraper import extract_flipkart_pdp_data
from utils.ajio_scraper import extract_ajio_pdp_details
from data_processors.flipkart_data_processor import preprocess_flipkart_data
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

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



st.set_page_config(page_title="Product Data Scraper", page_icon="🔍")

st.title("🛒 E-Commerce Product Data Scraper")

st.markdown("""
Enter up to **5 product URLs** from e-commerce sites (Amazon.in, Myntra.com) to fetch product details.
""")

# Display up to 5 input boxes
num_urls = 5
product_urls = []
for i in range(num_urls):
    url = st.text_input(f"Product URL {i+1}", placeholder="https://www.amazon.in/...")
    if url.strip():
        product_urls.append(url.strip())

def scrape_amazon_product(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        data = extract_amazon_data(page)
        browser.close()
    return data

def scrape_flipkart_product(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    return extract_flipkart_pdp_data(soup, url)


# AJIO scraper function using Playwright
async def scrape_ajio_product(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        await page.wait_for_selector(".prod-container", timeout=10000)
        data = await extract_ajio_pdp_data(page, url)
        await browser.close()
        return data


def determine_website(url):
    if "amazon" in url.lower():
        return "amazon"
    elif "myntra" in url.lower():
        return "myntra"
    elif "flipkart" in url.lower():
        return "flipkart"
    elif "ajio" in url.lower():
        return "ajio"
    else:
        return "unsupported"

def generate_summary_paragraph(data):
    summary = []
    for key, value in data.items():
        summary.append(f"**{key}:** {value}")
    return "\n\n".join(summary)

if st.button("Fetch Product Data"):
    if product_urls:
        all_data = []
        with st.spinner("Scraping data..."):
            for idx, url in enumerate(product_urls, 1):
                website = determine_website(url)
                st.info(f"Processing URL {idx} of {len(product_urls)}")
                try:
                    if website == "amazon":
                        data = scrape_amazon_product(url)
                        data["Source URL"] = url
                        all_data.append(data)
                    elif website == "flipkart":
                        data = preprocess_flipkart_data(scrape_flipkart_product(url))
                        data["Source URL"] = url
                        all_data.append(data)
                    elif website == "myntra":
                        data = asyncio.get_event_loop().run_until_complete(run_myntra_pdp_scraper(url))
                        data["Source URL"] = url
                        all_data.append(data)
                    elif website == "ajio":
                        data = asyncio.get_event_loop().run_until_complete(extract_ajio_pdp_details(url))
                        data["Source URL"] = url
                        all_data.append(data)
                    else:
                        st.warning(f"Unsupported website for URL: {url}")
                except Exception as e:
                    st.error(f"Failed to scrape {url}: {e}")

        if all_data:
            df = pd.DataFrame(all_data)
            print(all_data)
            st.success("Product data fetched successfully!")
            st.dataframe(df)

            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name='product_data.csv',
                mime='text/csv'
            )

            st.subheader("📄 Summary of Scraped Data:")
            for idx, data in enumerate(all_data, 1):
                st.markdown(f"### Product {idx}")
                summary_paragraph = generate_summary_paragraph(data)
                st.markdown(summary_paragraph)
        else:
            st.error("No data was scraped from the provided URLs.")
    else:
        st.warning("Please enter at least one valid product URL.")
