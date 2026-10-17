# データベース設計

## 設計方針

- PKをDjangoの自動採番によって取得する場合もほかテーブルと記述を揃えるため、明示的にPKを指定しています。
- システム構造上リツイートは見れない設計にしているので、リツイート先のIDを保存するカラムは作成してません。
- 外部キーのon_deleteは基本的にSET_NULLを採用しています。ユーザー情報が削除されてもツイートまで連鎖削除するメリットがほとんどなく、データ量も少ないため残しておいて問題ないと判断しました。
- アクセストークンやTOTP秘密鍵は平文で保存します。DBが流出した場合でも、APIの利用上限はX Developer Portal側で制御されており、その変更にはXアカウントへのログイン（2段階認証あり）が必要なため、実害は限定的と判断しました。リスクが変わった場合は再検討します。
- 逆参照名（related_name）はデフォルトと同じになる場合でも、すべてのリレーションフィールドに明示的に指定します。統一性と可読性を優先するためです。
- AbstractUserから継承されるフィールドのうち、first_name・last_name・email・groups・user_permissionsはこのアプリでは使用しないため、ER図には記載していません。

## ER図

```mermaid
erDiagram
    users ||--o| accounts : "認証情報"
    users ||--o{ tweets:"ツイート"
    tweets ||--o{ tweet_media:"ツイートの写真"

users{
    bigint id PK "ツイッターのユーザーID"
    varchar(100) username "ユーザー名(@の後ろ)"
    varchar(100) name "表示名"
    varchar(URL) profile_image_url "アイコン画像URL"
}

accounts{
    bigint id PK "djangoの自動採番"
    bigint user FK "userを参照"
    text access_token "OAuth 2.0 アクセストークン"
    text refresh_token "OAuth 2.0 リフレッシュトークン"
    text totp_secret "nofeed-twitterの2段階認証用TOTP秘密鍵"
    varchar(150) username "nofeed-twitterのアカウント名(AbstractUserから継承)"
    varchar(128) password "nofeed-twitterのパスワード(AbstractUserから継承)"
    boolean is_active "利用可否(AbstractUserから継承)"
    boolean is_staff "admin画面に入れるか(AbstractUserから継承)"
    boolean is_superuser "全権限を持つか(AbstractUserから継承)"
    datetime last_login "最終ログイン日時(AbstractUserから継承)"
    datetime date_joined "アカウント作成日時(AbstractUserから継承)"
}

tweets{
    bigint id PK "tweetID"
    bigint author FK "Userを参照"
    text text "投稿本文"
    datetime created_at "投稿日時"
    bigint conversation_id "会話の元になっているtweetID"
    bigint in_reply_to_tweet_id "リプライ先のtweetID"
    bigint in_quoted_to_tweet_id "引用元のtweetID"
    }

tweet_media{
    varchar(50) media_key PK "メディアのID"
    bigint tweet FK "紐ずくツイート"
    varchar(12) media_type "メディアの種類"
    varchar url "画像のurl"
    text alt_text "代替テキスト"
    int width "メディアの横幅(px)"
    int height "メディアの縦幅(px)"
    int duration_ms "動画の長さ(ミリ秒)"
}
```
