# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-05-05 12:05
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0037_auto_20200505_1222'),
    ]

    operations = [
        migrations.AlterField(
            model_name='incident',
            name='line',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='kitten.Line'),
        ),
    ]