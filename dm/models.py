from django.db import models


class Conversation(models.Model):
    """DMの会話単位"""

    id = models.BigAutoField(primary_key=True, help_text="DMの会話ID")
    participant = models.ForeignKey(
        "users.User",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
        help_text="DMの相手",
    )
    dm_conversation_id = models.CharField(
        max_length=50, help_text="DMの会話ID(相手と共有)"
    )
    last_message_at = models.DateTimeField(
        blank=True, null=True, help_text="最後のメッセージ日時"
    )

    class Meta:
        db_table = "conversations"


class DirectMessage(models.Model):
    """DMメッセージ"""

    id = models.BigIntegerField(primary_key=True, help_text="DMメッセージ ID")
    conversation = models.ForeignKey(
        "dm.Conversation",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="messages",
        help_text="DMの部屋",
    )
    sender = models.ForeignKey(
        "users.User",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="senders",
        help_text="送信者",
    )
    text = models.TextField(help_text="DM本文")
    created_at = models.DateTimeField(help_text="DM送信日時")

    class Meta:
        db_table = "direct_messages"


class DirectMessageMedia(models.Model):
    """DMメディア情報(画像・動画)"""

    class MediaType(models.TextChoices):
        PHOTO = "photo", "写真"
        VIDEO = "video", "動画"
        GIF = "animated_gif", "gif画像"

    media_key = models.CharField(
        primary_key=True, max_length=50, help_text="Xのmedia_key"
    )
    direct_message = models.ForeignKey(
        "dm.DirectMessage",
        on_delete=models.CASCADE,
        related_name="media",
        help_text="紐づくDM",
    )
    media_type = models.CharField(
        max_length=12, choices=MediaType.choices, help_text="メディアの種類"
    )
    url = models.CharField(help_text="メディアのURL")
    alt_text = models.TextField(blank=True, null=True, help_text="代替テキスト")
    width = models.IntegerField(help_text="メディアの横幅(px)")
    height = models.IntegerField(help_text="メディアの縦幅(px)")
    duration_ms = models.IntegerField(
        blank=True, null=True, help_text="動画の長さ(m秒)"
    )

    class Meta:
        db_table = "media"
