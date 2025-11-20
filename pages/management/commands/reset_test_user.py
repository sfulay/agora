from django.core.management.base import BaseCommand
from pages.models import Interview, Participant
from pages.interview_settings import ordered_modules

class Command(BaseCommand):
    help = 'Resets interview data for a test user and marks consent as completed'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = Participant.objects.get(username=username)
            # Delete all interviews
            interviews_deleted = Interview.objects.filter(participant=user).delete()
            
            # Reset completed modules and then mark Consent as completed
            user.completed_modules = 'Consent'  # Directly set Consent as completed
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully reset user {username} and marked consent as completed'
                )
            )
        except Participant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User {username} does not exist')
            )