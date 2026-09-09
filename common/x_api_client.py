"""
X APIへ実際にリクエストを送る関数をまとめたモジュール。
定数やエンドポイントURLは common/x_api.py に置く。
"""

from typing import TypedDict
from urllib.parse import urlencode

import requests
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from common.x_api import (
    TWITTER_AUTH_ENDPOINT,
    TWITTER_CLIENT_ID,
    TWITTER_CLIENT_SECRET,
    TWITTER_GET_TWEET_ENDPOINT,
    TWITTER_MEDIA_ENDPOINT,
    TWITTER_REDIRECT_URI,
    TWITTER_SEARCH_RECENT_ENDPOINT,
    TWITTER_TOKEN_ENDPOINT,
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


def build_auth_url(state: str, code_challenge: str) -> str:
    """twitter の認証画面へ遷移させるための URL を組み立てて返す。

    state: リダイレクトURLにくっついて返ってくる。呼び出し側のセッションの値と突合して自分のアプリが始めた認証か判別する。
    code_challenge: PKCE 用のハッシュ値。X側が保持して、トークン交換時 code_verifier(ハッシュ前の値)を送り突合する。
    """
    # 現状このアプリを使用するのは自分だけの想定なので、とりあえず全部の権限をとりあえず列挙している。
    # 不要だった権限は消していいかもしれない。
    TWITTER_AUTH_ALL_SCOPE = (
        "tweet.read "
        "tweet.write "
        "tweet.moderate.write "
        "users.read "
        "users.email "
        "follows.read "
        "follows.write "
        "offline.access "
        "space.read "
        "mute.read "
        "mute.write "
        "like.read "
        "like.write "
        "list.read "
        "list.write "
        "block.read "
        "block.write "
        "bookmark.read "
        "bookmark.write "
        "dm.read dm.write "
        "media.write"
    )

    params = {
        "response_type": "code",
        "client_id": TWITTER_CLIENT_ID,
        "redirect_uri": TWITTER_REDIRECT_URI,
        "scope": TWITTER_AUTH_ALL_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    encoded_params = urlencode(params)

    twitter_auth_url = TWITTER_AUTH_ENDPOINT + "?" + encoded_params

    return twitter_auth_url


def post_token_request(code: str, code_verifier: str) -> requests.Response:
    """認可コードをアクセストークンと交換するリクエスト

    code: 認証後リダイレクトで返ってくるコード。 X側がどの承認か特定するのに使用する。
    code_verifier: PKCE 用の値。code_challengeのハッシュ前の値が入っている。

    response.json() の結果は下記の形。
    {
        "token_type": "bearer",
        "expires_in": アクセストークンの有効秒数,
        "access_token": "アクセストークン",
        "refresh_token": "リフレッシュトークン",
        "scope": "許可されたスコープ"
    }
    """
    response = requests.post(
        TWITTER_TOKEN_ENDPOINT,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TWITTER_REDIRECT_URI,
            "client_id": TWITTER_CLIENT_ID,
            "code_verifier": code_verifier,
        },
        auth=(
            TWITTER_CLIENT_ID,
            TWITTER_CLIENT_SECRET,
        ),
    )
    return response


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


def get_replies(
    request: HttpRequest, next_token: str | None = None, since_id: int | None = None
) -> requests.Response:
    """自分宛てのリプライを一覧取得するリクエスト

    next_token: 2ページ目以降を取得するときだけ入れる。
    since_id: このIDより新しいリプライだけを取得したいときに入れる。

    response.json() の結果は下記の形。
        {
            "data": [TweetResponseData],
            "includes": {"media": [MediaResponseData]},
            "meta": {
                "result_count": 取得できた件数,
                "next_token": "次のページがあるときだけ入る"
            }
        }
    ※ 該当するリプライが0件の場合、"data" と "includes" は入らない。
    """
    params = {
        "query": f"to:{request.user.x_user.username} -is:retweet -from:{request.user.x_user.username}",
        "max_results": 100,
        "post.fields": "created_at,author_id,conversation_id,referenced_tweets",
        "expansions": "attachments.media_keys",
        "media.fields": "url,type,alt_text,width,height,duration_ms",
    }

    if next_token:
        params["pagination_token"] = next_token

    if since_id:
        params["since_id"] = since_id

    response = requests.get(
        TWITTER_SEARCH_RECENT_ENDPOINT,
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        params=params,
    )

    return response
