import streamlit as st
import asyncio
from scraper_manager import ScraperManager

st.title("Unified Product Scraper")

keywords = st.text_input("Keywords (comma-separated)").split(",")
platforms = st.multiselect("Platforms", ["ajio", "myntra", "amazon", "flipkart"])
limit = st.number_input("Products per keyword", min_value=1, max_value=100, value=5)

if st.button("Start Scraping"):
    manager = ScraperManager()
    results = asyncio.run(manager.run_all(platforms, [k.strip() for k in keywords if k.strip()], limit))
    for platform, items in results.items():
        st.subheader(platform.capitalize())
        st.write(items)
