# Generated by Django 3.1.4 on 2020-12-30 00:21

import common.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GCalShow',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gcal_id', common.models.TruncatingCharField(max_length=256, unique=True)),
                ('title', common.models.TruncatingCharField(max_length=1024, verbose_name='title')),
                ('start', models.DateTimeField(verbose_name='start time')),
                ('end', models.DateTimeField(verbose_name='end time')),
                ('users', models.ManyToManyField(related_name='gcal_shows', to=settings.AUTH_USER_MODEL, verbose_name='users')),
            ],
            options={
                'verbose_name': 'Google Calendar show',
                'verbose_name_plural': 'Google Calendar shows',
                'ordering': ('start', 'id'),
            },
        ),
    ]
