from django.shortcuts import render


def tweets_view(request):
    return render(request, "tweets/tweets.html")
