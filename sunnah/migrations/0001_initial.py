from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SunnahLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.localdate)),
                ('prayer_type', models.CharField(choices=[('fajr', 'Fajr Sunnah'), ('dhuhr', 'Dhuhr Sunnah'), ('asr', 'Asr Sunnah'), ('maghrib', 'Maghrib Sunnah'), ('isha', 'Isha Sunnah')], max_length=20)),
                ('completed', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sunnah_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', 'prayer_type'],
                'unique_together': {('user', 'date', 'prayer_type')},
            },
        ),
        migrations.AddIndex(
            model_name='sunnahlog',
            index=models.Index(fields=['user', 'date'], name='sunnahlog_user_date_idx'),
        ),
    ]
