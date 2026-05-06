import os
from google import genai
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
for model in client.models.list():
    if "gemini" in model.name.lower():
        print(model.name)
