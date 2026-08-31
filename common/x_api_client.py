"""
X APIへ実際にリクエストを送る関数をまとめたモジュール。
定数やエンドポイントURLは common/x_api.py に置く。
"""

import requests
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from common.x_api import (
    TWITTER_GET_TWEET_ENDPOINT,
    TWITTER_MEDIA_ENDPOINT,
    TWITTER_SEARCH_RECENT_ENDPOINT,
    TWITTER_TWEET_ENDPOINT,
    TWITTER_USER_TWEETS_ENDPOINT,
    TWITTER_USERS_ENDPOINT,
)


def post_media_request(request: HttpRequest, image: UploadedFile) -> requests.Response:
    """画像をアップロードするリクエスト

    response.json() の結果は下記の形。
    {
        "data": {
            "id": "アップロードされたメディアのID",
            "media_key": "メディアのキー",
        }
    }
    """
    image.seek(0)
    response = requests.post(
        TWITTER_MEDIA_ENDPOINT,
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        files={"media": image},
        data={"media_category": "tweet_image"},
    )
    return response


def post_tweet_request(request: HttpRequest, payload: dict) -> requests.Response:
    """ツイートやリプライを投稿するリクエスト

    payload: ツイートやリプライするデータを下記の形で入れる。
    "reply"はリプライの時、"media"は画像をつけるときだけ入れる。
    {
        "text": 本文,
        "reply": {"in_reply_to_tweet_id": リプライ先のツイートID},
        "media": {"media_ids": [メディアID, ...]}
    }

    response.json() の結果は下記の形。
    {
        "data": {
            "id": "投稿されたツイート or リプライ ID",
            "text": "本文"
        }
    }
    """
    response = requests.post(
        TWITTER_TWEET_ENDPOINT,
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        json=payload,
    )
    return response
