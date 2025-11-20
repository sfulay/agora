"""
Django management command to generate avatars based on demographic data using DALL-E
Usage:
    python manage.py generate_demographic_avatars --participants 123,456,789
    python manage.py generate_demographic_avatars --all-with-demographics
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from pages.models import Participant
from pages.demographic_avatar_generator import DemographicAvatarGenerator
import os


class Command(BaseCommand):
    help = 'Generate DALL-E avatars for specified participants based on their demographic data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--participants',
            type=str,
            help='Comma-separated list of participant IDs',
        )
        parser.add_argument(
            '--all-with-demographics',
            action='store_true',
            help='Generate avatars for all participants with demographic data',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing generated avatars',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually generating avatars',
        )
        parser.add_argument(
            '--show-demographics',
            action='store_true',
            help='Show demographic information for participants (debug mode)',
        )

    def handle(self, *args, **options):
        # Check for OpenAI API key
        if not options['dry_run'] and not options['show_demographics'] and not os.getenv('OPENAI_API_KEY'):
            raise CommandError('OPENAI_API_KEY environment variable is required')

        # Initialize the demographic avatar generator
        generator = DemographicAvatarGenerator()
        
        participant_ids = []
        
        if options['participants']:
            # Parse comma-separated participant IDs
            try:
                participant_ids = [int(pid.strip()) for pid in options['participants'].split(',')]
            except ValueError:
                raise CommandError('Invalid participant ID format. Use comma-separated integers.')
        
        elif options['all_with_demographics']:
            # Get prolific IDs from CSV first, then find matching participants
            import pandas as pd
            from django.conf import settings
            try:
                csv_path = 'data/all_df_clean_pass_concept_measures_joined.csv'
                df = pd.read_csv(csv_path)
                csv_prolific_ids = df['PROLIFIC_PID'].tolist()
                
                # Find participants in database that match CSV prolific IDs
                participant_ids = list(
                    Participant.objects.filter(
                        prolific_id__in=csv_prolific_ids
                    ).values_list('id', flat=True)
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Found {len(csv_prolific_ids)} prolific IDs in CSV, '
                        f'{len(participant_ids)} matching participants in database'
                    )
                )
            except Exception as e:
                raise CommandError(f'Error reading CSV file: {e}')
        else:
            raise CommandError('Must specify either --participants or --all-with-demographics')

        if not participant_ids:
            self.stdout.write(self.style.WARNING('No participants found'))
            return

        # Show demographics mode
        if options['show_demographics']:
            self.stdout.write('=== DEMOGRAPHIC INFORMATION ===')
            for pid in participant_ids[:10]:  # Limit to first 10 for demo
                generator.get_demographic_info(pid)
                self.stdout.write('')
            return

        # Filter participants based on overwrite option
        if not options['overwrite']:
            # Exclude participants who already have generated avatars
            existing_generated = set(
                Participant.objects.filter(
                    id__in=participant_ids,
                    avatar__generated_image__isnull=False
                ).values_list('id', flat=True)
            )
            
            if existing_generated:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipping {len(existing_generated)} participants with existing generated avatars: '
                        f'{", ".join(map(str, existing_generated))}'
                    )
                )
                participant_ids = [pid for pid in participant_ids if pid not in existing_generated]

        if not participant_ids:
            self.stdout.write(self.style.WARNING('No participants to process after filtering'))
            return

        self.stdout.write(f'Processing {len(participant_ids)} participants: {participant_ids}')

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No avatars will be generated'))
            for pid in participant_ids:
                try:
                    participant = Participant.objects.get(id=pid)
                    enhanced_description, has_interview = generator.generate_enhanced_description(participant)
                    interview_note = " (with interview context)" if has_interview else " (demographics only)"
                    self.stdout.write(f'Participant {pid} ({participant.prolific_id}){interview_note}')
                    self.stdout.write(f'  Would generate: {enhanced_description}')
                except Participant.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Participant {pid} not found'))
            return

        successful_count = 0
        failed_count = 0
        
        for participant_id in participant_ids:
            try:
                with transaction.atomic():
                    success = generator.generate_avatar_for_participant(participant_id)
                    if success:
                        successful_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Generated demographic avatar for participant {participant_id}')
                        )
                    else:
                        failed_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'✗ Failed to generate avatar for participant {participant_id}')
                        )
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing participant {participant_id}: {e}')
                )

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Demographic Avatar Generation Summary:')
        self.stdout.write(f'  Successful: {successful_count}')
        self.stdout.write(f'  Failed: {failed_count}')
        self.stdout.write(f'  Total processed: {successful_count + failed_count}')
        
        if successful_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nGenerated avatars are automatically set as default for participants.'
                )
            )