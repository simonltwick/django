# Generated by Django 2.2.20 on 2021-05-24 10:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bike', '0036_maintenanceactionhistory_bike'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceaction',
            name='due_distance',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
