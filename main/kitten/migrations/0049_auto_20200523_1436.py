# Generated by Django 2.2.12 on 2020-05-23 13:36

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kitten', '0048_auto_20200521_1143'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='game',
            name='delay',
        ),
        migrations.AlterField(
            model_name='game',
            name='current_time',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='game',
            name='level',
            field=models.PositiveSmallIntegerField(choices=[(10, 'Basic'), (20, 'Intermediate'), (30, 'Advanced'), (40, 'Expert')]),
        ),
        migrations.AlterField(
            model_name='gametemplate',
            name='level',
            field=models.PositiveSmallIntegerField(choices=[(10, 'Basic'), (20, 'Intermediate'), (30, 'Advanced'), (40, 'Expert')]),
        ),
        migrations.AlterField(
            model_name='impact',
            name='one_time_amount',
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='impact',
            name='recurring_amount',
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='incidenttype',
            name='responses',
            field=models.ManyToManyField(to='kitten.Response', verbose_name='possible responses'),
        ),
        migrations.AlterField(
            model_name='incidenttype',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Line'), (2, 'Train'), (3, 'Station')]),
        ),
        migrations.AlterField(
            model_name='line',
            name='line_reputation',
            field=models.PositiveSmallIntegerField(default=100),
        ),
        migrations.AlterField(
            model_name='line',
            name='on_time_arrivals',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='line',
            name='total_arrivals',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='line',
            name='train_interval',
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.AlterField(
            model_name='line',
            name='trains_dir1',
            field=models.PositiveSmallIntegerField(default=3),
        ),
        migrations.AlterField(
            model_name='line',
            name='trains_dir2',
            field=models.PositiveSmallIntegerField(default=3),
        ),
        migrations.AlterField(
            model_name='linelocation',
            name='position',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name='linelocation',
            name='transit_delay',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='linelocation',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, 'Depot'), (1, 'Track'), (2, 'Station')], default=0),
        ),
        migrations.AlterField(
            model_name='linetemplate',
            name='train_interval',
            field=models.PositiveSmallIntegerField(default=10, verbose_name='Interval between trains starting'),
        ),
        migrations.AlterField(
            model_name='linetemplate',
            name='trains_dir1',
            field=models.PositiveSmallIntegerField(default=3, verbose_name='Number of trains starting in direction1'),
        ),
        migrations.AlterField(
            model_name='linetemplate',
            name='trains_dir2',
            field=models.PositiveSmallIntegerField(default=3, verbose_name='Number of trains starting in direction2'),
        ),
        migrations.AlterField(
            model_name='network',
            name='night_traffic',
            field=models.PositiveSmallIntegerField(default=50, help_text='passenger traffic at start/end of the day'),
        ),
        migrations.AlterField(
            model_name='network',
            name='peak_evening_traffic',
            field=models.PositiveSmallIntegerField(default=150, help_text='passenger traffic compared to daytime normal=100'),
        ),
        migrations.AlterField(
            model_name='network',
            name='peak_morning_traffic',
            field=models.PositiveSmallIntegerField(default=200, help_text='passenger traffic compared to daytime normal=100'),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='name',
            field=models.CharField(blank=True, default='', help_text='A name is only required for stations', max_length=40),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='passenger_traffic_dir1',
            field=models.PositiveSmallIntegerField(default=100, help_text='Relative peak passenger traffic in direction 1 at this station.', verbose_name='Peak passenger traffic in direction1'),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='passenger_traffic_dir2',
            field=models.PositiveSmallIntegerField(default=100, help_text='Relative peak passenger traffic in direction 2 at this station.', verbose_name='Peak passenger traffic in direction2'),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='position',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='transit_delay',
            field=models.PositiveSmallIntegerField(default=1, help_text='time to travel along lines; wait time at stations or depots'),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='turnaround_percent_direction1',
            field=models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)], verbose_name='Turnaround % from direction 1'),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='turnaround_percent_direction2',
            field=models.PositiveSmallIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100)], verbose_name='Turnaround % from direction 2'),
        ),
        migrations.AlterField(
            model_name='placetemplate',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, 'Depot'), (1, 'Track'), (2, 'Station')], default=1),
        ),
        migrations.AlterField(
            model_name='team',
            name='level',
            field=models.PositiveSmallIntegerField(choices=[(10, 'Basic'), (20, 'Intermediate'), (30, 'Advanced'), (40, 'Expert')], default=10),
        ),
    ]
