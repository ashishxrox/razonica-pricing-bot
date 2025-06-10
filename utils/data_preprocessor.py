import os
import re
import datetime
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
import openai

# Step 6: Load API Key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY not found in environment variables.")
openai.api_key = openai_api_key
# print("Loaded API Key:", openai_api_key[:4] + "****")

# ====================
# Preprocessing Steps
# ====================

TEXT_COLUMNS = [
    'Brand Name', 'Product Name', 'Product Details', 'About This Item',
    'All Bullet Points', 'Additional Details', 
    'Brand Snapshot', 'Product Description'
]

NUM_COLUMNS = [
    'Rating', 'Rating Count', 'Price (INR)', 
    'Original Price (INR)'
    # 'Discount' removed from here to treat separately
]

METADATA_COLUMNS = [
    'Product URL',
    'Product Name',
    'Brand Name',
    'Rating',
    'Rating Count',
    'Price (INR)',
    'Original Price (INR)',
    'Discount'
]

def _clean_text(text):
    """
    Clean text by removing extra whitespace and trimming.
    """
    text = re.sub(r'\s+', ' ', str(text))
    return text.strip()

def preprocess_product_data(data: pd.DataFrame):
    """
    Preprocess the normalized product data:
    1. Drop unnecessary columns.
    2. Fill missing values.
    3. Clean text columns.
    """
    # Step 1: Drop unwanted columns
    columns_to_drop = ['Badge', 'Date of Extraction', 'Product and Seller Details']
    data = data.drop(columns=[col for col in columns_to_drop if col in data.columns], errors='ignore')

    # Step 2: Fill missing values and clean text columns
    for col in TEXT_COLUMNS:
        if col in data.columns:
            data[col] = data[col].fillna('').apply(_clean_text)

    # Step 3: Fill numeric columns except 'Discount'
    for col in NUM_COLUMNS:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

    # Step 4: Handle 'Discount' field separately
    if 'Discount' in data.columns:
        data['Discount'] = data['Discount'].apply(
            lambda x: 0 if pd.isna(x) else x
        )
        # We do not convert it to numeric here, just ensure missing are filled

    return data

# ====================
# Embedding Functions
# ====================

def concat_text(row):
    """
    Concatenate text columns into a single string for embedding.
    """
    texts = [str(row.get(col, "")) for col in TEXT_COLUMNS if pd.notna(row.get(col, ""))]
    return " ".join(texts)

def get_embedding(text, model="text-embedding-3-large"):
    """
    Get embedding from OpenAI API.
    """
    response = openai.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding

def generate_embeddings(data: pd.DataFrame):
    """
    Generate embeddings for all rows in the DataFrame.
    """
    data['combined_text'] = data.apply(concat_text, axis=1)

    embeddings = []
    for text in tqdm(data['combined_text'], desc="Generating Embeddings"):
        emb = get_embedding(text)
        embeddings.append(emb)

    data['embedding'] = embeddings
    return data

def build_embeddings_json(data: pd.DataFrame):
    """
    Build the in-memory JSON structure from the DataFrame.
    """
    output_data = []
    for _, row in data.iterrows():
        item = {
            'embedding': row['embedding'],
            'metadata': {col: row.get(col, "") for col in METADATA_COLUMNS},
            'createdAt': datetime.datetime.utcnow().isoformat() + 'Z'
        }
        output_data.append(item)
    return output_data
