"""
複数のアプリから使用する共通の関数をまとめたモジュール。
"""

import logging

import requests

from common.x_api_client import post_update_tokens
from users.models import Account

logger = logging.getLogger(__name__)


def update_tokens(request):
    """リフレッシュトークンを使って、アクセストークンを新しくする。

    成功した場合は True 失敗した場合は Flase  を返す。
    """
    response = post_update_tokens(request)

    if response.status_code != 200:
        return False

    token_data = response.json()

    Account.objects.update_tokens(
        request.user, token_data["access_token"], token_data["refresh_token"]
    )

    return True


def request_with_token_refresh(request, send_request, *args):
    """リクエストを実行し、401 の場合はトークンを更新して再実行する。

    send_request に渡す関数の第一引数は request である必要がある。

    (status, 値) のタプルを返す。
    成功時は ("success", response)、
    失敗時は ("error", エラー内容の辞書) を返す。
    """
    try:
        response = send_request(request, *args)
    except requests.exceptions.RequestException as e:
        logger.exception("APIリクエスト失敗: %s %s", e.request.method, e.request.url)
        return "error", {
            "status": "error",
            "message": "接続に失敗しました。",
            "error_code": response.status_code,
        }

    if response.status_code == 401:
        if not update_tokens(request):
            return "error", {
                "status": "error",
                "message": "アクセストークンの更新に失敗しました。",
                "error_code": response.status_code,
            }

        try:
            response = send_request(request, *args)
        except requests.exceptions.RequestException as e:
            logger.exception(
                "APIリクエスト失敗: %s %s", e.request.method, e.request.url
            )
            return "error", {
                "status": "error",
                "message": "接続に失敗しました。",
                "error_code": response.status_code,
            }

    if not (200 <= response.status_code < 300):
        logger.error(
            "APIリクエスト失敗: status=%s body=%s", response.status_code, response.text
        )
        return "error", {
            "status": "error",
            "message": "想定外のエラーが発生しました。",
            "error_code": response.status_code,
        }

    return "success", response
