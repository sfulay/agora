# Generated migration for avatar generation fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0055_add_opinion_vs_experience_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='avatar',
            name='generated_image',
            field=models.ImageField(blank=True, null=True, upload_to='GeneratedAvatars/'),
        ),
        migrations.AddField(
            model_name='avatar',
            name='is_generated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='avatar',
            name='generation_prompt',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='avatar',
            name='generation_model',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='avatar',
            name='generated_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='participant',
            name='use_generated_avatar',
            field=models.BooleanField(default=False),
        ),
    ]