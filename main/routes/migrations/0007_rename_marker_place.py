# Generated by Django 5.2.3 on 2025-06-12 11:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0006_track_raw_gpx_id'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Marker',
            new_name='Place',
        ),
    ]
