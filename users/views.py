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
    return render(request, "users/login.html")


@require_POST
@redirect_to_tweets_if_logged_in
def do_login(request):
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
                {"status": "success", "redirect_url": reverse("two_factor_auth")}
            )
        else:
            return JsonResponse(
                {
                    "status": "success",
                    "redirect_url": reverse("two_factor_qrcode"),
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
def two_factor_qrcode_view(request):
    user_id = request.session.get("pending_user_id")

    account = Account.objects.get(id=user_id)
    totp_secret = account.totp_secret

    # パスワードとユーザー名が流出した場合、login.htmlでパスワードとユーザー名を入力後
    # [users/two_factor_qrcode/]に直接アクセスすることで、秘密鍵を再設定できてしまうのを防ぐため
    if totp_secret:
        return redirect("two_factor_auth")

    # すでにqrコード読み取り済みで[two_factor_qrcode.html]ページをリロードしてしまった場合、
    # 秘密鍵が一致しなくなるため
    if not request.session.get("pending_totp_secret"):
        pending_totp_secret = pyotp.random_base32()
    else:
        pending_totp_secret = request.session.get("pending_totp_secret")

    request.session["pending_totp_secret"] = pending_totp_secret

    qrcode_b64 = make_qrcode_b64(account.username, pending_totp_secret)

    return render(
        request,
        "users/two_factor_qrcode.html",
        {"qrcode": qrcode_b64},
    )


@require_POST
@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def verify_two_factor_code(request):
    """入力された認証キーが正しいか確認

    正しい場合はAccount.totp_secretに保存する。
    """
    two_factor_code = request.POST.get("twoFactorCode")
    pending_totp_secret = request.session.get("pending_totp_secret")

    totp = pyotp.TOTP(pending_totp_secret)

    if totp.verify(two_factor_code):
        pending_user_id = request.session.get("pending_user_id")
        user = Account.objects.get(id=pending_user_id)
        user.totp_secret = pending_totp_secret
        user.save(update_fields=["totp_secret"])

        login(request, user)

        has_access_token = bool(user.access_token)

        if not has_access_token:
            return JsonResponse(
                {"status": "success", "redirect_url": reverse("twitter_auth")}
            )
        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})
    else:
        return JsonResponse({"status": "fail", "message": "認証コードが一致しません。"})


@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def two_factor_auth_view(request):
    pending_user_id = request.session.get("pending_user_id")
    account = Account.objects.filter(id=pending_user_id).first()
    if account is None:
        return redirect("login")
    if not account.totp_secret:
        return redirect("two_factor_qrcode")
    return render(request, "users/two_factor_auth.html")


@require_POST
@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def totp_auth(request):
    totp_auth_number = request.POST.get("totpAuthNumber")

    pending_user_id = request.session.get("pending_user_id")
    user = Account.objects.get(id=pending_user_id)

    totp = pyotp.TOTP(user.totp_secret)

    if totp.verify(totp_auth_number):
        login(request, user)
        if not user.access_token:
            return JsonResponse(
                {"status": "success", "redirect_url": reverse("twitter_auth")}
            )
        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})

    return JsonResponse({"status": "fail", "message": "認証キーが正しくありません。"})


@login_required
def twitter_auth_view(request):
    if request.user.access_token and request.user.x_user:
        return redirect("tweets")
    return render(request, "users/twitter_auth.html")


@login_required
@require_POST
def twitter_auth_start(request):
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
def twitter_auth_redirect(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("state")
    code_verifier = request.session.get("code_verifier")

    if state is None or state != session_state:
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
    return render(request, "users/twitter_auth_error.html")


def _register_x_user(request):
    """ログイン中のユーザー自身のTwitterユーザー情報を取得し、DBに登録する。"""

    # 呼ぶタイミングによってuserの情報が古く、有効なaccess_tokenが存在しない場合があるため
    request.user.refresh_from_db()

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

    # 一応requestのuser情報を更新しておく
    request.user.refresh_from_db()

    return status
