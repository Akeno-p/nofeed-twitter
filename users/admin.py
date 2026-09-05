from django.contrib import admin

from .models import Account, XUser

admin.site.register(XUser)
admin.site.register(Account)
