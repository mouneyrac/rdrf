# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rdrf', '0031_auto_20160720_1442'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailnotification',
            name='email_from',
            field=models.EmailField(default=b'No Reply <no-reply@mg.ccgapps.com.au>', max_length=254),
        )
    ]
