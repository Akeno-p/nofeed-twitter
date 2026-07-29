from django.shortcuts import render


def api_usage_view(request):
    return render(request, "api_usage/api_usage.html")
