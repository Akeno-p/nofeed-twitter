"""
X APIを使用するための定数やエンドポイントURLをまとめたモジュール。
関数は common/utils.py に置く。
"""

import os

# ====== OAuth クライアント認証情報 =====

TWITTER_CLIENT_ID = os.environ["TWITTER_CLIENT_ID"]
TWITTER_CLIENT_SECRET = os.environ["TWITTER_CLIENT_SECRET"]


# ===== リダイレクトuri =====

TWITTER_REDIRECT_URI = os.environ["TWITTER_REDIRECT_URI"]


# ===== OAuth エンドポイント =====

# GET：認証画面の表示
TWITTER_AUTH_ENDPOINT = "https://x.com/i/oauth2/authorize"
# POST：トークンの取得
TWITTER_TOKEN_ENDPOINT = "https://api.x.com/2/oauth2/token"


# ===== APIエンドポイント =====

# GET：自分のユーザー情報の取得
TWITTER_USERS_ME_ENDPOINT = "https://api.x.com/2/users/me"
# GET：ユーザー情報の取得
TWITTER_USERS_ENDPOINT = "https://api.x.com/2/users"
# POST：ツイート投稿
TWITTER_TWEET_ENDPOINT = "https://api.x.com/2/tweets"
# GET：ツイート単体取得
TWITTER_GET_TWEET_ENDPOINT = "https://api.x.com/2/tweets/{tweet_id}"
# GET：ユーザーのツイート一覧取得
TWITTER_USER_TWEETS_ENDPOINT = "https://api.x.com/2/users/{user_id}/tweets"
# GET：ツイートを検索して取得(直近7日分のみ)
TWITTER_SEARCH_RECENT_ENDPOINT = "https://api.x.com/2/tweets/search/recent"
