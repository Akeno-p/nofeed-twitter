from __future__ import annotations

from django.db import models
from django.utils import timezone

from common.x_api_client import TweetResponseData


class TweetManager(models.Manager):
    def my_tweets(self, account):
        """自分のツイート(リプライを除く)を新しい順で返す"""
        return (
            self.filter(author=account.user_id, in_reply_to_tweet_id__isnull=True)
            .select_related("author")
            .prefetch_related("media")
            .order_by("-created_at")
        )

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


class TweetMedia(models.Model):
    """ツイートのメディア情報(画像・動画)"""

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
