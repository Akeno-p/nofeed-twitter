from .models import Account
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from urllib.parse import urlencode
from django.conf import settings
from .decorators import (
    redirect_to_tweets_if_logged_in,
    redirect_to_login_if_no_pending_user,
)
import pyotp
import qrcode
import io
import base64
import secrets
import hashlib


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

    has_totp_secret = bool(
        (
            Account.objects.filter(id=user_id)
            .values_list("totp_secret", flat=True)
            .first()
        )
    )
    print(has_totp_secret)

    # パスワードとユーザー名が流出した場合、login.htmlでパスワードとユーザー名を入力後
    # [users/two_factor_qrcode/]に直接アクセスすることで、秘密鍵を再設定できてしまうのを防ぐため
    if has_totp_secret:
        return redirect("two_factor_auth")

    user_name = Account.objects.get(id=user_id).username

    # すでにqrコード読み取り済みで[two_factor_qrcode.html]ページをリロードしてしまった場合、
    # 秘密鍵が一致しなくなるため
    if not request.session.get("interim_totp_secret"):
        interim_totp_secret = pyotp.random_base32()
    else:
        interim_totp_secret = request.session.get("interim_totp_secret")

    request.session["interim_totp_secret"] = interim_totp_secret

    url = pyotp.TOTP(interim_totp_secret).provisioning_uri(
        name=user_name, issuer_name="nofeed-twitter"
    )

    qrcode_img = qrcode.make(url)

    buffer = io.BytesIO()

    qrcode_img.save(buffer)
    qrcode_b64 = base64.b64encode(buffer.getvalue()).decode()

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
    interim_totp_secret = request.session.get("interim_totp_secret")

    totp = pyotp.TOTP(interim_totp_secret)

    if totp.verify(two_factor_code):
        pending_user_id = request.session.get("pending_user_id")
        user = Account.objects.get(id=pending_user_id)
        user.totp_secret = interim_totp_secret
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
    totp_secret = (
        Account.objects.filter(id=pending_user_id)
        .values_list("totp_secret", flat=True)
        .first()
    )
    if not totp_secret:
        return redirect("two_factor_qrcode")
    return render(request, "users/two_factor_auth.html")


@require_POST
@redirect_to_tweets_if_logged_in
@redirect_to_login_if_no_pending_user
def totp_auth(request):
    totp_auth_number = request.POST.get("totpAuthNumber")

    pending_user_id = request.session.get("pending_user_id")
    user = Account.objects.get(id=pending_user_id)

    totp_secret = user.totp_secret

    totp = pyotp.TOTP(totp_secret)

    if totp.verify(totp_auth_number):
        login(request, user)
        has_access_token = bool(user.access_token)
        if not has_access_token:
            return JsonResponse(
                {"status": "success", "redirect_url": reverse("twitter_auth")}
            )
        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})

    return JsonResponse({"status": "fail", "message": "認証キーが正しくありません。"})


@login_required
def twitter_auth_view(request):
    has_access_token = bool(request.user.access_token)
    if has_access_token:
        return redirect("tweets")
    return render(request, "users/twitter_auth.html")


@login_required
@require_POST
def twitter_auth_start(request):
    # 文字数はcode_verifierが43~128指定 stateは指定なし
    # token_urlsafeの引数は文字数ではなくバイト数なので(16)は16文字という意味ではない。
    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)

    code_challenge = _sha256_base64url(code_verifier)

    request.session["state"] = state
    request.session["code_verifier"] = code_verifier

    # 現状このアプリを使用するのは自分だけの想定なので、とりあえず全部の権限をとりあえず列挙している。
    # アプリが完成したら不要だった権限は消していいかもしれない。
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

    TWITTER_AUTH_ENDPOINT = "https://x.com/i/oauth2/authorize"

    params = {
        "response_type": "code",
        "client_id": settings.TWITTER_CLIENT_ID,
        "redirect_uri": "http://localhost:8000/users/twitter_auth_redirect/",
        "scope": TWITTER_AUTH_ALL_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    encoded_params = urlencode(params)

    twitter_auth_url = TWITTER_AUTH_ENDPOINT + "?" + encoded_params

    return JsonResponse({"redirect_url": twitter_auth_url})


def _sha256_base64url(code_verifier):
    """sha256のハッシュ値をbase64url形式に直した値を返す。"""

    code_challenge = code_verifier.encode()
    code_challenge = hashlib.sha256(code_challenge).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge)
    code_challenge = code_challenge.decode()
    code_challenge = code_challenge.rstrip("=")

    return code_challenge


def twitter_auth_redirect():
    print("ここがリダイレクトurlです。")
