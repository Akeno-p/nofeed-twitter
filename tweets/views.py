import requests
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from common.utils import _request_with_token_refresh
from common.x_api import (
    TWITTER_GET_TWEET_ENDPOINT,
    TWITTER_SEARCH_RECENT_ENDPOINT,
    TWITTER_TWEET_ENDPOINT,
    TWITTER_USER_TWEETS_ENDPOINT,
    TWITTER_USERS_ENDPOINT,
)
from tweets.models import Tweet
from users.models import User


@login_required
def tweets_view(request):
    my_tweets = list(
        Tweet.objects.filter(
            author=request.user.user_id, in_reply_to_tweet_id__isnull=True
        )
        .select_related("author")
        .order_by("-created_at")
    )

    for tweet in my_tweets:
        _set_display_created_at(tweet)

    return render(request, "tweets/tweets.html", {"my_tweets": my_tweets})


def _set_display_created_at(tweet):
    """ツイートに、一覧表示用の作成日時を display_created_at としてセットする。

    表示形式は投稿日時によって変わる。
    当日は「3分」「5時間」、同じ年は「8月2日」、それ以外は「2025年8月2日」。

    戻り値はなく、渡された tweet を直接書き換える。
    """
    now = timezone.localtime()
    now_date = now.strftime("%Y年%m月%d日")
    now_year = now.strftime("%Y年")
    local_created = timezone.localtime(tweet.created_at)
    created_date = local_created.strftime("%Y年%m月%d日")
    created_year = local_created.strftime("%Y年")

    if now_date == created_date:
        diff_time = now - local_created
        diff_total_seconds = diff_time.total_seconds()
        diff_hours = int(diff_total_seconds // 3600)
        diff_minutes = int(diff_total_seconds % 3600 // 60)

        if diff_hours == 0:
            relative_time = f"{diff_minutes}分"
        else:
            relative_time = f"{diff_hours}時間"
        tweet.display_created_at = relative_time
        return

    if now_year == created_year:
        # strftimeを使用すると08月02日のように0埋めになってしまうため
        month_day = f"{local_created.month}月{local_created.day}日"
        tweet.display_created_at = month_day
        return

    tweet.display_created_at = created_date


@login_required
def tweet(request):
    tweet_text = request.POST.get("tweetText")

    def tweet_request():
        tweet_response = requests.post(
            TWITTER_TWEET_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            json={"text": tweet_text},
        )
        return tweet_response

    tweet_status, tweet_result = _request_with_token_refresh(
        request, tweet_request, 201
    )

    if tweet_status == "error":
        return JsonResponse(tweet_result)

    def get_tweet():
        get_tweet_response = requests.get(
            TWITTER_GET_TWEET_ENDPOINT.format(tweet_id=tweet_id),
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            params={
                "post.fields": "created_at,author_id,conversation_id,referenced_tweets",
            },
        )

        return get_tweet_response

    tweet_id = tweet_result.json().get("data").get("id")

    get_tweet_status, get_tweet_result = _request_with_token_refresh(
        request, get_tweet, 200
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

    # tweetのcreated_atをstrからdatetimeに更新するため
    tweet.refresh_from_db()

    _set_display_created_at(tweet)

    html = render_to_string("tweets/_tweets.html", {"tweet": tweet})

    return JsonResponse({"status": "success", "html": html})


@login_required
def save_all_tweets(request):

    def get_all_tweets():
        all_tweets_response = requests.get(
            TWITTER_USER_TWEETS_ENDPOINT.format(user_id=request.user.user.id),
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            # 最大100件までしか取得できない
            params={
                "max_results": 100,
                "post.fields": "created_at,author_id,conversation_id,referenced_tweets",
            },
        )

        return all_tweets_response

    get_all_tweets_status, get_all_tweets_result = _request_with_token_refresh(
        request, get_all_tweets, 200
    )

    if get_all_tweets_status == "error":
        return JsonResponse(get_all_tweets_result)

    all_tweets_list = get_all_tweets_result.json().get("data")

    saved_tweet_ids = set(
        Tweet.objects.filter(author=request.user.user_id).values_list("id", flat=True)
    )

    tweets_list = []

    for tweet in all_tweets_list:
        tweet_id = int(tweet.get("id"))

        if tweet_id in saved_tweet_ids:
            continue

        in_reply_to_tweet_id = None
        in_quoted_to_tweet_id = None

        referenced_tweet_list = tweet.get("referenced_tweets")

        if referenced_tweet_list is not None:
            for referenced_tweet in referenced_tweet_list:
                referenced_tweet_type = referenced_tweet.get("type")

                if referenced_tweet_type == "quoted":
                    in_quoted_to_tweet_id = referenced_tweet.get("id")
                elif referenced_tweet_type == "replied_to":
                    in_reply_to_tweet_id = referenced_tweet.get("id")

        tweet = Tweet(
            id=tweet_id,
            author_id=tweet.get("author_id"),
            text=tweet.get("text"),
            created_at=tweet.get("created_at"),
            conversation_id=tweet.get("conversation_id"),
            in_reply_to_tweet_id=in_reply_to_tweet_id,
            in_quoted_to_tweet_id=in_quoted_to_tweet_id,
        )
        tweets_list.append(tweet)

    Tweet.objects.bulk_create(tweets_list)
    return JsonResponse({"status": "success"})


@login_required
def replies_view(request):
    my_tweets = list(
        Tweet.objects.filter(
            author=request.user.user_id,
            in_reply_to_tweet_id__isnull=True,
        ).order_by("-created_at")
    )

    tweet_ids = [tweet.id for tweet in my_tweets]

    replies = list(
        Tweet.objects.filter(in_reply_to_tweet_id__in=tweet_ids)
        .select_related("author")
        .order_by("-created_at")
    )

    for reply in replies:
        _set_display_created_at(reply)

        in_reply_to_text = Tweet.objects.get(id=reply.in_reply_to_tweet_id).text
        reply.in_reply_to_text = in_reply_to_text

    return render(request, "tweets/replies.html", {"replies": replies})


def reply(request):
    reply_text = request.POST.get("replyText")
    in_reply_to_tweet_id = request.POST.get("replyId")

    def reply_request():
        reply_response = requests.post(
            TWITTER_TWEET_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            json={
                "text": reply_text,
                "reply": {"in_reply_to_tweet_id": in_reply_to_tweet_id},
            },
        )
        return reply_response

    reply_status, reply_result = _request_with_token_refresh(
        request, reply_request, 201
    )

    if reply_status == "error":
        return JsonResponse(reply_result)

    return JsonResponse({"status": "success"})


def save_replies(request):

    my_tweet_ids = Tweet.objects.filter(
        author=request.user.user_id, in_reply_to_tweet_id__isnull=True
    ).values_list("id", flat=True)

    last_reply_id = (
        Tweet.objects.filter(conversation_id__in=my_tweet_ids)
        .exclude(author=request.user.user_id)
        .aggregate(last_id=Max("id"))["last_id"]
    )

    def get_replies():
        replies_response = requests.get(
            TWITTER_SEARCH_RECENT_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            params={
                "query": f"to:{request.user.user.username} -is:retweet -from:{request.user.user.username}",
                "max_results": 100,
                "post.fields": "created_at,author_id,conversation_id,referenced_tweets",
                "since_id": last_reply_id,
            },
        )

        return replies_response

    replies_status, replies_result = _request_with_token_refresh(
        request, get_replies, 200
    )

    if replies_status == "error":
        JsonResponse(replies_result)

    replies_response_list = replies_result.json().get("data")

    replies_list = []
    not_saved_user_ids = []
    all_tweet_ids = set(Tweet.objects.values_list("id", flat=True))
    saved_user_ids = set(User.objects.values_list("id", flat=True))

    for reply in replies_response_list:
        author_id = int(reply.get("author_id"))

        if author_id not in saved_user_ids:
            not_saved_user_ids.append(author_id)

        in_reply_to_tweet_id = None
        in_quoted_to_tweet_id = None

        referenced_tweet_list = reply.get("referenced_tweets")

        if referenced_tweet_list is not None:
            for referenced_tweet in referenced_tweet_list:
                referenced_tweet_type = referenced_tweet.get("type")

                if referenced_tweet_type == "quoted":
                    in_quoted_to_tweet_id = referenced_tweet.get("id")
                elif referenced_tweet_type == "replied_to":
                    in_reply_to_tweet_id = referenced_tweet.get("id")

        reply_id = int(reply.get("id"))
        if reply_id not in all_tweet_ids:
            reply = Tweet(
                id=reply_id,
                author_id=reply.get("author_id"),
                text=reply.get("text"),
                created_at=reply.get("created_at"),
                conversation_id=reply.get("conversation_id"),
                in_reply_to_tweet_id=in_reply_to_tweet_id,
                in_quoted_to_tweet_id=in_quoted_to_tweet_id,
            )
        replies_list.append(reply)

    if not_saved_user_ids:
        save_users_status, save_users_result = _save_users(request, not_saved_user_ids)

        if save_users_status == "error":
            return JsonResponse(save_users_result)

    print(replies_list)

    Tweet.objects.bulk_create(replies_list)

    return JsonResponse({"status": "success"})


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

    return _request_with_token_refresh(request, users_request, 200)


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
