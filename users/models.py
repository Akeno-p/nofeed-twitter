from __future__ import annotations

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import QuerySet

from common.x_api_client import TweetResponseData, XUserResponseData


class XUserManager(models.Manager):
    def all_user_ids(self) -> QuerySet[int]:
        """保存済みのXのユーザーIDを返す"""
        saved_user_ids = self.values_list("id", flat=True)
        return saved_user_ids

    def not_saved_author_ids(
        self, tweet_responses: list[TweetResponseData]
    ) -> list[int]:
        """ツイートのリストから未保存のユーザーのIDを取得して返す"""
        not_saved_author_ids = []
        saved_user_ids = set(self.all_user_ids())
        for response in tweet_responses:
            author_id = int(response["author_id"])
            if author_id not in saved_user_ids:
                not_saved_author_ids.append(author_id)

        return not_saved_author_ids

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

        self.bulk_create(x_users)


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


class AccountManager(UserManager):
    def update_token(self, user_id: int, access_token: str, refresh_token: str) -> None:
        """トークンを更新する。 戻り値はない。"""
        self.filter(id=user_id).update(
            access_token=access_token, refresh_token=refresh_token
        )

    def update_x_user(self, user_id: int, x_user: XUser) -> None:
        """x_userを更新する。戻り値はない。"""
        self.filter(id=user_id).update(x_user=x_user)


class Account(AbstractUser):
    """nofeed-twitter利用者の認証・トークン管理用"""

    objects = AccountManager()

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
