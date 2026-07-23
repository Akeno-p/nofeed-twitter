from django.shortcuts import redirect
from functools import wraps


def redirect_to_tweets_if_logged_in(view_func):
    """既にログイン済みならtweetsページに遷移させる"""

    def wrapper(request):
        if request.user.is_authenticated:
            return redirect("tweets")
        return view_func(request)

    return wrapper


def redirect_to_login_if_no_pending_user(view_func):
    """セッションにpending_user_idがない場合loginページに遷移させる"""

    def wrapper(request):
        if not request.session.get("pending_user_id"):
            return redirect("login")
        return view_func(request)

    return wrapper
