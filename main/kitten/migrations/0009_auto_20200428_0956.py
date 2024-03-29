# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-04-28 08:56
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0008_auto_20200428_0955'),
    ]

    operations = [
        migrations.AddField(
            model_name='network',
            name='day_end_time',
            field=models.TimeField(default=datetime.time(22, 0)),
        ),
        migrations.AddField(
            model_name='network',
            name='day_start_time',
            field=models.TimeField(default=datetime.time(6, 0)),
        ),
        migrations.AddField(
            model_name='network',
            name='game_round_duration',
            field=models.DurationField(default=datetime.timedelta(seconds=1800)),
        ),
    ]
