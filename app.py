import os
import json
import numpy as np
import pandas as pd
import sys
import requests
import asyncio
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from utils.amazon_scraper import extract_pdp_data
from utils.flipkart_scraper import extract_flipkart_pdp_data
# from utils.ajio_scraper import extract_ajio_pdp_details
from utils.myntra_scraper import run_myntra_pdp_scraper
from data_processors.flipkart_data_processor import preprocess_flipkart_data
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
import nest_asyncio

# Patch event loop for Streamlit
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
nest_asyncio.apply()


# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()


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

st.set_page_config(page_title="🛒 Product Data Scraper & Pricing Bot", page_icon="💸")

st.title("🛒 E-Commerce Product Data Scraper + 🧠 Pricing Recommendation")

st.markdown("""
Enter up to **5 product URLs** from an e-commerce site (e.g., Amazon.in) to fetch product details, generate a summary paragraph, and get pricing & discount recommendations.
""")

# --------------------- #
# Load Embeddings       #
# --------------------- #
@st.cache_data
def load_embeddings(json_file):
    with open(json_file, "r") as f:
        data = json.load(f)

    if isinstance(data, dict):
        embeddings = np.array([data["embedding"]])
        metadata = [data["metadata"]]
    elif isinstance(data, list):
        embeddings = np.array([item["embedding"] for item in data])
        metadata = [item["metadata"] for item in data]
    else:
        raise ValueError("Unexpected data format in embeddings file")

    return embeddings, metadata

# Load embeddings once
embeddings, metadata = load_embeddings("./product_embeddings/product_embeddings2.json")
# print(metadata)

# --------------------- #
# Embedding Functions   #
# --------------------- #
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

# --------------------- #
# Scraping & Summaries  #
# --------------------- #
def scrape_amazon_product(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        data = extract_pdp_data(page)
        browser.close()
    return data

def scrape_flipkart_product(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    return extract_flipkart_pdp_data(soup, url)



def generate_summary_paragraph(data):
    def safe_get(field, key, default=""):
        """
        Safely get nested value from data[field][key] if field is a dict,
        or return the string itself if field is a str (i.e., already flattened).
        """
        value = data.get(field, "")
        if isinstance(value, dict):
            return value.get(key, default)
        elif isinstance(value, str):
            return value  # assume it's already flattened and contains what we need
        return default

    summary = []

    brand = safe_get("Brand Snapshot", "Brand Name", "Unknown Brand")
    description = data.get("Product Description", "")

    # Extract About This Item fields (handling both dict and str)
    style = safe_get("About This Item", "Style Info")
    color = safe_get("About This Item", "Color Info")
    work = safe_get("About This Item", "Work/Design Info")
    occasion = safe_get("About This Item", "Occasion / Usage")

    summary.append(f"**Brand:** {brand}")

    # Additional Details (must be a dict to be meaningful)
    additional_details = data.get("Additional Details", {})
    if isinstance(additional_details, dict) and additional_details:
        key_info = [f"{key}: {value}" for key, value in additional_details.items()]
        summary.append(f"**Additional Details:** {', '.join(key_info)}")

    return "\n\n".join(summary)


# --------------------- #
# Determine Market Place#
# --------------------- #

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

# --------------------- #
# Pricing Prompt Builder#
# --------------------- #
def construct_context(product_summary, top_products):
    context = (
        "You are a pricing expert. Your task is to recommend an appropriate price and discount strategy "
        "for the following new product, based on similar products provided below. "
        "Use the given matched market examples to benchmark pricing, identify discount strategies, "
        "and recommend an optimal pricing range and discount framing.\n\n"
        
        "Please strictly follow this output format:\n\n   [**Write each of these pointers on a new line**]"
        "**Product Title**: (title)\n"
        "**Suggested Price Range**: ₹XXXX - ₹XXXX\n"
        "**Discount**: XX% (type, e.g., Flat or Up to)\n"
        "**Offer Framing Suggestion**: (a short, catchy line for marketing)\n"
        "**Supporting Logic**: (1-2 short and crisp sentences, explaining the recommendation and referencing the matched examples)\n\n"
        
        "New Product Summary:\n"
        f"{product_summary}\n\n"
        
        "Here are the top similar products:\n"
    )
    
    for i, (meta, sim) in enumerate(top_products, 1):
        context += f"\n#{i} (Similarity: {sim:.2f}):\n"
        context += f"- Product Name: {meta.get('Product Name', 'N/A')}\n"
        context += f"- Price: ₹{meta.get('Price (INR)', 'N/A')}\n"
        context += f"- Discount: {meta.get('Discount', 'N/A')}\n"
        context += f"- Material: {meta.get('Material', 'N/A')}\n"
        context += f"- Pattern: {meta.get('Pattern', 'N/A')}\n"
        context += f"- Style: {meta.get('Style', 'N/A')}\n"
        context += f"- Category: {meta.get('Category', 'N/A')}\n"
        context += f"- Rating: {meta.get('Rating', 'N/A')}\n"
        context += f"- Rating Count: {meta.get('Rating Count', 'N/A')}\n"
    
    context += (
        "\n\nPlease return only the structured recommendation as specified, "
        "followed by the supporting logic. Do not include any additional text or disclaimers."
    )
    
    return context



# --------------------- #
# Main UI               #
# --------------------- #
num_urls = 5
product_urls = []
for i in range(num_urls):
    url = st.text_input(f"Product URL {i+1}", placeholder="https://www.amazon.in/...")
    if url.strip():
        product_urls.append(url.strip())
if st.button("Fetch Data & Get Recommendations"):
    if product_urls:
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
            # st.dataframe(df)
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
    else:
        st.warning("Please enter at least one valid product URL.")