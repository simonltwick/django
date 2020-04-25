from django.contrib import admin
from .models import Network, Team, Game, Line, GameLineParameters

admin.site.register(Network)
admin.site.register(Team)
admin.site.register(Line)
admin.site.register(Game)
admin.site.register(GameLineParameters)
# admin.site.register(LineLocation)
