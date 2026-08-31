import json
import logging
import re

import requests
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from common.utils import request_with_token_refresh, update_tokens
from common.x_api import (
    TWITTER_GET_TWEET_ENDPOINT,
    TWITTER_MEDIA_ENDPOINT,
    TWITTER_SEARCH_RECENT_ENDPOINT,
    TWITTER_TWEET_ENDPOINT,
    TWITTER_USER_TWEETS_ENDPOINT,
    TWITTER_USERS_ENDPOINT,
)
from common.x_api_client import post_media_request, post_tweet_request
from tweets.models import Tweet, TweetMedia
from users.models import User

logger = logging.getLogger(__name__)


@login_required
def tweets_view(request):
    my_tweets = list(Tweet.objects.my_tweets(request.user))

    for tweet in my_tweets:
        tweet.strip_media_link()
        tweet.set_display_created_at()

    return render(request, "tweets/tweets.html", {"my_tweets": my_tweets})


@login_required
def post_tweet(request):
    """ツイートボタンを押した時の処理"""
    tweet_text = request.POST.get("tweetText")
    images_list = request.FILES.getlist("images")

    media_ids = []

    for image in images_list:
        image_status, image_result = request_with_token_refresh(
            request, post_media_request, image
        )
        if image_status == "error":
            return JsonResponse(image_result)

        media_ids.append(image_result.json()["data"]["id"])

    payload = {"text": tweet_text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    status, result = request_with_token_refresh(request, post_tweet_request, payload)

    if status == "error":
        return JsonResponse(result)

    # 手元のデータからでも保存する値は組み立てられるが、処理が複雑になるのと、
    # 実際のデータとずれるリスクもあるため、APIから取り直す形にしています。
    tweet_id = result.json().get("data").get("id")

    def get_tweet():
        get_tweet_response = requests.get(
            TWITTER_GET_TWEET_ENDPOINT.format(tweet_id=tweet_id),
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            params={
                "post.fields": "created_at,author_id,conversation_id,referenced_tweets,attachments",
                "expansions": "attachments.media_keys",
                "media.fields": "url,type,alt_text,width,height,duration_ms",
            },
        )

        return get_tweet_response

    get_tweet_status, get_tweet_result = request_with_token_refresh(
        request,
        get_tweet,
    )

    if get_tweet_status == "error":
        return JsonResponse(get_tweet_result)

    created_tweet = get_tweet_result.json().get("data")

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

    tweet_media_list = get_tweet_result.json().get("includes", {}).get("media", [])

    media_list = []

    for tweet_media in tweet_media_list:
        media = TweetMedia(
            media_key=tweet_media.get("media_key"),
            tweet=tweet,
            media_type=tweet_media.get("type"),
            url=tweet_media.get("url"),
            alt_text=tweet_media.get("alt_text"),
            width=tweet_media.get("width"),
            height=tweet_media.get("height"),
            duration_ms=tweet_media.get("duration_ms"),
        )
        media_list.append(media)

    TweetMedia.objects.bulk_create(media_list)

    # tweetのcreated_atをstrからdatetimeに更新するため
    tweet.refresh_from_db()
    tweet.strip_media_link()
    tweet.set_display_created_at()

    html = render_to_string("tweets/_tweets.html", {"tweet": tweet})

    return JsonResponse({"status": "success", "html": html})


@login_required
def save_all_tweets(request):
    """ツイート全件取得ボタンを押した時の処理"""
    all_tweets_list = []
    all_tweets_media_list = []
    next_token = None

    def get_all_tweets():
        params = {
            "max_results": 100,
            "post.fields": "created_at,author_id,conversation_id,referenced_tweets,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "url,type,alt_text,width,height,duration_ms",
        }
        if next_token:
            params["pagination_token"] = next_token

        response = requests.get(
            TWITTER_USER_TWEETS_ENDPOINT.format(user_id=request.user.user.id),
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            # 最大100件までしか取得できない
            params=params,
        )

        return response

    while True:
        status, result = request_with_token_refresh(
            request,
            get_all_tweets,
        )

        if status == "error":
            return JsonResponse(result)

        body = result.json()
        all_tweets_list.extend(body["data"])
        all_tweets_media_list.extend(body.get("includes").get("media", []))
        next_token = body["meta"].get("next_token")

        if not next_token:
            break

    saved_tweet_ids = set(
        Tweet.objects.filter(author=request.user.user_id).values_list("id", flat=True)
    )
    saved_tweet_media_keys = set(TweetMedia.objects.values_list("media_key", flat=True))

    tweets_list = []
    media_list = []
    tweets_media_keys = []

    for tweet_response in all_tweets_list:
        tweet_id = int(tweet_response.get("id"))

        if tweet_id in saved_tweet_ids:
            continue

        in_reply_to_tweet_id = None
        in_quoted_to_tweet_id = None

        referenced_tweet_list = tweet_response.get("referenced_tweets")

        if referenced_tweet_list is not None:
            for referenced_tweet in referenced_tweet_list:
                referenced_tweet_type = referenced_tweet.get("type")

                if referenced_tweet_type == "quoted":
                    in_quoted_to_tweet_id = referenced_tweet.get("id")
                elif referenced_tweet_type == "replied_to":
                    in_reply_to_tweet_id = referenced_tweet.get("id")

        tweet = Tweet(
            id=tweet_id,
            author_id=tweet_response.get("author_id"),
            text=tweet_response.get("text"),
            created_at=tweet_response.get("created_at"),
            conversation_id=tweet_response.get("conversation_id"),
            in_reply_to_tweet_id=in_reply_to_tweet_id,
            in_quoted_to_tweet_id=in_quoted_to_tweet_id,
        )
        tweets_list.append(tweet)
        media_keys = tweet_response.get("attachments", {}).get("media_keys", [])
        for media_key in media_keys:
            tweets_media_keys.append({"tweet_id": tweet_id, "media_key": media_key})

    Tweet.objects.bulk_create(tweets_list)

    for tweet_media in all_tweets_media_list:
        this_tweet_id = None
        tweet_media_key = tweet_media.get("media_key")
        if tweet_media_key in saved_tweet_media_keys:
            continue

        for m_k_dict in tweets_media_keys:
            if m_k_dict["media_key"] == tweet_media_key:
                this_tweet_id = m_k_dict["tweet_id"]

        media = TweetMedia(
            media_key=tweet_media.get("media_key"),
            tweet_id=this_tweet_id,
            media_type=tweet_media.get("type"),
            url=tweet_media.get("url"),
            alt_text=tweet_media.get("alt_text"),
            width=tweet_media.get("width"),
            height=tweet_media.get("height"),
            duration_ms=tweet_media.get("duration_ms"),
        )
        media_list.append(media)

    TweetMedia.objects.bulk_create(media_list)

    my_tweets = list(
        Tweet.objects.filter(
            author=request.user.user_id, in_reply_to_tweet_id__isnull=True
        )
        .select_related("author")
        .prefetch_related("media")
        .order_by("-created_at")
    )

    for tweet in my_tweets:
        tweet.strip_media_link()
        tweet.set_display_created_at()

    html = render_to_string(
        "tweets/_tweets_list.html", {"my_tweets": my_tweets}, request=request
    )

    return JsonResponse({"status": "success", "html": html})


@login_required
def replies_view(request):
    my_tweets = list(
        Tweet.objects.filter(
            author=request.user.user_id,
            in_reply_to_tweet_id__isnull=True,
        )
        .prefetch_related("media")
        .order_by("-created_at")
    )

    my_replies = list(
        Tweet.objects.filter(
            author=request.user.user_id,
            in_reply_to_tweet_id__isnull=False,
        )
        .select_related("author")
        .prefetch_related("media")
        .order_by("-created_at")
    )

    tweet_ids = [tweet.id for tweet in my_tweets]

    replies = list(
        Tweet.objects.filter(in_reply_to_tweet_id__in=tweet_ids)
        .exclude(author=request.user.user_id)
        .select_related("author")
        .prefetch_related("media")
        .order_by("-created_at")
    )

    tweets_by_id = {tweet.id: tweet for tweet in my_tweets}
    my_reply_by_parent_tweet_id = {
        tweet.in_reply_to_tweet_id: tweet for tweet in my_replies
    }

    for reply in replies:
        parent_tweet = tweets_by_id[reply.in_reply_to_tweet_id]
        my_reply = my_reply_by_parent_tweet_id.get(reply.id)

        _decorate_reply(reply, parent_tweet, my_reply)

    return render(request, "tweets/replies.html", {"replies": replies})


def _decorate_reply(
    base_reply: Tweet, parent_tweet: Tweet, my_reply: Tweet | None = None
):
    """repliesページの表示用にデータを成形する。

    base_reply : 主役のリプライ
    parent_tweet : 主役のリプライの送信元ツイート
    my_reply : 主役リプライに対しての自分のリプライ(未返信の場合はNone)
    """
    base_reply.text = _strip_leading_mentions(base_reply.text)
    base_reply.strip_media_link()
    base_reply.set_display_created_at()
    base_reply.in_reply_to_tweet_text = _strip_leading_mentions(
        parent_tweet.text
    ).rsplit(" https://t.co", 1)[0]

    parent_tweet_media_list = [media.url for media in parent_tweet.media.all()]

    base_reply.in_reply_to_tweet_media_list = json.dumps(parent_tweet_media_list)

    if my_reply:
        my_reply.strip_media_link()
        my_reply.set_display_created_at()
        base_reply.my_reply = my_reply
        base_reply.my_reply.display_text = _strip_leading_mentions(
            base_reply.my_reply.text
        )


def _strip_leading_mentions(text):
    """replyのテキストのusernameを除去する。

    例
    変換前 (@username リプライです。)
    変換後 (リプライです。)
    """
    return re.sub(r"^@\w+\s+", "", text)


def post_reply(request):
    """リプライ返信ボタンを押した時の処理"""
    reply_text = request.POST.get("replyText")
    reply_id = request.POST.get("replyId")
    images_list = request.FILES.getlist("images")

    media_ids = []

    for image in images_list:
        image_status, image_result = request_with_token_refresh(
            request, post_media_request, image
        )
        if image_status == "error":
            return JsonResponse(image_result)

        media_ids.append(image_result.json()["data"]["id"])

    payload = {"text": reply_text, "reply": {"in_reply_to_tweet_id": reply_id}}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    post_reply_status, post_reply_result = request_with_token_refresh(
        request, post_tweet_request, payload
    )

    if post_reply_status == "error":
        return JsonResponse(post_reply_result)

    posted_reply_id = post_reply_result.json().get("data").get("id")

    def get_reply():
        get_reply_response = requests.get(
            TWITTER_GET_TWEET_ENDPOINT.format(tweet_id=posted_reply_id),
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            params={
                "post.fields": "created_at,author_id,conversation_id,referenced_tweets",
                "expansions": "attachments.media_keys",
                "media.fields": "url,type,alt_text,width,height,duration_ms",
            },
        )
        return get_reply_response

    get_reply_status, get_reply_result = request_with_token_refresh(
        request,
        get_reply,
    )

    if get_reply_status == "error":
        return JsonResponse(get_reply_result)

    body = get_reply_result.json()
    created_reply_list = [body.get("data")]
    created_reply_media_list = body.get("includes", {}).get("media", [])

    save_replies_status, save_replies_result = _save_replies(
        request, created_reply_list, created_reply_media_list
    )

    if save_replies_status == "error":
        return JsonResponse(save_replies_result)

    my_reply = Tweet.objects.get(id=posted_reply_id)
    reply = Tweet.objects.get(id=reply_id)
    parent_tweet = Tweet.objects.get(id=reply.in_reply_to_tweet_id)
    _decorate_reply(reply, parent_tweet, my_reply)

    html = render_to_string("tweets/_replies.html", {"reply": reply})

    return JsonResponse({"status": "success", "html": html})


def save_all_replies(request):
    """リプライ全件取得ボタンを押した時の処理"""
    all_replies_list = []
    all_replies_media_list = []
    next_token = None

    my_tweet_ids = Tweet.objects.filter(
        author=request.user.user_id, in_reply_to_tweet_id__isnull=True
    ).values_list("id", flat=True)

    last_reply_id = (
        Tweet.objects.filter(conversation_id__in=my_tweet_ids)
        .exclude(author=request.user.user_id)
        .aggregate(last_id=Max("id"))["last_id"]
    )
    last_reply = Tweet.objects.filter(id=last_reply_id).first()
    if last_reply:
        last_reply_created_at = last_reply.created_at
        last_reply_created_at = timezone.localtime(last_reply_created_at)
        last_reply_created_at_display = last_reply_created_at.strftime("%Y年%m月%d日")

    params = {
        "query": f"to:{request.user.user.username} -is:retweet -from:{request.user.user.username}",
        "max_results": 100,
        "post.fields": "created_at,author_id,conversation_id,referenced_tweets",
        "expansions": "attachments.media_keys",
        "media.fields": "url,type,alt_text,width,height,duration_ms",
        "since_id": last_reply_id,
    }

    def get_replies():
        if next_token:
            params["pagination_token"] = next_token

        response = requests.get(
            TWITTER_SEARCH_RECENT_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            params=params,
        )

        return response

    status, message = "success", None

    while True:
        response = get_replies()

        if response.status_code == 401:
            if not update_tokens(request):
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "アクセストークンの更新に失敗しました。",
                        "error_code": response.status_code,
                    }
                )
            else:
                response = get_replies()

        if response.status_code == 400:
            error_message = response.json().get("errors")[0].get("message")
            SINCE_ID_TOO_OLD_MESSAGE = "'since_id' must be a tweet id created after"

            if SINCE_ID_TOO_OLD_MESSAGE in error_message:
                del params["since_id"]
                response = get_replies()

                if response.status_code == 401:
                    if not update_tokens(request):
                        return JsonResponse(
                            {
                                "status": "error",
                                "message": "アクセストークンの更新に失敗しました。",
                                "error_code": response.status_code,
                            }
                        )
                    else:
                        response = get_replies()
                status, message = (
                    "partial",
                    (
                        "Xの仕様により、取得できるのは直近7日分のリプライのみです。"
                        f"保存されている最新のリプライは{last_reply_created_at_display}のものなので、"
                        "それ以降に届いたリプライの一部が取得できていない可能性があります。"
                    ),
                )
            else:
                logger.error(
                    "APIリクエスト失敗: status=%s body=%s",
                    response.status_code,
                    response.text,
                )
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "想定外のエラーが発生しました。",
                        "error_code": response.status_code,
                    }
                )

        if response.status_code != 200:
            logger.error(
                "APIリクエスト失敗: status=%s body=%s",
                response.status_code,
                response.text,
            )
            return JsonResponse(
                {
                    "status": "error",
                    "message": "想定外のエラーが発生しました。",
                    "error_code": response.status_code,
                }
            )

        body = response.json()
        replies = body.get("data")
        if replies:
            all_replies_list.extend(replies)
        next_token = body["meta"].get("next_token")

        all_replies_media_list.extend(body.get("includes", {}).get("media", []))

        if not next_token:
            break

    if all_replies_list is not None:
        save_replies_status, save_replies_result = _save_replies(
            request, all_replies_list, all_replies_media_list
        )

        if save_replies_status == "error":
            return JsonResponse(save_replies_result)

    my_tweets = list(
        Tweet.objects.filter(
            author=request.user.user_id,
            in_reply_to_tweet_id__isnull=True,
        ).order_by("-created_at")
    )

    my_replies = list(
        Tweet.objects.filter(
            author=request.user.user_id,
            in_reply_to_tweet_id__isnull=False,
        )
        .select_related("author")
        .order_by("-created_at")
    )

    tweet_ids = [tweet.id for tweet in my_tweets]

    replies = list(
        Tweet.objects.filter(in_reply_to_tweet_id__in=tweet_ids)
        .exclude(author=request.user.user_id)
        .select_related("author")
        .prefetch_related("media")
        .order_by("-created_at")
    )

    tweets_by_id = {tweet.id: tweet for tweet in my_tweets}
    my_reply_by_parent_tweet_id = {
        tweet.in_reply_to_tweet_id: tweet for tweet in my_replies
    }

    for reply in replies:
        parent_tweet = tweets_by_id[reply.in_reply_to_tweet_id]
        my_reply = my_reply_by_parent_tweet_id.get(reply.id)

        _decorate_reply(reply, parent_tweet, my_reply)

    html = render_to_string(
        "tweets/_replies_list.html", {"replies": replies}, request=request
    )

    return JsonResponse({"status": status, "message": message, "html": html})


