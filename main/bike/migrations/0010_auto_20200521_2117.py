# Generated by Django 2.2.12 on 2020-05-21 20:17

import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bike', '0009_auto_20200520_0944'),
    ]

    operations = [
        migrations.AddField(
            model_name='componenttype',
            name='maintenance_schedule',
            field=models.ManyToManyField(to='bike.MaintenanceSchedule'),
        ),
        migrations.AddField(
            model_name='maintenanceaction',
            name='activity_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='bike.MaintenanceSchedule'),
        ),
        migrations.AddField(
            model_name='maintenanceaction',
            name='bike',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='maint_actions', to='bike.Bike'),
        ),
        migrations.AddField(
            model_name='maintenanceaction',
            name='completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='maintenanceaction',
            name='completed_distance',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='maintenanceaction',
            name='description',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='maintenanceaction',
            name='due_date',
            field=models.DateField(blank=True, default=datetime.date.today, null=True),
        ),
        migrations.AlterField(
            model_name='component',
            name='bike',
            field=models.ForeignKey(blank=True, help_text='Leave blank if this is a subcomponent of another part of a bike.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='components', to='bike.Bike'),
        ),
        migrations.AlterField(
            model_name='maintenanceaction',
            name='completed_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='maintenanceaction',
            name='component',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='bike.Component'),
        ),
    ]