# Generated by Django 2.2.12 on 2020-05-27 22:20

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('bike', '0017_auto_20200527_2319'),
    ]

    operations = [
        migrations.AlterField(
            model_name='odometer',
            name='reading_time',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
