from django.contrib.auth.decorators import login_required
from django.shortcuts import render


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
