from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from common.x_api_client import UserResponseData


class UserManager(models.Manager):
    def bulk_create_from_responses(
        self, user_responses: list[UserResponseData]
    ) -> None:
        """ユーザー情報を複数保存する"""
        users = []
        for response in user_responses:
            user = User(
                id=response.get("id"),
                username=response.get("username"),
                name=response.get("name"),
                profile_image_url=response.get("profile_image_url"),
            )
            users.append(user)

        User.objects.bulk_create(users)


class User(models.Model):
    """ユーザー情報"""

    objects = UserManager()

    id = models.BigIntegerField(primary_key=True, help_text="TwitterのユーザーID")
    username = models.CharField(max_length=100, help_text="ユーザー名(@の後ろ)")
    name = models.CharField(max_length=100, help_text="表示名")
    profile_image_url = models.URLField(
        blank=True, null=True, help_text="アイコン画像URL"
    )

    class Meta:
        db_table = "users"


class Account(AbstractUser):
    """nofeed-twitter利用者の認証・トークン管理用"""

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        User,
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
