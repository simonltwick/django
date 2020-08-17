# Generated by Django 2.2.12 on 2020-05-27 09:30

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bike', '0012_auto_20200522_1044'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity', models.CharField(max_length=200)),
                ('reference_info', models.CharField(max_length=300)),
                ('recurring', models.BooleanField(default=False)),
                ('maintenance_interval', models.PositiveIntegerField(blank=True, null=True)),
                ('maint_interval_units', models.PositiveSmallIntegerField(blank=True, choices=[(101, 'Miles'), (102, 'Kilometres'), (103, 'Days'), (104, 'Years')], null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='componenttype',
            name='maint_interval_units',
        ),
        migrations.RemoveField(
            model_name='componenttype',
            name='maintenance_interval',
        ),
        migrations.RemoveField(
            model_name='componenttype',
            name='maintenance_schedule',
        ),
        migrations.AlterField(
            model_name='maintenanceaction',
            name='activity_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='bike.MaintenanceType'),
        ),
        migrations.DeleteModel(
            name='MaintenanceSchedule',
        ),
        migrations.AddField(
            model_name='maintenancetype',
            name='component_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bike.ComponentType'),
        ),
        migrations.AddField(
            model_name='maintenancetype',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_types', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='componenttype',
            name='maintenance_type',
            field=models.ManyToManyField(to='bike.MaintenanceType'),
        ),
    ]