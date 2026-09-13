import secrets

import pyotp
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from common.utils import request_with_token_refresh
from common.x_api_client import build_auth_url, get_me, post_token_request

from .decorators import (
    redirect_to_login_if_no_pending_user,
    redirect_to_tweets_if_logged_in,
)
from .models import Account, XUser
from .totp import make_qrcode_b64
from .x_oauth import make_code_challenge


@redirect_to_tweets_if_logged_in
def login_view(request):
    """ログインページを開く"""
    return render(request, "users/login.html")


@require_POST
@redirect_to_tweets_if_logged_in
def do_login(request):
    """ログイン処理を実行する"""
    username = request.POST.get("username")
    password = request.POST.get("password")

    if username == "" and password == "":
        return JsonResponse(
            {
                "status": "fail",
                "reason": "empty",
                "empty_fields": ["username", "password"],
                "message": "「ユーザー名」と「パスワード」が空欄です。",
            }
        )

    if username == "":
        return JsonResponse(
            {
                "status": "fail",
                "reason": "empty",
                "empty_fields": ["username"],
                "message": "「ユーザー名」が空欄です。",
            }
        )

    if password == "":
        return JsonResponse(
            {
                "status": "fail",
                "reason": "empty",
                "empty_fields": ["password"],
                "message": "「パスワード」が空欄です。",
            }
        )

    user = authenticate(request, username=username, password=password)

    if user:
        request.session["pending_user_id"] = user.id

        if user.totp_secret:
            return JsonResponse(
                {"status": "success", "redirect_url": reverse("totp_auth")}
            )
        else:
            return JsonResponse(
                {
                    "status": "success",
                    "redirect_url": reverse("totp_setup"),
                }
            )

    return JsonResponse(
        {
            "status": "fail",
            "reason": "invalid_credentials",
            "message": "「ユーザー名」か「パスワード」が間違っています。",
        }
    )


@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def totp_setup_view(request):
    """2段階認証用 QRコード ページを開く"""
    user_id = request.session.get("pending_user_id")

    account = Account.objects.get(id=user_id)
    totp_secret = account.totp_secret

    # パスワードとユーザー名が流出した場合、login.htmlでパスワードとユーザー名を入力後
    # [users/totp_setup/]に直接アクセスすることで、秘密鍵を再設定できてしまうのを防ぐため
    if totp_secret:
        return redirect("totp_auth")

    # すでにqrコード読み取り済みで[totp_setup.html]ページをリロードしてしまった場合、
    # 秘密鍵が一致しなくなるため
    if not request.session.get("pending_totp_secret"):
        pending_totp_secret = pyotp.random_base32()
    else:
        pending_totp_secret = request.session.get("pending_totp_secret")

    request.session["pending_totp_secret"] = pending_totp_secret

    qrcode_b64 = make_qrcode_b64(account.username, pending_totp_secret)

    return render(
        request,
        "users/totp_setup.html",
        {"qrcode": qrcode_b64},
    )


@require_POST
@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def totp_setup_verify(request):
    """totp_secret 初回保存処理

    QRコードを読み取った認証アプリの認証コードを検証し、
    正しければ Account.totp_secret に保存してログインする。
    """
    totp_auth_number = request.POST.get("totpAuthNumber")
    pending_totp_secret = request.session.get("pending_totp_secret")

    totp = pyotp.TOTP(pending_totp_secret)

    if totp.verify(totp_auth_number):
        pending_user_id = request.session.get("pending_user_id")
        account = Account.objects.get(id=pending_user_id)
        account.totp_secret = pending_totp_secret
        account.save(update_fields=["totp_secret"])

        login(request, account)

        if not account.is_x_linked():
            return JsonResponse(
                {"status": "success", "redirect_url": reverse("twitter_auth")}
            )
        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})
    else:
        return JsonResponse({"status": "fail", "message": "認証コードが一致しません。"})


@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def totp_auth_view(request):
    """2段階認証コード 入力ページを開く"""
    pending_user_id = request.session.get("pending_user_id")
    account = Account.objects.get(id=pending_user_id)
    if not account.totp_secret:
        return redirect("totp_setup")
    return render(request, "users/totp_auth.html")


@require_POST
@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def totp_auth_verify(request):
    """2段階認証の処理"""
    totp_auth_number = request.POST.get("totpAuthNumber")

    pending_user_id = request.session.get("pending_user_id")
    account = Account.objects.get(id=pending_user_id)

    totp = pyotp.TOTP(account.totp_secret)

    if totp.verify(totp_auth_number):
        login(request, account)

        if not account.is_x_linked():
            return JsonResponse(
                {"status": "success", "redirect_url": reverse("twitter_auth")}
            )
        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})

    return JsonResponse({"status": "fail", "message": "認証キーが正しくありません。"})


@login_required
def twitter_auth_view(request):
    """Twitter認証ページを開く"""
    if request.user.is_x_linked():
        return redirect("tweets")
    return render(request, "users/twitter_auth.html")


@login_required
@require_POST
def twitter_auth_start(request):
    """Twitter認証ページへのURLを生成して返す"""
    # 文字数はcode_verifierが43~128指定 stateは指定なし
    # token_urlsafeの引数は文字数ではなくバイト数なので(16)は16文字という意味ではない。
    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = make_code_challenge(code_verifier)

    twitter_auth_url = build_auth_url(state, code_challenge)

    request.session["state"] = state
    request.session["code_verifier"] = code_verifier

    return JsonResponse({"redirect_url": twitter_auth_url})


@login_required
def twitter_auth_callback(request):
    """Twitter認証後のコールバック処理"""
    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.pop("state", None)
    code_verifier = request.session.pop("code_verifier", None)

    if state is None or state != session_state or code is None:
        return redirect("twitter_auth_error")

    response = post_token_request(code, code_verifier)

    if response.status_code != 200:
        return redirect("twitter_auth_error")

    token_data = response.json()

    Account.objects.update_token(
        request.user, token_data["access_token"], token_data["refresh_token"]
    )

    if not request.user.x_user:
        status = _register_x_user(request)
        if status == "error":
            return redirect("twitter_auth_error")

    return redirect("tweets")


def twitter_auth_error_view(request):
    """Twitter認証失敗ページを開く"""
    return render(request, "users/twitter_auth_error.html")


def _register_x_user(request):
    """ログイン中のユーザー自身のTwitterユーザー情報を取得し、DBに登録する。"""
    status, result = request_with_token_refresh(request, get_me)

    if status == "error":
        return status

    data = result.json()["data"]
    x_user = XUser(
        id=data.get("id"),
        username=data.get("username"),
        name=data.get("name"),
        profile_image_url=data.get("profile_image_url"),
    )

    x_user.save()

    Account.objects.update_x_user(request.user, x_user)

    return status
