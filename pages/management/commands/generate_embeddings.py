"""
Management command to generate embeddings for all interview segments

Usage:
    python manage.py generate_embeddings
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from pages.models import InterviewSegment, SegmentEmbedding, Participant
from generating_v2.chat_rag import EmbeddingService
import numpy as np


class Command(BaseCommand):
    help = 'Generate embeddings for interview segments from agora members for AgoraChat RAG'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of segments to process at once (default: 100)'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing embeddings'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        overwrite = options['overwrite']

        self.stdout.write(self.style.SUCCESS('Starting embedding generation...'))

        # Load agora member prolific IDs
        agora_members_file = os.path.join(settings.BASE_DIR, 'data', 'agora_members.txt')

        if not os.path.exists(agora_members_file):
            self.stdout.write(self.style.ERROR(f'Agora members file not found: {agora_members_file}'))
            return

        with open(agora_members_file, 'r') as f:
            prolific_ids = [line.strip() for line in f if line.strip()]

        self.stdout.write(f'Loaded {len(prolific_ids)} agora member prolific IDs')

        # Get participants with these prolific IDs
        agora_participants = Participant.objects.filter(prolific_id__in=prolific_ids)
        participant_count = agora_participants.count()

        self.stdout.write(f'Found {participant_count} agora members in database')

        # Initialize embedding service
        embedding_service = EmbeddingService()
        self.stdout.write(f'Using model: {embedding_service.model_name}')
        self.stdout.write(f'Embedding dimension: {embedding_service.dimension}')

        # Get segments to process - only for agora members
        base_segments = InterviewSegment.objects.filter(
            audio__question__interview__participant__in=agora_participants
        )

        if overwrite:
            segments = base_segments
            # Delete existing embeddings for agora members only
            deleted_count = SegmentEmbedding.objects.filter(segment__in=base_segments).count()
            SegmentEmbedding.objects.filter(segment__in=base_segments).delete()
            self.stdout.write(f'Deleted {deleted_count} existing embeddings for agora members')
        else:
            # Only process segments without embeddings
            existing_ids = SegmentEmbedding.objects.values_list('segment_id', flat=True)
            segments = base_segments.exclude(id__in=existing_ids)

        total_segments = segments.count()
        self.stdout.write(f'Processing {total_segments} segments...')

        if total_segments == 0:
            self.stdout.write(self.style.SUCCESS('No segments to process!'))
            return

        # Convert to list to avoid QuerySet slicing issues
        all_segments = list(segments.select_related('audio__question__interview__participant'))
        self.stdout.write(f'Loaded {len(all_segments)} segments into memory')

        # Process in batches
        processed = 0
        batch_num = 1
        for i in range(0, len(all_segments), batch_size):
            batch_segments = all_segments[i:i + batch_size]

            # Extract texts
            texts = [seg.segment_text for seg in batch_segments]

            # Generate embeddings
            self.stdout.write(f'Processing batch {batch_num} ({len(batch_segments)} segments)...')
            embeddings = embedding_service.embed_batch(texts)
            batch_num += 1

            # Save to database
            segment_embeddings = []
            for seg, embedding in zip(batch_segments, embeddings):
                # Serialize embedding as binary
                embedding_binary = embedding.astype('float32').tobytes()

                segment_embeddings.append(
                    SegmentEmbedding(
                        segment=seg,
                        embedding_vector=embedding_binary,
                        model_version=embedding_service.model_name
                    )
                )

            SegmentEmbedding.objects.bulk_create(segment_embeddings)

            processed += len(batch_segments)
            self.stdout.write(f'Progress: {processed}/{total_segments} ({100 * processed // total_segments}%)')

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {processed} embeddings!'))
        self.stdout.write(self.style.SUCCESS('AgoraChat is ready to use!'))
