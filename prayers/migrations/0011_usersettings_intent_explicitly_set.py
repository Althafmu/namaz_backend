from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prayers', '0010_usersettings_sunnah_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='intent_explicitly_set',
            field=models.BooleanField(
                default=False,
                help_text='Whether the user explicitly chose an intent level in onboarding.',
            ),
        ),
    ]