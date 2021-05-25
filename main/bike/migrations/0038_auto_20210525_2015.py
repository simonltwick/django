# Generated by Django 2.2.20 on 2021-05-25 19:15

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bike', '0037_maintenanceaction_due_distance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='maintenanceaction',
            name='completed_date',
            field=models.DateField(blank=True, help_text='legacy', null=True),
        ),
        migrations.AlterField(
            model_name='maintenanceaction',
            name='completed_distance',
            field=models.FloatField(blank=True, help_text='legacy', null=True),
        ),
        migrations.AlterField(
            model_name='maintenanceaction',
            name='distance',
            field=models.FloatField(blank=True, help_text='legacy', null=True),
        ),
        migrations.AlterField(
            model_name='maintenanceaction',
            name='maint_interval_distance_units',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(10, 'miles'), (20, 'kilometres')], null=True),
        ),
        migrations.AlterField(
            model_name='maintenancetype',
            name='maint_interval_distance_units',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(10, 'miles'), (20, 'kilometres')], null=True),
        ),
        migrations.AlterUniqueTogether(
            name='maintenanceaction',
            unique_together={('user', 'bike', 'component', 'maint_type', 'description', 'due_date', 'due_distance')},
        ),
    ]