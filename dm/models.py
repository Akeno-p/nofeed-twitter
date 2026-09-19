from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from django.db import models
from django.db.models import QuerySet
from django.utils.dateparse import parse_datetime

from common.x_api_client import DirectMessageResponseData, MediaResponseData
from users.models import Account


class DirectMessageMediaPair(TypedDict):
    """メディアキー(pk)とそれに紐づくDMのID(pk)を持った辞書

    media_key: メディアキー(DirectMessageMedia.media_key)
    direct_message_id: DMのID(DirectMessage.id)
    """

    media_key: str
    direct_message_id: int


class ConversationManager(models.Manager):
    def participant_ids(
        self, dm_responses: list[DirectMessageResponseData], account: Account
    ) -> set[int]:
        """1対1のDMのリストから、会話相手のユーザーIDを重複なしで返す"""
        participant_ids = set()
        for response in dm_responses:
            participant_id = Conversation.participant_id_from(
                response["dm_conversation_id"], account
            )
            participant_ids.add(participant_id)

        return participant_ids

    def save_from_responses(
        self,
        dm_responses: list[DirectMessageResponseData],
        account: Account,
        saved_user_ids: set[int],
    ) -> dict[str, Conversation]:
        """1対1のDMのリストから会話を保存する。

        未保存の会話は新しく作成し、保存済みの会話は最後のメッセージ日時を更新する。

        dm_responses: 保存したいDM。
        saved_user_ids: 保存済みのXユーザーID。会話相手が未保存の場合は会話相手を空にする。

        戻り値は dm_conversation_id がキー Conversationインスタンス が値 の辞書。
        """
        last_message_at_by_dm_conversation_id: dict[str, datetime] = {}

        for dm_response in dm_responses:
            dm_conversation_id = dm_response["dm_conversation_id"]
            created_at = parse_datetime(dm_response["created_at"])
            last_message_at = last_message_at_by_dm_conversation_id.get(
                dm_conversation_id
            )

            if last_message_at is None or created_at > last_message_at:
                last_message_at_by_dm_conversation_id[dm_conversation_id] = created_at

        conversations_by_dm_conversation_id = {}

        for conversation in self.filter(
            dm_conversation_id__in=last_message_at_by_dm_conversation_id.keys()
        ):
            conversations_by_dm_conversation_id[conversation.dm_conversation_id] = (
                conversation
            )

        new_conversations = []
        update_conversations = []
        for (
            dm_conversation_id,
            last_message_at,
        ) in last_message_at_by_dm_conversation_id.items():
            conversation = conversations_by_dm_conversation_id.get(dm_conversation_id)

            if conversation is None:
                participant_id = Conversation.participant_id_from(
                    dm_conversation_id, account
                )

                if participant_id not in saved_user_ids:
                    participant_id = None

                conversation = Conversation(
                    participant_id=participant_id,
                    dm_conversation_id=dm_conversation_id,
                    last_message_at=last_message_at,
                )
                new_conversations.append(conversation)

                conversations_by_dm_conversation_id[dm_conversation_id] = conversation
                continue

            if (
                conversation.last_message_at is None
                or last_message_at > conversation.last_message_at
            ):
                conversation.last_message_at = last_message_at
                update_conversations.append(conversation)

        self.bulk_create(new_conversations)
        self.bulk_update(update_conversations)
        return conversations_by_dm_conversation_id


