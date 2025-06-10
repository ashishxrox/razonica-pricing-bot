import os
import json
import numpy as np
import pandas as pd
import sys
import requests
import pprint
import asyncio
import nest_asyncio
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from playwright.sync_api import sync_playwright

from utils.amazon_scraper import extract_pdp_data
from utils.flipkart_scraper import extract_flipkart_pdp_data
from utils.myntra_scraper import run_myntra_pdp_scraper
from data_processors.flipkart_data_processor import preprocess_flipkart_data
from utils.scraper_manager import ScraperManager
from utils.normalize import normalize_product_data
from utils.data_preprocessor import preprocess_product_data, generate_embeddings, build_embeddings_json



# Patch event loop for Streamlit
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
nest_asyncio.apply()

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="🛒 Product Data Scraper & Pricing Bot", page_icon="💸")
st.title("🛒 E-Commerce Product Data Scraper + 🧠 Pricing Recommendation")

def load_embeddings():
    if "in_memory_json" in st.session_state and st.session_state.in_memory_json:
        # Use embeddings from in-memory state
        data = st.session_state.in_memory_json
        embeddings = np.array([item["embedding"] for item in data])
        metadata = [item["metadata"] for item in data]
    else:
        return None

    return embeddings, metadata

# Load embeddings (will prefer in-memory, fallback to file)


def embed_text(text):
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=[text]
    )
    embedding = response.data[0].embedding
    return np.array(embedding)

def find_similar_products(new_embedding, embeddings, metadata, top_n=5):
    similarities = cosine_similarity([new_embedding], embeddings)[0]
    top_indices = similarities.argsort()[-top_n:][::-1]
    top_products = [(metadata[i], similarities[i]) for i in top_indices]
    return top_products

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

