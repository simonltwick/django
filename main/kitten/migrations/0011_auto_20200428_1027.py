# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-04-28 09:27
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0010_auto_20200428_0957'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='game_round_duration',
            field=models.DurationField(default=datetime.timedelta(seconds=1800)),
        ),
        migrations.AddField(
            model_name='game',
            name='tick_interval',
            field=models.DurationField(default=datetime.timedelta(seconds=60)),
        ),
    ]
