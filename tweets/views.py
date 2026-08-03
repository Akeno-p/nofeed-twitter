import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from common.utils import _update_tokens
from common.x_api import TWITTER_TWEET_ENDPOINT


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
                {"status": "error", "message": "アクセストークンの更新に失敗しました。"}
            )

        tweet_response = requests.post(
            TWITTER_TWEET_ENDPOINT,
            headers={"Authorization": f"Bearer {request.user.access_token}"},
            json={"text": tweet_text},
        )

    if tweet_response.status_code != 201:
        return JsonResponse(
            {"status": "error", "message": "想定外のエラーが発生しました。"}
        )
    
    return JsonResponse({"status": "success"})
