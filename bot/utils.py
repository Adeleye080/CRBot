import os
import time
import jwt
from dotenv import load_dotenv

load_dotenv()


APP_ID = os.getenv("APP_ID")
PRIVATE_KEY = os.getenv("PRIVATE_KEY").replace("\\n", "\n")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


def generate_jwt():
    """
    Generate GitHub JWT for authentication
    """
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 10 * 60,
        "iss": APP_ID
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def verify_webhook(req):
    signature = req.headers.get("X-Hub-Signature-256")
    computed_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        json.dumps(req.json).encode(),
        hashlib.sha256
    ).hexdigest()
    if signature != computed_signature:
        raise ValueError("Invalid signature")


def get_installation_access_token(installation_id):
    jwt_token = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()["token"]