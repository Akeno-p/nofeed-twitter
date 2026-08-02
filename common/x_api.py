"""
X APIを使用するための定数やエンドポイントURLをまとめたモジュール。
関数は common/utils.py に置く。
"""

import os

# OAuth クライアント認証情報
TWITTER_CLIENT_ID = os.environ["TWITTER_CLIENT_ID"]
TWITTER_CLIENT_SECRET = os.environ["TWITTER_CLIENT_SECRET"]

# リダイレクトuri
TWITTER_REDIRECT_URI = os.environ["TWITTER_REDIRECT_URI"]

# OAuth エンドポイント
TWITTER_AUTH_ENDPOINT = "https://x.com/i/oauth2/authorize"
TWITTER_TOKEN_ENDPOINT = "https://api.x.com/2/oauth2/token"

# APIエンドポイント
TWITTER_USERS_ME_ENDPOINT = "https://api.x.com/2/users/me"
