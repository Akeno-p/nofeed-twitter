from django.urls import path

from . import views

urlpatterns = [
    path("", views.tweets_view, name="tweets"),
    path("replies", views.replies_view, name="replies"),
    path("post_tweet", views.post_tweet, name="post_tweet"),
    path("save_all_tweets", views.save_all_tweets, name="save_all_tweets"),
    path("post_reply", views.post_reply, name="post_reply"),
    path("save_all_replies", views.save_all_replies, name="save_all_replies"),
]
