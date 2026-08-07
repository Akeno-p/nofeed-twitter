import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from common.utils import _update_tokens
from common.x_api import TWITTER_TWEET_ENDPOINT, TWITTER_USER_TWEETS_ENDPOINT
from tweets.models import Tweet


@login_required
def tweets_view(request):
    return render(
        request,
        "tweets/tweets.html",
    )


@login_required
def reply_view(request):
    return render(
        request,
        "tweets/reply.html",
    )


@login_required
def tweet(request):
    tweet_text = request.POST.get("tweetText")

    tweet_response = requests.post(
        TWITTER_TWEET_ENDPOINT,
        headers={"Authorization": f"Bearer {request.user.access_token}"},
        json={"text": tweet_text},
    )

    if tweet_response.status_code == 401:
        is_update_tokens = _update_tokens(request)

        if not is_update_tokens:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "アクセストークンの更新に失敗しました。",
                    "error_code": tweet_response.status_code,
                }
            )

        tweet_response = requests.post(
            TWITTER_TWEET_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            json={"text": tweet_text},
        )

    if tweet_response.status_code != 201:
        return JsonResponse(
            {
                "status": "error",
                "message": "想定外のエラーが発生しました。",
                "error_code": tweet_response.status_code,
            }
        )

    return JsonResponse({"status": "success"})


@login_required
def save_all_tweets(request):
    all_tweets_response = _get_all_tweets(request)

    if all_tweets_response.status_code == 401:
        is_update_tokens = _update_tokens(request)
        if not is_update_tokens:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "アクセストークンの更新に失敗しました。",
                    "error_code": all_tweets_response.status_code,
                }
            )
        all_tweets_response = _get_all_tweets(request)

    if all_tweets_response.status_code != 200:
        return JsonResponse(
            {
                "status": "error",
                "message": "想定外のエラーが発生しました。",
                "error_code": all_tweets_response.status_code,
            }
        )

    all_tweets_list = all_tweets_response.json().get("data")

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


def _get_all_tweets(request):
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
