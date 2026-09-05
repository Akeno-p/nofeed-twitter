from __future__ import annotations

from typing import TypedDict

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from common.x_api_client import MediaResponseData, TweetResponseData
from users.models import Account


class TweetMediaPair(TypedDict):
    """メディアキー(pk)とそれに紐づくツイートのID(pk)を持った辞書

    media_key: メディアキー(TweetMedia.media_key)
    tweet_id: ツイートID(Tweet.id)
    """

    media_key: str
    tweet_id: int


class TweetManager(models.Manager):
    def my_tweets(self, account: Account) -> QuerySet[Tweet]:
        """自分のツイート(リプライを除く)を新しい順で返す"""
        return (
            self.filter(author=account.user_id, in_reply_to_tweet_id__isnull=True)
            .select_related("author")
            .prefetch_related("media")
            .order_by("-created_at")
        )

    def all_tweet_ids(self) -> QuerySet[int]:
        """すべてのツイートのIdを返す"""
        return self.values_list("id", flat=True)

    def create_from_response(self, created_tweet: TweetResponseData) -> Tweet:
        """ツイートを1件保存する"""
        in_reply_to_tweet_id = None

        in_quoted_to_tweet_id = None

        tweet_type = created_tweet.get("type")

        if tweet_type == "quoted":
            in_quoted_to_tweet_id = created_tweet.get("id")
        elif tweet_type == "replied_to":
            in_reply_to_tweet_id = created_tweet.get("id")

        tweet = Tweet(
            id=created_tweet.get("id"),
            author_id=created_tweet.get("author_id"),
            text=created_tweet.get("text"),
            created_at=created_tweet.get("created_at"),
            conversation_id=created_tweet.get("conversation_id"),
            in_reply_to_tweet_id=in_reply_to_tweet_id,
            in_quoted_to_tweet_id=in_quoted_to_tweet_id,
        )

        tweet.save()

        return tweet

    def bulk_create_from_responses(
        self, tweet_responses: list[TweetResponseData], saved_tweet_ids: set[int]
    ) -> list[TweetMediaPair]:
        """リストで渡したツイートを保存する。

        tweet_responses: 保存したいツイート。
        saved_tweet_ids: 保存済みのツイートのID、保存済みのツイートをスキップするのに使用する。
        """

        tweets_list = []
        tweet_media_pairs = []
        for response in tweet_responses:
            tweet_id = int(response.get("id"))

            media_keys = response.get("attachments", {}).get("media_keys", [])

            for media_key in media_keys:
                tweet_media_pairs.append({"media_key": media_key, "tweet_id": tweet_id})

            if tweet_id in saved_tweet_ids:
                continue

            in_reply_to_tweet_id = None
            in_quoted_to_tweet_id = None

            referenced_tweet_list = response.get("referenced_tweets")

            if referenced_tweet_list is not None:
                for referenced_tweet in referenced_tweet_list:
                    referenced_tweet_type = referenced_tweet.get("type")

                    if referenced_tweet_type == "quoted":
                        in_quoted_to_tweet_id = referenced_tweet.get("id")
                    elif referenced_tweet_type == "replied_to":
                        in_reply_to_tweet_id = referenced_tweet.get("id")

            tweet = Tweet(
                id=tweet_id,
                author_id=response.get("author_id"),
                text=response.get("text"),
                created_at=response.get("created_at"),
                conversation_id=response.get("conversation_id"),
                in_reply_to_tweet_id=in_reply_to_tweet_id,
                in_quoted_to_tweet_id=in_quoted_to_tweet_id,
            )
            tweets_list.append(tweet)

        self.bulk_create(tweets_list)

        return tweet_media_pairs


