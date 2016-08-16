# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0014_auto_20160708_1011'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctor',
            name='family_name',
            field=models.CharField(max_length=100, verbose_name=b'Family/Last name', db_index=True),
        ),
        migrations.AlterField(
            model_name='doctor',
            name='given_names',
            field=models.CharField(max_length=100, verbose_name=b'Given/First names', db_index=True),
        ),
        migrations.AlterField(
            model_name='doctor',
            name='suburb',
            field=models.CharField(max_length=50, verbose_name=b'Suburb/Town/City'),
        ),
        migrations.AlterField(
            model_name='patient',
            name='next_of_kin_suburb',
            field=models.CharField(max_length=50, null=True, verbose_name=b'Suburb/Town/City', blank=True),
        ),
    ]
