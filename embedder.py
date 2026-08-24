import requests
import logging

API_URL = "http://localhost:1234/v1/embeddings"

def get_embedding(text):
    """
    Sends text to the local LM Studio embeddings endpoint and returns the float array.
    Fails gracefully if the server is unreachable.
    """
    try:
        payload = {
            "input": text,
            "model": "local-model"  # Typically ignored by LM Studio, but standard for OpenAI spec
        }
        # Increased timeout to allow for local model loading and slow inference
        response = requests.post(API_URL, json=payload, timeout=30.0)
        response.raise_for_status()
        
        data = response.json()
        return data['data'][0]['embedding']
        
    except requests.exceptions.RequestException as e:
        logging.error(f"LM Studio endpoint unreachable: {e}")
        return None