class Conversation(models.Model):
    """DMの会話単位"""

    objects = ConversationManager()

    id = models.BigAutoField(primary_key=True, help_text="DMの会話ID")
    participant = models.ForeignKey(
        "users.XUser",
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

    @staticmethod
    def is_one_to_one(dm_conversation_id: str) -> bool:
        """会話IDが1対1のDMのものであれば True を返す。

        1対1のDMの会話IDは「小さいユーザーID-大きいユーザーID」の形式で、
        グループDMの会話IDは数字のみの形式になっている。
        """
        return "-" in dm_conversation_id

    @staticmethod
    def participant_id_from(dm_conversation_id: str, account: Account) -> int:
        """1対1のDMの会話IDから、会話相手のユーザーIDを返す。"""
        user_ids = [int(user_id) for user_id in dm_conversation_id.split("-")]

        for user_id in user_ids:
            if user_id != account.x_user_id:
                return user_id

        # 自分自身とのDMの場合
        return account.x_user_id


class DirectMessageManager(models.Manager):
    def all_dm_ids(self) -> QuerySet[int]:
        """すべてのDMのIDを返す"""
        return self.values_list("id", flat=True)

    def last_dm(self) -> DirectMessage | None:
        """最新のDMを返す"""
        return self.order_by("-created_at").first()

    def bulk_create_from_responses(
        self,
        dm_responses: list[DirectMessageResponseData],
        conversations_by_dm_conversation_id: dict[str, Conversation],
        saved_user_ids: set[int],
    ) -> list[DirectMessageMediaPair]:
        """リストで渡したDMのうち、未保存のものを保存する。

        dm_responses: 保存したいDM。
        conversations_by_dm_conversation_id: dm_conversation_id をキーにした、DMの紐づけ先の会話の辞書。
        saved_user_ids: 保存済みのXユーザーID。送信者が未保存の場合は送信者を空にする。

        戻り値は、DMに添付されたメディアのメディアキーとDMのIDの組のリスト。
        """
        saved_dm_ids = set(self.all_dm_ids())
        direct_messages = []
        dm_media_pairs = []

        for response in dm_responses:
            dm_id = int(response["id"])

            media_keys = response.get("attachments", {}).get("media_keys", [])

            for media_key in media_keys:
                dm_media_pairs.append(
                    {"media_key": media_key, "direct_message_id": dm_id}
                )

            if dm_id in saved_dm_ids:
                continue

            sender_id = int(response["sender_id"])

            if sender_id not in saved_user_ids:
                sender_id = None

            direct_message = DirectMessage(
                id=dm_id,
                conversation=conversations_by_dm_conversation_id[
                    response["dm_conversation_id"]
                ],
                sender_id=sender_id,
                text=response.get("text", ""),
                created_at=response["created_at"],
            )
            direct_messages.append(direct_message)
            saved_dm_ids.add(dm_id)

        self.bulk_create(direct_messages)

        return dm_media_pairs


class DirectMessage(models.Model):
    """DMメッセージ"""

    objects = DirectMessageManager()

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
        "users.XUser",
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


class DirectMessageMediaManager(models.Manager):
    def all_media_keys(self) -> QuerySet[str]:
        """すべてのDMメディアのmedia_key(id)を返す"""
        return self.values_list("media_key", flat=True)

    def bulk_create_from_responses(
        self,
        media_responses: list[MediaResponseData],
        dm_media_pairs: list[DirectMessageMediaPair],
    ) -> None:
        """リストで渡したメディアのうち、未保存のものを保存する。

        media_responses: 保存したいメディア。
        dm_media_pairs: メディアキーとそれに紐づくDMのIDの組のリスト。組がないメディアは保存しない。
        """
        saved_media_keys = set(self.all_media_keys())
        dm_id_by_media_key = {
            pair["media_key"]: pair["direct_message_id"] for pair in dm_media_pairs
        }
        media_list = []

        for response in media_responses:
            media_key = response["media_key"]
            direct_message_id = dm_id_by_media_key.get(media_key)

            if media_key in saved_media_keys:
                continue

            # グループDMのメディアなど、紐づくDMを保存していないメディアは保存できないため
            if direct_message_id is None:
                continue

            media = DirectMessageMedia(
                media_key=media_key,
                direct_message_id=direct_message_id,
                media_type=response.get("type"),
                url=response.get("url"),
                alt_text=response.get("alt_text"),
                width=response.get("width"),
                height=response.get("height"),
                duration_ms=response.get("duration_ms"),
            )
            media_list.append(media)
            saved_media_keys.add(media_key)

        self.bulk_create(media_list)


class DirectMessageMedia(models.Model):
    """DMメディア情報(画像・動画)"""

    objects = DirectMessageMediaManager()

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
    url = models.CharField(blank=True, null=True, help_text="メディアのURL")
    alt_text = models.TextField(blank=True, null=True, help_text="代替テキスト")
    width = models.IntegerField(blank=True, null=True, help_text="メディアの横幅(px)")
    height = models.IntegerField(blank=True, null=True, help_text="メディアの縦幅(px)")
    duration_ms = models.IntegerField(
        blank=True, null=True, help_text="動画の長さ(m秒)"
    )

    class Meta:
        db_table = "media"
