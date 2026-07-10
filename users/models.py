from django.db import models


class User(models.Model):
    """ユーザー情報"""

    id = models.BigIntegerField(primary_key=True, help_text="TwitterのユーザーID")
    username = models.CharField(max_length=100, help_text="ユーザー名(@の後ろ)")
    name = models.CharField(max_length=100, help_text="表示名")
    profile_image_url = models.URLField(
        blank=True, null=True, help_text="アイコン画像URL"
    )

    class Meta:
        db_table = "users"


class Account(models.Model):
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
    access_token = models.TextField(help_text="OAuth 2.0 アクセストークン")
    refresh_token = models.TextField(
        blank=True, null=True, help_text="OAuth 2.0 リフレッシュトークン"
    )
    access_token_expires_at = models.DateTimeField(
        blank=True, null=True, help_text="アクセストークンの有効期限"
    )
    totp_secret = models.TextField(blank=True, null=True, help_text="TOTP秘密鍵")

    class Meta:
        db_table = "accounts"
