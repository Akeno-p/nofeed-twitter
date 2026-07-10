from django.db import models


class Tweet(models.Model):
    """ツイート"""

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
