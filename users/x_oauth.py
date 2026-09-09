import base64
import hashlib


def make_code_challenge(code_verifier: str) -> str:
    """PKCE 用に code_verifier を SHA-256 でハッシュ化し、base64url 形式で返す。"""

    code_challenge = code_verifier.encode()
    code_challenge = hashlib.sha256(code_challenge).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge)
    code_challenge = code_challenge.decode()
    code_challenge = code_challenge.rstrip("=")

    return code_challenge