def scrape_amazon_product(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        data = extract_pdp_data(page)
        browser.close()
    return data

def scrape_flipkart_product(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    return extract_flipkart_pdp_data(soup, url)

def generate_summary_paragraph(data):
    def safe_get(field, key, default=""):
        value = data.get(field, "")
        if isinstance(value, dict):
            return value.get(key, default)
        elif isinstance(value, str):
            return value
        return default
    brand = safe_get("Brand Snapshot", "Brand Name", "Unknown Brand")
    summary = [f"**Brand:** {brand}"]
    additional_details = data.get("Additional Details", {})
    if isinstance(additional_details, dict) and additional_details:
        key_info = [f"{k}: {v}" for k, v in additional_details.items()]
        summary.append(f"**Additional Details:** {', '.join(key_info)}")
    return "\n\n".join(summary)

def construct_context(product_summary, top_products):
    context = (
        "You are a pricing expert. Please recommend a price range and discount "
        "for the product below using similar products for reference.\n\n"
        "**Product Summary:**\n"
        f"{product_summary}\n\n"
        "Top similar products:\n"
    )
    for i, (meta, sim) in enumerate(top_products, 1):
        context += (
            f"\n#{i} (Similarity: {sim:.2f}):\n"
            f"- Name: {meta.get('Product Name', 'N/A')}\n"
            f"- Price: ₹{meta.get('Price (INR)', 'N/A')}\n"
            f"- Discount: {meta.get('Discount', 'N/A')}\n"
        )
    context += "\n\nPlease format your answer as:\n"
    context += "**Product Title**: ...\n**Suggested Price Range**: ₹XXXX - ₹XXXX\n**Discount**: XX%\n**Offer Framing**: ...\n**Supporting Logic**: ..."
    return context

# ================================
# Streamlit App
# ================================
# st.title("Unified Product Scraper")

# st.title("🛒 E-commerce Product Scraper & Recommendation Engine")

# -------------------------
# PART 1: KEYWORD-BASED SCRAPING
# -------------------------
# st.header("🔍 Keyword-Based Scraping")
keywords = st.text_input("Keywords (comma-separated)").split(",")
platforms = st.multiselect("Platforms", ["ajio", "myntra", "amazon", "flipkart"])
limit = st.number_input("Products per keyword", min_value=1, max_value=100, value=5)

if "in_memory_json" not in st.session_state:
    st.session_state.in_memory_json = []

if st.button("Start Keyword Scraping"):
    manager = ScraperManager()
    results = asyncio.run(manager.run_all(platforms, [k.strip() for k in keywords if k.strip()], limit))
    for platform, items in results.items():
        st.subheader(platform.capitalize())
        data_list = []
        for item in items:
            product_url = item.get("product_url", "")
            normalized_item = normalize_product_data(item, product_url)
            data_list.append(normalized_item)
            # print("***This is Scrapped Data***")
            # print(normalized_item["Discount"])
        # print(data_list)
        df = pd.DataFrame(data_list)
        preprocessed_df = preprocess_product_data(df)

        st.write(f"Products Scraped from {platform}:")
        st.dataframe(preprocessed_df)

        # Make sure embeddings are generated and appended to the dataframe
        preprocessed_df = generate_embeddings(preprocessed_df)

        embeddings_json = build_embeddings_json(preprocessed_df)
        st.session_state.in_memory_json.extend(embeddings_json)

    st.success("Keyword-based scraping completed successfully!")

# -------------------------
# PART 2: URL-BASED SCRAPING
# -------------------------
# st.header("🔗 URL-Based Scraping & Recommendations")
num_urls = 5
product_urls = []

for i in range(num_urls):
    url = st.text_input(f"Product URL {i+1}", placeholder="https://www.amazon.in/...")
    if url.strip():
        product_urls.append(url.strip())

if st.button("Fetch Data & Get Recommendations"):
    if not product_urls:
        st.warning("Please enter at least one valid product URL.")
    elif not st.session_state.in_memory_json:
        st.warning("Please run keyword-based scraping first to generate embeddings.")
    else:
        embeddings, metadata = load_embeddings()
        print(metadata)
        all_data = []
        with st.spinner("Scraping data..."):
            for idx, url in enumerate(product_urls, 1):
                website = determine_website(url)
                try:
                    st.info(f"Processing URL {idx} of {len(product_urls)}")
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
                        data = asyncio.get_event_loop().run_until_complete(extract_pdp_details(url))
                        data["Source URL"] = url
                        all_data.append(data)
                    else:
                        st.warning(f"Unsupported website for URL: {url}")
                except Exception as e:
                    st.error(f"Failed to scrape {url}: {e}")

        if all_data:
            df = pd.DataFrame(all_data)
            st.success("Product data scraped successfully!")
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name='product_data.csv',
                mime='text/csv'
            )

            st.subheader("📄 Summary & Pricing Recommendations:")
            for idx, data in enumerate(all_data, 1):
                st.markdown(f"## 🔎 Product {idx}")
                summary_paragraph = generate_summary_paragraph(data)
                st.markdown(summary_paragraph)

                with st.spinner("Generating embedding and retrieving similar products..."):
                    new_embedding = embed_text(summary_paragraph)
                    top_products = find_similar_products(new_embedding, embeddings, metadata, top_n=5)

                st.markdown("### 📝 Top 5 Similar Products:")
                for i, (meta, sim) in enumerate(top_products, 1):
                    st.markdown(f"**#{i} (Similarity: {sim:.2f})**")
                    st.markdown(f"- **Product Name:** {meta.get('Product Name', 'N/A')}")
                    st.markdown(f"- **Price:** {meta.get('Price (INR)', 'N/A')}")
                    st.markdown(f"- **Discount:** {meta.get('Discount', 'N/A')}")
                    st.markdown(f"- **Rating:** {meta.get('Rating', 'N/A')}")
                    st.markdown(f"- **Rating Count:** {meta.get('Rating Count', 'N/A')}")
                    # Add Product URL if available
                    product_url = meta.get('Product URL', '')
                    if product_url:
                        st.markdown(f"- **Product URL:** [Link]({product_url})")
                    else:
                        st.markdown(f"- **Product URL:** N/A")
                    st.markdown("---")

                with st.spinner("Querying GPT-4o for pricing recommendation..."):
                    context = construct_context(summary_paragraph, top_products)
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": context}
                        ]
                    )
                    answer = response.choices[0].message.content
                    st.markdown(f"💡 **GPT-4o Recommendation:**")
                    st.write(answer)
                    st.markdown("---")
        else:
            st.error("No data was scraped from the provided URLs.")