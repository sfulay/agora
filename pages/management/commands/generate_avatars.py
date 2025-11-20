"""
Django management command to generate avatars for participants using DALL-E
Usage:
    python manage.py generate_avatars --participants 123,456,789
    python manage.py generate_avatars --all-interviewed
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from pages.models import Participant, Interview
from pages.avatar_generator import AvatarGenerator
import os


class Command(BaseCommand):
    help = 'Generate DALL-E avatars for specified participants based on their interview transcripts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--participants',
            type=str,
            help='Comma-separated list of participant IDs',
        )
        parser.add_argument(
            '--all-interviewed',
            action='store_true',
            help='Generate avatars for all participants with completed interviews',
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

    def handle(self, *args, **options):
        # Check for OpenAI API key
        if not os.getenv('OPENAI_API_KEY'):
            raise CommandError('OPENAI_API_KEY environment variable is required')

        participant_ids = []
        
        if options['participants']:
            # Parse comma-separated participant IDs
            try:
                participant_ids = [int(pid.strip()) for pid in options['participants'].split(',')]
            except ValueError:
                raise CommandError('Invalid participant ID format. Use comma-separated integers.')
        
        elif options['all_interviewed']:
            # Get all participants with completed interviews (using correct relationship name)
            participant_ids = list(
                Participant.objects.filter(
                    interview__completed=True
                ).distinct().values_list('id', flat=True)
            )
        else:
            raise CommandError('Must specify either --participants or --all-interviewed')

        if not participant_ids:
            self.stdout.write(self.style.WARNING('No participants found'))
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
                    self.stdout.write(f'Would generate avatar for: {pid} ({participant.prolific_id})')
                except Participant.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Participant {pid} not found'))
            return

        # Initialize the avatar generator
        generator = AvatarGenerator()
        
        successful_count = 0
        failed_count = 0
        
        for participant_id in participant_ids:
            try:
                with transaction.atomic():
                    success = generator.generate_avatar_for_participant(participant_id)
                    if success:
                        successful_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Generated avatar for participant {participant_id}')
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
        self.stdout.write(f'Avatar Generation Summary:')
        self.stdout.write(f'  Successful: {successful_count}')
        self.stdout.write(f'  Failed: {failed_count}')
        self.stdout.write(f'  Total processed: {successful_count + failed_count}')
        
        if successful_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nTo use generated avatars, set use_generated_avatar=True for participants.'
                )
            )