from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prayers', '0009_add_intent_level_to_usersettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='sunnah_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Whether optional Sunna tracking is enabled for this user.',
            ),
        ),
    ]
