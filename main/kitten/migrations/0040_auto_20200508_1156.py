# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-05-08 10:56
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0039_auto_20200507_1900'),
    ]

    operations = [
        migrations.AlterField(
            model_name='impact',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(10, 'Line'), (20, 'Passenger'), (25, 'Station'), (30, 'Staff'), (40, 'Cost')], default=10),
        ),
        migrations.AlterField(
            model_name='incident',
            name='response',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='active_incidents', to='kitten.Response'),
        ),
        migrations.AlterField(
            model_name='network',
            name='name',
            field=models.CharField(max_length=40, unique=True),
        ),
        migrations.AlterField(
            model_name='network',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='networks', to=settings.AUTH_USER_MODEL),
        ),
    ]