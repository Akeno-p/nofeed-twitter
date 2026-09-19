"""
X APIを使用するための定数やエンドポイントURLをまとめたモジュール。
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
# POST：画像のアップロード
TWITTER_MEDIA_ENDPOINT = "https://api.x.com/2/media/upload"
# GET：ツイート単体取得
TWITTER_GET_TWEET_ENDPOINT = "https://api.x.com/2/tweets/{tweet_id}"
# GET：ユーザーのツイート一覧取得
TWITTER_USER_TWEETS_ENDPOINT = "https://api.x.com/2/users/{user_id}/tweets"
# GET：ツイートを検索して取得(直近7日分のみ)
TWITTER_SEARCH_RECENT_ENDPOINT = "https://api.x.com/2/tweets/search/recent"
# GET：自分が参加しているDMを新しい順に取得(直近30日分のみ)
TWITTER_DM_EVENTS_ENDPOINT = "https://api.x.com/2/dm_events"

# ===== その他 =====

# リクエストのtimeout時間
TWITTER_API_TIMEOUT = (3.0, 10.0)

# 取得したトークンに持たせたい権限
TWITTER_AUTH_ALL_SCOPE = " ".join(  # noqa: FLY002
    [
        "tweet.read",
        "tweet.write",
        "tweet.moderate.write",
        "users.read",
        "users.email",
        "follows.read",
        "follows.write",
        "offline.access",
        "space.read",
        "mute.read",
        "mute.write",
        "like.read",
        "like.write",
        "list.read",
        "list.write",
        "block.read",
        "block.write",
        "bookmark.read",
        "bookmark.write",
        "dm.read",
        "dm.write",
        "media.write",
    ]
)
