from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def api_usage_view(request):
    return render(request, "api_usage/api_usage.html")
