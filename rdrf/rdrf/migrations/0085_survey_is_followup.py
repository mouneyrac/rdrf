# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-11-30 15:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rdrf', '0084_surveyrequest_communication_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='survey',
            name='is_followup',
            field=models.BooleanField(default=False),
        ),
    ]
