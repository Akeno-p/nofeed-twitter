import base64
import io

import pyotp
import qrcode


def make_qrcode_b64(user_name: str, totp_secret: str) -> str:
    """TOTP の秘密鍵を認証アプリに登録するための QRコードを作り、base64で返す。

    戻り値は HTML に <img src="data:image/png;base64,{{ 戻り値 }}"> の形で埋め込める。
    """
    url = pyotp.TOTP(totp_secret).provisioning_uri(
        name=user_name, issuer_name="nofeed-twitter"
    )

    qrcode_img = qrcode.make(url)

    buffer = io.BytesIO()

    qrcode_img.save(buffer)
    qrcode_b64 = base64.b64encode(buffer.getvalue()).decode()

    return qrcode_b64
