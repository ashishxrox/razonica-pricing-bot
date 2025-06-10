# scraper.py

import requests
from bs4 import BeautifulSoup
import re
import uuid
import pandas as pd
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/113.0.0.0 Safari/537.36"
}

def get_amazon_product_data(url):
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Data extraction logic
    try:
        brand_name = soup.find('a', id='bylineInfo').get_text(strip=True)
    except:
        brand_name = ''

    try:
        product_name = soup.find('span', id='productTitle').get_text(strip=True)
    except:
        product_name = ''

    try:
        rating = soup.find('span', {'class': 'a-icon-alt'}).get_text(strip=True)
    except:
        rating = ''

    try:
        rating_count = soup.find('span', id='acrCustomerReviewText').get_text(strip=True)
    except:
        rating_count = ''

    try:
        price = soup.find('span', {'class': 'a-price-whole'}).get_text(strip=True).replace(',', '')
        price = '₹' + price
    except:
        price = ''

    try:
        original_price = soup.find('span', {'class': 'a-text-price'}).get_text(strip=True)
    except:
        original_price = ''

    try:
        discount = soup.find('span', {'class': 'a-size-base a-color-price'}).get_text(strip=True)
    except:
        discount = ''

    badge = ''  # badge scraping can be added if needed

    date_of_extraction = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Sample dummy data for other fields
    product_details = {'Material composition': 'PURE COTTON', 'Length': 'Knee Length'}
    about_this_item = {'Fabric Info': 'Cotton', 'Color Info': 'Red'}
    all_bullet_points = ['Point 1', 'Point 2', 'Point 3']
    additional_details = {'Country of Origin': 'India'}
    brand_snapshot = {'Brand Name': brand_name}
    product_and_seller_details = {}
    product_description = 'Sample product description'

    data_id = str(uuid.uuid4())

    row = {
        'Data ID': data_id,
        'Product URL': url,
        'Brand Name': brand_name,
        'Product Name': product_name,
        'Rating': rating,
        'Rating Count': rating_count,
        'Price (INR)': price,
        'Original Price (INR)': original_price,
        'Discount': discount,
        'Badge': badge,
        'Date of Extraction': date_of_extraction,
        'Product Details': product_details,
        'About This Item': about_this_item,
        'All Bullet Points': all_bullet_points,
        'Additional Details': additional_details,
        'Brand Snapshot': brand_snapshot,
        'Product and Seller Details': product_and_seller_details,
        'Product Description': product_description
    }

    return row
