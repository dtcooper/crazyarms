# Generated by Django 3.1.2 on 2020-10-14 07:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledBroadcast',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_path', models.CharField(max_length=1024)),
                ('scheduled_time', models.DateTimeField()),
                ('task_id', models.UUIDField(null=True)),
                ('play_status', models.CharField(choices=[('-', 'Pending'), ('p', 'Played'), ('e', 'Error')], default='-', max_length=1)),
            ],
            options={
                'ordering': ('-scheduled_time',),
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('harbor_auth', models.CharField(choices=[('a', 'Always'), ('n', 'Never'), ('s', 'Schedule Based')], max_length=1)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduledGCalShow',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gcal_id', models.CharField(max_length=1024, unique=True)),
                ('title', models.CharField(max_length=1024)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField()),
                ('users', models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
