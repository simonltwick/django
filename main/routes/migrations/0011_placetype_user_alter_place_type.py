# Generated by Django 5.2.3 on 2025-06-23 09:45

import django.db.models.deletion
import routes.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0010_alter_place_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='placetype',
            name='user',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='place',
            name='type',
            field=models.ForeignKey(default=routes.models.get_default_place_type, on_delete=django.db.models.deletion.SET_DEFAULT, to='routes.placetype'),
        ),
    ]
