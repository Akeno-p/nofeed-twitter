from .models import Account
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.urls import reverse
import pyotp
import qrcode
import io
import base64


def login_view(request):
    return render(request, "users/login.html")


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


def two_factor_auth_view(request):
    return render(request, "users/two_factor_auth.html")


def two_factor_qrcode_view(request):
    user_id = request.session.get("pending_user_id")

    totp_secret = (
        Account.objects.filter(id=user_id).values_list("totp_secret", flat=True).first()
    )

    # パスワードとユーザー名が流出した場合、ログイン後[users/verify_two_factor_code/]に
    # 直接アクセスすることで、秘密鍵を再設定できてしまうのを防ぐため
    if totp_secret:
        return redirect("login")

    qrcode_b64 = _setup_totp_secret(request)
    return render(
        request,
        "users/two_factor_qrcode.html",
        {"qrcode": qrcode_b64},
    )


def _setup_totp_secret(request):
    """秘密鍵の生成とQRコードの生成

    戻り値はQRコードのbase64
    """
    user_id = request.session.get("pending_user_id")
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

    return qrcode_b64


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

        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})
    else:
        return JsonResponse({"status": "fail", "message": "認証コードが一致しません。"})


def totp_auth(request):
    totp_auth_number = request.POST.get("totpAuthNumber")

    pending_user_id = request.session.get("pending_user_id")
    user = Account.objects.get(id=pending_user_id)
    totp_secret = user.totp_secret

    totp = pyotp.TOTP(totp_secret)

    if totp.verify(totp_auth_number):
        login(request, user)
        return JsonResponse({"status": "success", "redirect_url": reverse("tweets")})
    else:
        return JsonResponse(
            {"status": "fail", "message": "認証キーが正しくありません。"}
        )
