# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-04-27 15:57
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0003_auto_20200427_1542'),
    ]

    operations = [
        migrations.RenameField(
            model_name='network',
            old_name='last_saved',
            new_name='last_updated',
        ),
    ]