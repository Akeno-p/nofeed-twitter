"""
複数のアプリから使用する共通の関数をまとめたモジュール。
定数やエンドポイントURLは common/x_api.py に置く。
"""

import requests

from common.x_api import (
    TWITTER_CLIENT_ID,
    TWITTER_CLIENT_SECRET,
    TWITTER_TOKEN_ENDPOINT,
)
from users.models import Account


def _update_tokens(request):
    """リフレッシュトークンを使って、アクセストークンを新しくする。

    成功した場合は True 失敗した場合は Flase  を返す。
    """

    # 呼ぶタイミングによってuserの情報が古く、有効なrefresh_tokenが存在しない場合があるため
    request.user.refresh_from_db()
    refresh_token = request.user.refresh_token

    twitter_tokens_endpoint_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": TWITTER_CLIENT_ID,
    }

    new_tokens_response = requests.post(
        TWITTER_TOKEN_ENDPOINT,
        data=twitter_tokens_endpoint_data,
        auth=(
            TWITTER_CLIENT_ID,
            TWITTER_CLIENT_SECRET,
        ),
    )

    if new_tokens_response.status_code != 200:
        return False

    new_tokens_dict = new_tokens_response.json()
    new_access_token = new_tokens_dict.get("access_token")
    new_refresh_token = new_tokens_dict.get("refresh_token")

    Account.objects.filter(id=request.user.id).update(
        access_token=new_access_token, refresh_token=new_refresh_token
    )

    request.user.refresh_from_db()

    return True


def _request_with_token_refresh(request, send_request, success_code):
    """リクエストを実行し、401 の場合はトークンを更新して再実行する。

    send_request には引数なしで呼べるリクエスト関数を、
    success_code には成功とみなす status_code を渡す。

    (status, 値) のタプルを返す。
    成功時は ("success", response)、
    失敗時は ("error", エラー内容の辞書) を返す。
    """
    response = send_request()

    if response.status_code == 401:
        if not _update_tokens(request):
            return "error", {
                "status": "error",
                "message": "アクセストークンの更新に失敗しました。",
                "error_code": response.status_code,
            }

        response = send_request()
    print(response.status_code)

    if response.status_code != success_code:
        return "error", {
            "status": "error",
            "message": "想定外のエラーが発生しました。",
            "error_code": response.status_code,
        }

    return "success", response
