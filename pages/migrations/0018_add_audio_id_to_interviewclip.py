# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0017_participantrecommendationsupport'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewclip',
            name='audio_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ] 