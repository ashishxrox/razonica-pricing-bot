import os
import json
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()

# Load embeddings from JSON
@st.cache_data
def load_embeddings(json_file):
    with open(json_file, "r") as f:
        data = json.load(f)

    if isinstance(data, dict):
        # Single embedding
        embeddings = np.array([data["embedding"]])
        metadata = [data["metadata"]]
    elif isinstance(data, list):
        # Multiple embeddings
        embeddings = np.array([item["embedding"] for item in data])
        metadata = [item["metadata"] for item in data]
    else:
        raise ValueError("Unexpected data format in embeddings file")

    return embeddings, metadata


# Function to embed new product text
def embed_text(text):
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=[text]
    )
    embedding = response.data[0].embedding
    return np.array(embedding)

# Find top N similar products
def find_similar_products(new_embedding, embeddings, metadata, top_n=5):
    similarities = cosine_similarity([new_embedding], embeddings)[0]
    top_indices = similarities.argsort()[-top_n:][::-1]
    top_products = [(metadata[i], similarities[i]) for i in top_indices]
    return top_products

# Construct the context for GPT-4o
def construct_context(user_input, top_products):
    context = "You are a pricing expert. Recommend an appropriate price and discount for the following new product based on similar products provided.\n\n"
    context += f"New Product Details:\n{user_input}\n\n"
    context += "Here are the top similar products:\n"
    for i, (meta, sim) in enumerate(top_products, 1):
        context += f"\n#{i} (Similarity: {sim:.2f}):\n"
        context += f"- Product Name: {meta.get('Product Name', 'N/A')}\n"
        context += f"- Price: {meta.get('Price (INR)', 'N/A')}\n"
        context += f"- Discount: {meta.get('Discount', 'N/A')}\n"
        context += f"- Rating: {meta.get('Rating', 'N/A')}\n"
        context += f"- Rating Count: {meta.get('Rating Count', 'N/A')}\n"
    context += "\nProvide your recommended price and discount for the new product, with a brief explanation."
    return context

# Streamlit UI
st.title("🛍️ Smart Price & Discount Recommendation Bot (RAG + GPT-4o)")

# Load embeddings
embeddings, metadata = load_embeddings("./product_embeddings/product_embeddings.json")

# Chat Input
user_input = st.text_area("Paste your product details (Name, Description, etc.)")

if st.button("Get Recommendation"):
    if user_input:
        with st.spinner("Generating embedding and retrieving similar products..."):
            new_embedding = embed_text(user_input)
            top_products = find_similar_products(new_embedding, embeddings, metadata, top_n=5)
        
        with st.spinner("Querying GPT-4o for a recommendation..."):
            context = construct_context(user_input, top_products)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": context}
                ]
            )
            answer = response.choices[0].message.content
            st.subheader("💡 GPT-4o Recommendation:")
            st.write(answer)

            st.subheader("🔎 Top Similar Products:")
            for i, (meta, sim) in enumerate(top_products, 1):
                st.write(f"**#{i}** | Similarity: {sim:.2f}")
                st.write(f"Product Name: {meta.get('Product Name', 'N/A')}")
                st.write(f"Price: {meta.get('Price (INR)', 'N/A')}")
                st.write(f"Discount: {meta.get('Discount', 'N/A')}")
                st.markdown("---")
    else:
        st.warning("Please enter product details.")
