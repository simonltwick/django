# Generated by Django 5.2.3 on 2025-06-26 14:59

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0015_preference_delete_preferences'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='track',
            name='ascent',
            field=models.IntegerField(blank=True, help_text='Ascent in metres', null=True),
        ),
        migrations.AddField(
            model_name='track',
            name='end_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='track',
            name='moving_distance',
            field=models.IntegerField(blank=True, help_text='Moving distance in metres', null=True),
        ),
        migrations.AddField(
            model_name='track',
            name='moving_time',
            field=models.IntegerField(blank=True, help_text='Moving time in seconds', null=True),
        ),
        migrations.AddField(
            model_name='track',
            name='start_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='preference',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='routes_preference', serialize=False, to=settings.AUTH_USER_MODEL),
        ),
    ]
