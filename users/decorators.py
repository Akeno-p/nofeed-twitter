from django.shortcuts import redirect
from functools import wraps


def redirect_to_tweets_if_logged_in(view_func):
    """既にログイン済みならtweetsページに遷移させる"""

    def wrapper(request):
        is_login = request.user.is_authenticated
        if is_login:
            return redirect("tweets")
        return view_func(request)

    return wrapper
