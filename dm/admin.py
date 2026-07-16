from django.contrib import admin
from .models import Conversation, DirectMessage, DirectMessageMedia

admin.site.register(Conversation)
admin.site.register(DirectMessage)
admin.site.register(DirectMessageMedia)
