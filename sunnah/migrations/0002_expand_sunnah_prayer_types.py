from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sunnah', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sunnahlog',
            name='prayer_type',
            field=models.CharField(
                choices=[
                    ('fajr', 'Fajr Sunnah'),
                    ('dhuhr', 'Dhuhr Sunnah'),
                    ('asr', 'Asr Sunnah'),
                    ('maghrib', 'Maghrib Sunnah'),
                    ('isha', 'Isha Sunnah'),
                    ('witr', 'Witr'),
                    ('dhuha', 'Dhuha'),
                    ('tahajjud', 'Tahajjud'),
                ],
                max_length=20,
            ),
        ),
    ]