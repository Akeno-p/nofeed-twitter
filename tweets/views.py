import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from common.utils import _request_with_token_refresh
from common.x_api import (
    TWITTER_GET_TWEET_ENDPOINT,
    TWITTER_TWEET_ENDPOINT,
    TWITTER_USER_TWEETS_ENDPOINT,
)
from tweets.models import Tweet


@login_required
def tweets_view(request):
    my_tweets = list(
        Tweet.objects.filter(author=request.user.user_id)
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
def reply_view(request):
    return render(
        request,
        "tweets/reply.html",
    )


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

    def get_all_tweets(request):
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

    request_status, get_all_tweets_result = _request_with_token_refresh(
        request, get_all_tweets, 200
    )

    if request_status == "error":
        return JsonResponse(get_all_tweets_result)

    all_tweets_list = get_all_tweets_result.json().get("data")

    saved_tweet_list = list(
        Tweet.objects.filter(author=request.user.user_id).values_list("id", flat=True)
    )

    for tweet in all_tweets_list:
        tweet_id = int(tweet.get("id"))

        if tweet_id in saved_tweet_list:
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
        tweet.save()

    return JsonResponse({"status": "success"})
