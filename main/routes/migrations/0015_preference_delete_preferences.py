# Generated by Django 5.2.3 on 2025-06-26 13:22

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('routes', '0014_preferences'),
    ]

    operations = [
        migrations.CreateModel(
            name='Preference',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='routes_preferences', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('distance_units', models.IntegerField(choices=[(10, 'Miles'), (20, 'Kilometres')], default=20)),
                ('track_nearby_search_distance', models.FloatField(default=5)),
                ('track_search_result_limit', models.IntegerField(default=100)),
                ('place_nearby_search_distance', models.FloatField(default=20)),
                ('place_search_result_limit', models.IntegerField(default=1000)),
            ],
        ),
        migrations.DeleteModel(
            name='Preferences',
        ),
    ]
