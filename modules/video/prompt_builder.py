#!/usr/bin/env python3

import os
import requests
from typing import Dict, Optional

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def call_deepseek_api(prompt: str, model: str = "deepseek-v4-flash") -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
    except requests.exceptions.RequestException as e:
        print(f"Error calling DeepSeek API: {e}")
        return None


def generate_ugc_prompt(product_info: Dict) -> str:
    prompt = f"Create a detailed UGC prompt for product: {product_info}"
    return call_deepseek_api(prompt, model="deepseek-v4-flash")


def generate_product_review_prompt(product_info: Dict) -> str:
    prompt = f"Generate a review prompt for product: {product_info}"
    return call_deepseek_api(prompt, model="deepseek-v4-flash")