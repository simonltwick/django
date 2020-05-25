# Generated by Django 2.2.12 on 2020-05-21 10:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0047_auto_20200518_1622'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='placetemplate',
            name='passenger_traffic_percent',
        ),
        migrations.AddField(
            model_name='placetemplate',
            name='passenger_traffic_dir1',
            field=models.PositiveSmallIntegerField(default=100, help_text='Relative peak passenger traffic in direction 1 at this station.'),
        ),
        migrations.AddField(
            model_name='placetemplate',
            name='passenger_traffic_dir2',
            field=models.PositiveSmallIntegerField(default=100, help_text='Relative peak passenger traffic in direction 2 at this station.'),
        ),
    ]