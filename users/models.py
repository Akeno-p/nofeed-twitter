from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from common.x_api_client import XUserResponseData


class XUserManager(models.Manager):
    def bulk_create_from_responses(
        self, x_user_responses: list[XUserResponseData]
    ) -> None:
        """ユーザー情報を複数保存する"""
        x_users = []
        for response in x_user_responses:
            x_user = XUser(
                id=response.get("id"),
                username=response.get("username"),
                name=response.get("name"),
                profile_image_url=response.get("profile_image_url"),
            )
            x_users.append(x_user)

        XUser.objects.bulk_create(x_users)


class XUser(models.Model):
    """ユーザー情報"""

    objects = XUserManager()

    id = models.BigIntegerField(primary_key=True, help_text="TwitterのユーザーID")
    username = models.CharField(max_length=100, help_text="ユーザー名(@の後ろ)")
    name = models.CharField(max_length=100, help_text="表示名")
    profile_image_url = models.URLField(
        blank=True, null=True, help_text="アイコン画像URL"
    )

    class Meta:
        db_table = "x_users"


class Account(AbstractUser):
    """nofeed-twitter利用者の認証・トークン管理用"""

    id = models.BigAutoField(primary_key=True)
    x_user = models.OneToOneField(
        XUser,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="account",
        help_text="Userテーブルの参照",
    )
    access_token = models.TextField(
        blank=True, null=True, help_text="OAuth 2.0 アクセストークン"
    )
    refresh_token = models.TextField(
        blank=True, null=True, help_text="OAuth 2.0 リフレッシュトークン"
    )
    totp_secret = models.TextField(
        blank=True,
        null=True,
        help_text="nofeed-twitterの2段階認証用TOTP秘密鍵",
    )

    class Meta:
        db_table = "accounts"
