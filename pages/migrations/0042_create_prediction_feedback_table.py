# Generated manually to handle existing database schema

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0041_predictionfeedback_recommendation_base_rec_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PredictionFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feedback_type', models.CharField(choices=[('too_high', 'My support is lower than predicted'), ('too_low', 'My support is higher than predicted'), ('neutral', "I'm neutral/unsure about this recommendation"), ('other', 'Other reason')], help_text='Type of feedback provided', max_length=20)),
                ('feedback_text', models.TextField(blank=True, help_text='Additional comments from the user')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('recommendation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pages.recommendation')),
            ],
            options={
                'verbose_name': 'Prediction Feedback',
                'verbose_name_plural': 'Prediction Feedback',
                'unique_together': {('participant', 'recommendation')},
            },
        ),
        migrations.AlterField(
            model_name='participantnarrativepart',
            name='participant_narrative',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parts', to='pages.participantnarrative'),
        ),
    ] 