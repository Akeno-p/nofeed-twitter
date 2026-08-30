"""
X APIへ実際にリクエストを送る関数をまとめたモジュール。
定数やエンドポイントURLは common/x_api.py に置く。
"""

import requests

from common.x_api import (
    TWITTER_GET_TWEET_ENDPOINT,
    TWITTER_MEDIA_ENDPOINT,
    TWITTER_SEARCH_RECENT_ENDPOINT,
    TWITTER_TWEET_ENDPOINT,
    TWITTER_USER_TWEETS_ENDPOINT,
    TWITTER_USERS_ENDPOINT,
)


def post_media_request(request, image):
    """画像をアップロードするリクエスト"""
    image.seek(0)
    post_media_response = requests.post(
        TWITTER_MEDIA_ENDPOINT,
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        files={"media": image},
        data={"media_category": "tweet_image"},
    )
    return post_media_response
