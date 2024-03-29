# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2020-05-03 11:17
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('kitten', '0027_auto_20200502_1137'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamInvitation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=20)),
                ('invitation_date', models.DateTimeField(auto_now_add=True)),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('invitee_username', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitees', to=settings.AUTH_USER_MODEL)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='kitten.Team')),
            ],
        ),
        migrations.AddField(
            model_name='team',
            name='invitations',
            field=models.ManyToManyField(related_name='invitations', through='kitten.TeamInvitation', to=settings.AUTH_USER_MODEL),
        ),
    ]