def _save_replies(request, replies_response_list, replies_media_response_list):
    """保存したいreplyのレスポンスをリストにして渡すと、渡したreplyが保存される。

    戻り値は、
    第一引数にstatus : error or success
    第二引数にerrorの場合はerror詳細 successの場合はNone
    """
    replies_list = []
    media_list = []
    replies_media_list = []
    not_saved_user_ids = []
    saved_all_tweet_ids = set(Tweet.objects.values_list("id", flat=True))
    saved_all_tweet_media_ids = set(
        TweetMedia.objects.values_list("media_key", flat=True)
    )
    saved_user_ids = set(User.objects.values_list("id", flat=True))
    for reply_response in replies_response_list:
        reply_id = int(reply_response.get("id"))
        author_id = int(reply_response.get("author_id"))

        if author_id not in saved_user_ids:
            not_saved_user_ids.append(author_id)

        media_keys = reply_response.get("attachments", {}).get("media_keys", [])
        for media_key in media_keys:
            replies_media_list.append({"tweet_id": reply_id, "media_key": media_key})

        in_reply_to_tweet_id = None
        in_quoted_to_tweet_id = None

        referenced_tweet_list = reply_response.get("referenced_tweets")

        if referenced_tweet_list is not None:
            for referenced_tweet in referenced_tweet_list:
                referenced_tweet_type = referenced_tweet.get("type")

                if referenced_tweet_type == "quoted":
                    in_quoted_to_tweet_id = referenced_tweet.get("id")
                elif referenced_tweet_type == "replied_to":
                    in_reply_to_tweet_id = referenced_tweet.get("id")

        if reply_id not in saved_all_tweet_ids:
            reply = Tweet(
                id=reply_id,
                author_id=reply_response.get("author_id"),
                text=reply_response.get("text"),
                created_at=reply_response.get("created_at"),
                conversation_id=reply_response.get("conversation_id"),
                in_reply_to_tweet_id=in_reply_to_tweet_id,
                in_quoted_to_tweet_id=in_quoted_to_tweet_id,
            )
            replies_list.append(reply)

    if not_saved_user_ids:
        save_users_status, save_users_result = _save_users(request, not_saved_user_ids)

        if save_users_status == "error":
            return save_users_status, save_users_result

    Tweet.objects.bulk_create(replies_list)

    for tweet_media in replies_media_response_list:
        this_tweet_id = None
        tweet_media_key = tweet_media.get("media_key")
        if tweet_media_key in saved_all_tweet_media_ids:
            continue

        for m_k_dict in replies_media_list:
            if m_k_dict["media_key"] == tweet_media_key:
                this_tweet_id = m_k_dict["tweet_id"]

        media = TweetMedia(
            media_key=tweet_media.get("media_key"),
            tweet_id=this_tweet_id,
            media_type=tweet_media.get("type"),
            url=tweet_media.get("url"),
            alt_text=tweet_media.get("alt_text"),
            width=tweet_media.get("width"),
            height=tweet_media.get("height"),
            duration_ms=tweet_media.get("duration_ms"),
        )
        media_list.append(media)
    TweetMedia.objects.bulk_create(media_list)

    return "success", None


def _get_users(request, user_ids):
    """取得したいuserのidをリストで渡すとuserの情報が取得される"""

    def users_request():
        users_response = requests.get(
            TWITTER_USERS_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            params={
                "ids": ",".join(str(user_id) for user_id in user_ids),
                "user.fields": "profile_image_url",
            },
        )
        return users_response

    return request_with_token_refresh(request, users_request)


def _save_users(request, user_ids):
    """保存したいuserのidをリストで渡すとuserの情報が保存される"""
    user_info_status, user_info_result = _get_users(request, user_ids)

    if user_info_status == "error":
        return user_info_result

    not_saved_user_info_list = user_info_result.json().get("data")

    not_saved_users = []
    for user_info in not_saved_user_info_list:
        user = User(
            id=user_info.get("id"),
            username=user_info.get("username"),
            name=user_info.get("name"),
            profile_image_url=user_info.get("profile_image_url"),
        )
        not_saved_users.append(user)

    User.objects.bulk_create(not_saved_users)

    return "success", None
