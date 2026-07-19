from django.shortcuts import render
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.urls import reverse


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
        return JsonResponse(
            {"status": "success", "redirect_url": reverse("two_factor_auth")}
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
