import hmac
import hashlib

def generate_challenge(user_id: str, secret_key: str):
    return hmac.new(secret_key.encode(), user_id.encode(), hashlib.sha256).hexdigest()