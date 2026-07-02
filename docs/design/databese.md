# データベース設計

```python
class Account(models.Model):
    """自分自身の認証・トークン管理用"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text="Userテーブルへの参照")
    access_token = models.TextField(help_text="OAuth 2.0 アクセストークン")
    refresh_token = models.TextField(blank=True, null=True, help_text="OAuth 2.0 リフレッシュトークン")
    token_expires_at = models.DateTimeField(blank=True, null=True, help_text="アクセストークンの有効期限")
    totp_secret = models.TextField(blank=True, null=True, help_text="TOTP秘密鍵（暗号化）")

    class Meta:
        db_table = "account"


class User(models.Model):
    """表示用のユーザー情報（自分 + 他者）"""
    id = models.BigIntegerField(primary_key=True, help_text="XのユーザーID")
    username = models.CharField(max_length=50, help_text="ユーザー名（@の後ろ）")
    name = models.CharField(max_length=100, help_text="表示名")
    profile_image_url = models.URLField(blank=True, null=True, help_text="アイコン画像URL")

    class Meta:
        db_table = "users"


class Post(models.Model):
    """投稿"""
    id = models.BigIntegerField(primary_key=True, help_text="Tweet ID")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts", help_text="投稿者")
    text = models.TextField(help_text="投稿本文")
    created_at = models.DateTimeField(help_text="投稿日時")
    conversation_id = models.BigIntegerField(blank=True, null=True, help_text="会話ID（スレッド管理用）")
    in_reply_to_tweet_id = models.BigIntegerField(blank=True, null=True, help_text="リプライ先のTweet ID")
    referenced_tweet_type = models.CharField(max_length=20, blank=True, null=True, help_text="replied_to / quoted / retweeted")

    class Meta:
        db_table = "posts"


class Reply(models.Model):
    """リプライ"""
    id = models.BigIntegerField(primary_key=True, help_text="リプライのTweet ID")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="replies", help_text="どの自分の投稿へのリプライか")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="replies", help_text="リプライしたユーザー")
    text = models.TextField(help_text="リプライ本文")
    created_at = models.DateTimeField(help_text="投稿日時")
    conversation_id = models.BigIntegerField(blank=True, null=True, help_text="会話ID")
    in_reply_to_tweet_id = models.BigIntegerField(blank=True, null=True, help_text="リプライ先のTweet ID")

    class Meta:
        db_table = "replies"


class Conversation(models.Model):
    """DMの会話単位"""
    id = models.CharField(max_length=50, primary_key=True, help_text="dm_conversation_id")
    participant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conversations", help_text="DMの相手")
    last_message_at = models.DateTimeField(blank=True, null=True, help_text="最後のメッセージ日時")

    class Meta:
        db_table = "conversations"


class DirectMessage(models.Model):
    """DMメッセージ"""
    id = models.BigIntegerField(primary_key=True, help_text="DMイベントID")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages", help_text="所属する会話")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages", help_text="送信者")
    text = models.TextField(blank=True, null=True, help_text="メッセージ本文")
    created_at = models.DateTimeField(help_text="送信日時")
    event_type = models.CharField(max_length=30, default="MessageCreate", help_text="MessageCreate など")

    class Meta:
        db_table = "direct_messages"


class Media(models.Model):
    """メディア情報（画像・動画）"""
    media_key = models.CharField(max_length=50, primary_key=True, help_text="Xのmedia_key")
    type = models.CharField(max_length=20, help_text="photo / video / animated_gif")
    url = models.URLField(blank=True, null=True, help_text="メディアのURL")
    alt_text = models.TextField(blank=True, null=True, help_text="代替テキスト")
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    duration_ms = models.IntegerField(blank=True, null=True, help_text="動画の場合の長さ（ミリ秒）")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, blank=True, null=True, related_name="media", help_text="紐づく投稿")
    direct_message = models.ForeignKey(DirectMessage, on_delete=models.CASCADE, blank=True, null=True, related_name="media", help_text="紐づくDM")

    class Meta:
        db_table = "media"
```
