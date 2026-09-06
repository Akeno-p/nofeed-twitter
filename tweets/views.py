import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from common.utils import request_with_token_refresh, update_tokens
from common.x_api_client import (
    MediaResponseData,
    TweetResponseData,
    get_all_tweets,
    get_replies,
    get_tweet,
    get_users,
    post_media_request,
    post_tweet_request,
)
from tweets.models import Tweet, TweetMedia
from users.models import XUser

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
        post_image_status, post_image_result = request_with_token_refresh(
            request, post_media_request, image
        )
        if post_image_status == "error":
            return JsonResponse(post_image_result)

        media_ids.append(post_image_result.json()["data"]["id"])

    payload = {"text": tweet_text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    post_tweet_status, post_tweet_result = request_with_token_refresh(
        request, post_tweet_request, payload
    )

    if post_tweet_status == "error":
        return JsonResponse(post_tweet_result)

    # 手元のデータからでも保存する値は組み立てられるが、処理が複雑になるのと、
    # 実際のデータとずれるリスクもあるため、取り直す形にしています。
    posted_tweet_id = post_tweet_result.json().get("data").get("id")

    get_tweet_status, get_tweet_result = request_with_token_refresh(
        request, get_tweet, posted_tweet_id
    )

    if get_tweet_status == "error":
        return JsonResponse(get_tweet_result)

    created_tweet = get_tweet_result.json().get("data")

    saved_tweet = Tweet.objects.create_from_response(created_tweet)

    media_responses = get_tweet_result.json().get("includes", {}).get("media", [])

    saved_tweet_media_keys = set(TweetMedia.objects.all_tweet_media_keys())
    TweetMedia.objects.bulk_create_for_tweet(
        media_responses, saved_tweet_media_keys, saved_tweet.id
    )

    # tweetのcreated_atをstrからdatetimeに更新するため
    saved_tweet.refresh_from_db()

    saved_tweet.strip_media_link()
    saved_tweet.set_display_created_at()

    html = render_to_string("tweets/_tweets.html", {"tweet": saved_tweet})

    return JsonResponse({"status": "success", "html": html})


@login_required
def save_all_tweets(request):
    """ツイート全件取得ボタンを押した時の処理"""
    all_tweet_responses = []
    all_tweet_media_responses = []
    next_token = None

    while True:
        status, result = request_with_token_refresh(request, get_all_tweets, next_token)

        if status == "error":
            return JsonResponse(result)

        body = result.json()
        all_tweet_responses.extend(body["data"])
        all_tweet_media_responses.extend(body.get("includes", {}).get("media", []))
        next_token = body["meta"].get("next_token")

        if not next_token:
            break

    tweet_media_pairs = Tweet.objects.bulk_create_from_responses(all_tweet_responses)
    TweetMedia.objects.bulk_create_from_responses(
        all_tweet_media_responses, tweet_media_pairs
    )

    my_tweets = list(Tweet.objects.my_tweets(request.user))

    for tweet in my_tweets:
        tweet.strip_media_link()
        tweet.set_display_created_at()

    html = render_to_string(
        "tweets/_tweets_list.html", {"my_tweets": my_tweets}, request=request
    )

    return JsonResponse({"status": "success", "html": html})


@login_required
def replies_view(request):
    """リプライページを開いた時の処理"""
    replies = Tweet.objects.get_decorated_replies(request.user)
    return render(request, "tweets/replies.html", {"replies": replies})


@login_required
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

    get_reply_status, get_reply_result = request_with_token_refresh(
        request, get_tweet, posted_reply_id
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
    reply.decorate_reply(parent_tweet, my_reply)

    html = render_to_string("tweets/_replies.html", {"reply": reply})

    return JsonResponse({"status": "success", "html": html})


@login_required
def save_all_replies(request):
    """リプライ全件取得ボタンを押した時の処理"""
    SINCE_ID_TOO_OLD_MESSAGE = "'since_id' must be a tweet id created after"
    all_replies_list = []
    all_replies_media_list = []
    next_token = None
    since_id = None

    last_reply = Tweet.objects.last_reply(request.user)

    if last_reply:
        since_id = last_reply.id
        last_reply_created_at = last_reply.created_at
        last_reply_created_at = timezone.localtime(last_reply_created_at)
        last_reply_created_at_display = last_reply_created_at.strftime("%Y年%m月%d日")

    status, message = "success", None

    while True:
        response = get_replies(request, next_token, since_id)

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
                response = get_replies(request, next_token, since_id)

        if response.status_code == 400:
            error_message = response.json().get("errors")[0].get("message")

            if SINCE_ID_TOO_OLD_MESSAGE in error_message:
                since_id = None

                status, message = (
                    "partial",
                    (
                        "Xの仕様により、取得できるのは直近7日分のリプライのみです。"
                        f"保存されている最新のリプライは{last_reply_created_at_display}のものなので、"
                        "それ以降に届いたリプライの一部が取得できていない可能性があります。"
                    ),
                )
                continue

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

    if all_replies_list:
        save_replies_status, save_replies_result = _save_replies(
            request, all_replies_list, all_replies_media_list
        )

        if save_replies_status == "error":
            return JsonResponse(save_replies_result)

    replies = Tweet.objects.get_decorated_replies(request.user)

    html = render_to_string(
        "tweets/_replies_list.html", {"replies": replies}, request=request
    )

    return JsonResponse({"status": status, "message": message, "html": html})


@login_required
def _save_replies(
    request,
    replies_response: list[TweetResponseData],
    replies_media_response: list[MediaResponseData],
):
    """保存したいreplyのレスポンスをリストにして渡すと、渡したreplyが保存される。

    戻り値は、
    第一引数にstatus : error or success
    第二引数にerrorの場合はerror詳細 successの場合はNone
    """
    not_saved_user_ids = XUser.objects.not_saved_author_ids(replies_response)

    if not_saved_user_ids:
        status, result = request_with_token_refresh(
            request, get_users, not_saved_user_ids
        )

        if status == "error":
            return status, result

        x_user_responses = result.json()["data"]

        XUser.objects.bulk_create_from_responses(x_user_responses)

    tweet_media_pairs = Tweet.objects.bulk_create_from_responses(replies_response)

    TweetMedia.objects.bulk_create_from_responses(
        replies_media_response, tweet_media_pairs
    )

    return "success", None
