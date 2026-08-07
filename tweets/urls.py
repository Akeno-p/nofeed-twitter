from django.urls import path

from . import views

urlpatterns = [
    path("", views.tweets_view, name="tweets"),
    path("reply", views.reply_view, name="reply"),
    path("tweet", views.tweet, name="tweet"),
    path("save_all_tweets", views.save_all_tweets, name="save_all_tweets"),
]
