# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-05-04 04:55
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0033_gameinvitation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gameinvitation',
            name='game',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='kitten.Game'),
        ),
        migrations.AlterField(
            model_name='gameinvitation',
            name='inviting_team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='kitten.Team'),
        ),
    ]