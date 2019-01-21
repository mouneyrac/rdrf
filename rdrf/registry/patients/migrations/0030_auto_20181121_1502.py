# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-11-21 15:02
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0029_patient_date_of_death'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='clinician',
            field=models.ForeignKey(blank=True,
                                    null=True,
                                    on_delete=models.SET_NULL,
                                    to=settings.AUTH_USER_MODEL,
                                    verbose_name='Clinician'),
        ),
    ]
