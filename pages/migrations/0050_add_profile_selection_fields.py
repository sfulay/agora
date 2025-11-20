# Generated manually on 2025-01-27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0049_recommendation_base_rec'),
    ]

    operations = [
        migrations.AddField(
            model_name='recommendationparticipantsummary',
            name='pro_profiles_selected',
            field=models.BooleanField(
                default=False,
                help_text="Whether this participant was selected for pro profiles (70% from >50 support, 30% from <50 support)"
            ),
        ),
        migrations.AddField(
            model_name='recommendationparticipantsummary',
            name='against_profiles_selected',
            field=models.BooleanField(
                default=False,
                help_text="Whether this participant was selected for against profiles (30% from >50 support, 70% from <50 support)"
            ),
        ),
    ] 