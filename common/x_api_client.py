"""
X APIへ実際にリクエストを送る関数をまとめたモジュール。
定数やエンドポイントURLは common/x_api.py に置く。
"""

from typing import TypedDict

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


class TweetResponseData(TypedDict, total=False):
    """ツイートやリプライ1件分のデータの形
    get_tweet のresponseを .json().get("data")した時の形


    "id": "ツイートID",
    "text": "本文",
    "author_id": "投稿者のユーザーID",
    "created_at": "投稿時間(例：2025-08-02T10:30:00.000Z)",
    "conversation_id": "会話ID",
    "referenced_tweets": [{
        "type": "replied_to / quoted",
        "id": "参照先ツイートID"
    }],
    "attachments": {"media_keys":["media_keyのリスト"]}
    """

    id: str
    text: str
    author_id: str
    created_at: str
    conversation_id: str
    referenced_tweets: list[dict]
    attachments: dict


class MediaResponseData(TypedDict, total=False):
    """メディア1件分のデータの形
    get_tweet のresponseを .json().get("includes",{}).get("media",[])した時の形

    "media_key": "メディアキー",
    "type": "photo / video / animated_gif",
    "url": メディアのURL,
    "alt_text": "代替テキスト",
    "width": 横幅,
    "height": 縦幅,
    "duration_ms": 15000
    """

    media_key: str
    type: str
    url: str
    alt_text: str
    width: int
    height: int
    duration_ms: int


class XUserResponseData(TypedDict):
    """Xユーザー1件分のデータの形
    get_users のresponseを .json().get("data",[])した時の形

    "id": "ユーザーID",
    "name": "表示名",
    "username": "ユーザー名(@の後ろ)",
    "profile_image_url": "アイコン画像のURL"
    """

    id: str
    name: str
    username: str
    profile_image_url: str


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


def get_tweet(request: HttpRequest, tweet_id: str | int) -> requests.Response:
    """ツイートやリプライを１件取得するリクエスト

    response.json() の結果は下記の形。

    {
        "data": {
            "id": "ツイートID",
            "text": "本文",
            "author_id": "投稿者のユーザーID",
            "created_at": "投稿時間(例：2025-08-02T10:30:00.000Z)",
            "conversation_id": "会話ID",
            "edit_history_tweet_ids": ["ツイートIDのリスト"],
            "referenced_tweets": [{
                "type": "replied_to / quoted",
                "id": "参照先ツイートID"
            }],
            "attachments": {"media_keys":["media_keyのリスト"]}
        },
        "includes": {
            "media": [
                {
                "media_key": "メディアキー",
                "type": "photo / video / animated_gif",
                "url": メディアのURL,
                "alt_text": "代替テキスト",
                "width": 横幅,
                "height": 縦幅,
                "duration_ms": 15000
                }
            ]
        }
    }


    """
    response = requests.get(
        TWITTER_GET_TWEET_ENDPOINT.format(tweet_id=tweet_id),
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        params={
            "post.fields": "created_at,author_id,conversation_id,referenced_tweets,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "url,type,alt_text,width,height,duration_ms",
        },
    )

    return response


def get_all_tweets(
    request: HttpRequest, next_token: str | None = None
) -> requests.Response:
    """自分のツイートを一覧取得するリクエスト

    params: 取得条件を下記の形で入れる。
    "pagination_token" は2ページ目以降を取得するときだけ入れる。
    {
        "max_results": 1回で取得する件数(最大100),
        "post.fields": "取得するツイートのフィールド",
        "expansions": "attachments.media_keys",
        "media.fields": "取得するメディアのフィールド"
        "pagination_token": "前回レスポンスの meta.next_token"
    }

    response.json()の結果は下記の形
    {
        "data": [TweetResponseData],
        "includes": {"media":[MediaResponseData]}
        "meta": {
            "result_count: 取得できた件数",
            "next_token": "次のページがあるときだけ入る"
        }
    }
    """
    params = {
        "max_results": 100,
        "post.fields": "created_at,author_id,conversation_id,referenced_tweets,attachments",
        "expansions": "attachments.media_keys",
        "media.fields": "url,type,alt_text,width,height,duration_ms",
    }
    if next_token:
        params["pagination_token"] = next_token
    response = requests.get(
        TWITTER_USER_TWEETS_ENDPOINT.format(user_id=request.user.x_user_id),
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        params=params,
    )

    return response


def get_users(request: HttpRequest, user_ids: list[int]) -> requests.Response:
    """ユーザー情報を複数取得するリクエスト

    user_ids: 取得したいユーザーのIDのリスト。1回で最大100件まで。

    response.json() の結果は下記の形。
    {
        "data": [
            {
                "id": "ユーザーID",
                "name": "表示名",
                "username": "ユーザー名(@の後ろ)",
                "profile_image_url": "アイコン画像のURL"
            }
        ]
    }
    ※ 削除・凍結されたユーザーのIDが含まれていた場合、そのユーザーは dataに入らず、
      代わりに "errors" キーに理由が入る。
    """
    response = requests.get(
        TWITTER_USERS_ENDPOINT,
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        params={
            "ids": ",".join(str(user_id) for user_id in user_ids),
            "user.fields": "profile_image_url",
        },
    )
    return response
