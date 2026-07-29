from django.shortcuts import render

def dm_view(request):
    return render(request, "dm/dm.html")