class Tweet(models.Model):
    """ツイート"""

    objects = TweetManager()

    id = models.BigIntegerField(primary_key=True, help_text="tweetID")
    author = models.ForeignKey(
        "users.User",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="tweets",
        help_text="投稿者",
    )
    text = models.TextField(help_text="投稿本文")
    created_at = models.DateTimeField(help_text="投稿日時")
    conversation_id = models.BigIntegerField(blank=True, null=True, help_text="会話ID")
    in_reply_to_tweet_id = models.BigIntegerField(
        blank=True, null=True, help_text="リプライ先のTweet ID"
    )
    in_quoted_to_tweet_id = models.BigIntegerField(
        blank=True, null=True, help_text="引用先のTweet ID"
    )

    class Meta:
        db_table = "tweets"

    def strip_media_link(self):
        """画像付き投稿の本文末尾に付く t.co リンクを取り除く。"""
        self.text = self.text.rsplit("https://t.co", 1)[0]

    def set_display_created_at(self):
        """ツイートに、一覧表示用の作成日時を display_created_at としてセットする。

        表示形式は投稿日時によって変わる。
        当日は「3分」「5時間」、同じ年は「8月2日」、それ以外は「2025年8月2日」。

        戻り値はなく、渡された self に.display_created_atをセットする。
        """
        now = timezone.localtime()
        now_date = now.strftime("%Y年%m月%d日")
        now_year = now.strftime("%Y年")
        local_created = timezone.localtime(self.created_at)
        created_date = local_created.strftime("%Y年%m月%d日")
        created_year = local_created.strftime("%Y年")

        if now_date == created_date:
            diff_time = now - local_created
            diff_total_seconds = diff_time.total_seconds()
            diff_hours = int(diff_total_seconds // 3600)
            diff_minutes = int(diff_total_seconds % 3600 // 60)

            if diff_hours == 0:
                if diff_minutes == 0:
                    relative_time = "今"
                else:
                    relative_time = f"{diff_minutes}分"
            else:
                relative_time = f"{diff_hours}時間"
            self.display_created_at = relative_time
            return

        if now_year == created_year:
            # strftimeを使用すると08月02日のように0埋めになってしまうため
            month_day = f"{local_created.month}月{local_created.day}日"
            self.display_created_at = month_day
            return

        self.display_created_at = created_date


class TweetMediaManager(models.Manager):
    def all_tweet_media_keys(self) -> QuerySet[str]:
        """すべてのツイートメディアのmedia_key(id)を返す"""
        return TweetMedia.objects.values_list("media_key", flat=True)

    def bulk_create_for_tweet(
        self,
        media_responses: list[MediaResponseData],
        saved_tweet_media_keys: set[str],
        tweet_id: int,
    ) -> None:
        """リストで渡したメディアを保存する。メディアの紐づけ先のツイートが一つの場合こちらを使う。

        media_responses: 保存したいメディア。
        saved_tweet_media_keys: 保存済みのメディアのID、保存済みのメディアをスキップするのに使用する。
        tweet_id: メディア紐づけ先のツイートID

        【例】
        メディアA -- ツイートA
        メディアB -- ツイートA
        メディアC -- ツイートA
        メディアD -- ツイートA
        """
        tweet_media_pairs = [
            {"tweet_id": tweet_id, "media_key": media_response["media_key"]}
            for media_response in media_responses
        ]
        self.bulk_create_from_responses(
            media_responses, saved_tweet_media_keys, tweet_media_pairs
        )

    def bulk_create_from_responses(
        self,
        media_responses: list[MediaResponseData],
        saved_tweet_media_keys: set[str],
        tweet_media_pairs: list[TweetMediaPair],
    ) -> None:
        """リストで渡したメディアを保存する。メディアの紐づけ先ツイートが複数の場合こちらを使う。

        media_responses: 保存したいメディア。
        saved_tweet_media_keys: 保存済みのメディアのID、保存済みのメディアをスキップするのに使用する。
        tweet_media_pairs: メディアキー(pk)とそれに紐づくツイートのID(pk)を持った辞書

        【例】
        メディアA -- ツイートA
        メディアB -- ツイートC
        メディアC -- ツイートA
        メディアD -- ツイートB
        """

        media_list = []
        for response in media_responses:
            media_key = response.get("media_key")
            tweet_id = None
            if media_key in saved_tweet_media_keys:
                continue

            for tweet_media_pair in tweet_media_pairs:
                if tweet_media_pair["media_key"] == media_key:
                    tweet_id = tweet_media_pair["tweet_id"]

            media = TweetMedia(
                media_key=media_key,
                tweet_id=tweet_id,
                media_type=response.get("type"),
                url=response.get("url"),
                alt_text=response.get("alt_text"),
                width=response.get("width"),
                height=response.get("height"),
                duration_ms=response.get("duration_ms"),
            )
            media_list.append(media)

        TweetMedia.objects.bulk_create(media_list)


class TweetMedia(models.Model):
    """ツイートのメディア情報(画像・動画)"""

    objects = TweetMediaManager()

    class MediaType(models.TextChoices):
        PHOTO = "photo", "写真"
        VIDEO = "video", "動画"
        GIF = "animated_gif", "gif画像"

    media_key = models.CharField(
        primary_key=True, max_length=50, help_text="mediaのkey"
    )
    tweet = models.ForeignKey(
        "tweets.Tweet",
        on_delete=models.CASCADE,
        related_name="media",
        help_text="紐づくツイート",
    )
    media_type = models.CharField(
        max_length=12, choices=MediaType.choices, help_text="メディアの種類"
    )
    url = models.URLField(blank=True, null=True, help_text="メディアのURL")
    alt_text = models.TextField(
        blank=True,
        null=True,
        help_text="代替テキスト",
    )
    width = models.IntegerField(blank=True, null=True, help_text="メディアの横幅(px)")
    height = models.IntegerField(blank=True, null=True, help_text="メディアの縦幅(px)")
    duration_ms = models.IntegerField(
        blank=True, null=True, help_text="動画の長さ(ミリ秒)"
    )

    class Meta:
        db_table = "tweet_media"
