# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-20 15:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0020_archivedpatient'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='next_of_kin_suburb',
            field=models.CharField(
                blank=True,
                max_length=50,
                null=True,
                verbose_name='Suburb/Town'),
        ),
    ]
