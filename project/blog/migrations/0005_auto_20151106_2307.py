# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0004_auto_20151106_2300'),
    ]

    operations = [
        migrations.AlterField(
            model_name='listingpicture',
            name='picture',
            field=models.ImageField(upload_to='media', default='', blank=True),
        ),
    ]
