import requests
from dotenv import load_dotenv

load_dotenv()

import os

CLIENT_ID = os.getenv("ML_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")

CODE = "TG-6a0dc65237f5e400017c49ec-174534805"

url = "https://api.mercadolibre.com/oauth/token"

payload = {
    "grant_type": "authorization_code",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": CODE,
    "redirect_uri": "https://mobile-sps.site/"
}

response = requests.post(url, data=payload)

print(response.json())