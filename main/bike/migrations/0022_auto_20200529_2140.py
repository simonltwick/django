# Generated by Django 2.2.12 on 2020-05-29 20:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bike', '0021_odometer_rider'),
    ]

    operations = [
        migrations.RenameField(
            model_name='odometer',
            old_name='reading_time',
            new_name='date',
        ),
    ]
