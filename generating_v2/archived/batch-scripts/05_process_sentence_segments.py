#!/usr/bin/env python3
"""
Script to process interview audio files into sentence-level segments.

This script:
1. Retrieves completed interviews from the database
2. Downloads audio files from S3
3. Transcribes with Whisper API (word-level timestamps if available)
4. Creates sentence-level segments based on punctuation
5. Splits audio into individual sentence WAV files
6. Uploads segments to S3
7. Saves InterviewSegment records to database

Usage:
    python generating_v2/05_process_sentence_segments.py
"""

import os
import sys
import django
import boto3
import openai
import json
from io import BytesIO
from pydub import AudioSegment
from datetime import datetime

# Setup Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from pages.models import Interview, InterviewAudio, InterviewSegment
from django.conf import settings
from django.core.files.base import ContentFile

# Setup OpenAI
sys.path.append('interviewer_agent')
from interviewer_agent.interviewer_utils.settings import get_open_api_keyset
openai.api_key = get_open_api_keyset()["key"]


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def enforce_sentence_boundaries(segments):
    """
    Split at every period, question mark, and exclamation point.
    """
    sentence_segments = []
    current_segments = []
    current_text = ""
    sentence_id = 0
    
    for i, seg in enumerate(segments):
        if isinstance(seg, dict):
            seg_text = seg.get('text', '').strip()
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)
        else:
            seg_text = getattr(seg, 'text', '').strip()
            seg_start = getattr(seg, 'start', 0)
            seg_end = getattr(seg, 'end', 0)
        
        current_segments.append({'text': seg_text, 'start': seg_start, 'end': seg_end})
        current_text += " " + seg_text
        
        # Check if this segment ends with sentence-ending punctuation
        ends_sentence = seg_text.rstrip().endswith(('.', '?', '!'))
        
        # Also check if there are periods WITHIN the accumulated text that we should split on
        has_internal_periods = '.' in current_text and not current_text.rstrip().endswith('.')
        
        # End sentence if:
        # 1. This segment ends with punctuation, OR
        # 2. There are internal periods we should split on, OR  
        # 3. Last segment (force end)
        should_end = ends_sentence or has_internal_periods or i == len(segments) - 1
        
        if should_end:
            if current_segments:
                # If we have internal periods, try to split at the last period
                if has_internal_periods and not ends_sentence:
                    # Find the last period in the text
                    last_period_pos = current_text.rfind('.')
                    if last_period_pos > 0:
                        # Split the text at the last period
                        first_part_text = current_text[:last_period_pos + 1].strip()
                        second_part_text = current_text[last_period_pos + 1:].strip()
                        
                        # Find which segment contains the period
                        split_segment_idx = 0
                        for j, seg in enumerate(current_segments):
                            if seg['text'] in current_text[last_period_pos:]:
                                split_segment_idx = j
                                break
                        
                        # Add first part as sentence
                        if first_part_text:
                            sentence_segments.append({
                                'id': sentence_id,
                                'start': current_segments[0]['start'],
                                'end': current_segments[split_segment_idx]['end'],
                                'text': first_part_text
                            })
                            sentence_id += 1
                        
                        # Continue with second part
                        current_segments = current_segments[split_segment_idx + 1:]
                        current_text = second_part_text
                        continue
                
                # Add the sentence
                sentence_segments.append({
                    'id': sentence_id,
                    'start': current_segments[0]['start'],
                    'end': current_segments[-1]['end'],
                    'text': current_text.strip()
                })
                sentence_id += 1
                current_segments = []
                current_text = ""
    
    return sentence_segments


def find_period_break_point(text, segments):
    """
    Find a period within the accumulated text to split more naturally.
    Returns the segment index to split after, or None if no good break point.
    """
    for i in range(len(text) - 1, -1, -1):
        if text[i] == '.' and i < len(text) - 1:
            # Find which segment this period belongs to
            period_pos = i
            for j, seg in enumerate(segments):
                if seg['text'] in text[period_pos:]:
                    return j + 1  # Split after this segment
    
    return None


def merge_segments_into_sentences(segments):
    """
    Legacy function - now calls enforce_sentence_boundaries for consistency.
    """
    return enforce_sentence_boundaries(segments)


def merge_words_into_sentences(transcription):
    """
    Merge word-level timestamps into sentence-level segments.
    Sentences are defined by punctuation: . ? !
    """
    # Extract words
    words = None
    if hasattr(transcription, 'words'):
        words = transcription.words
    elif isinstance(transcription, dict) and 'words' in transcription:
        words = transcription['words']
    
    if not words:
        # Fallback: use segments and merge them into sentences based on punctuation
        log("⚠️  No word-level data available - using segment-based fallback")
        
        if hasattr(transcription, 'segments'):
            segments = transcription.segments
        elif isinstance(transcription, dict) and 'segments' in transcription:
            segments = transcription['segments']
        else:
            log("❌ No segments available either!")
            return []
        
        sentence_segments = merge_segments_into_sentences(segments)
        log(f"✅ Created {len(sentence_segments)} sentence segments from {len(segments)} original segments")
        return sentence_segments
    
    # Process word-level data into sentences
    sentence_segments = []
    current_words = []
    current_text = ""
    sentence_id = 0
    
    # Sentence-ending punctuation
    sentence_endings = {'.', '?', '!'}
    
    for i, word in enumerate(words):
        # Extract word data
        if isinstance(word, dict):
            w_text = word.get('word', '').strip()
            w_start = word.get('start', 0)
            w_end = word.get('end', 0)
        else:
            w_text = getattr(word, 'word', '').strip()
            w_start = getattr(word, 'start', 0)
            w_end = getattr(word, 'end', 0)
        
        current_words.append({'word': w_text, 'start': w_start, 'end': w_end})
        current_text += w_text
        
        # Check if this word ends with sentence-ending punctuation
        ends_sentence = any(w_text.endswith(punct) for punct in sentence_endings)
        
        # Also end sentence if we've accumulated too many words (max 50 words per sentence)
        too_long = len(current_words) >= 50
        
        # End sentence if punctuation found or if too long or if last word
        if ends_sentence or too_long or i == len(words) - 1:
            if current_words:
                sentence_segments.append({
                    'id': sentence_id,
                    'start': current_words[0]['start'],
                    'end': current_words[-1]['end'],
                    'text': current_text.strip(),
                    'word_count': len(current_words)
                })
                sentence_id += 1
                current_words = []
                current_text = ""
    
    log(f"✅ Created {len(sentence_segments)} sentence segments from {len(words)} words")
    return sentence_segments


def transcribe_audio(audio_buffer):
    """
    Transcribe audio using Whisper API with proper sentence boundary enforcement.
    """
    try:
        audio_buffer.seek(0)
        audio_buffer.name = "audio.wav"
        
        log("  Transcribing with Whisper API...")
        
        # Use segment-level transcription with proper sentence boundary enforcement
        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_buffer,
            language="en",
            response_format="verbose_json"
        )
        
        # Extract segments
        if hasattr(transcription, 'segments') and transcription.segments:
            segments = transcription.segments
        elif isinstance(transcription, dict) and 'segments' in transcription:
            segments = transcription['segments']
        else:
            log("❌ No segments available!")
            return []
        
        # Use improved sentence boundary detection
        sentence_segments = enforce_sentence_boundaries(segments)
        log(f"✅ Created {len(sentence_segments)} sentence segments from {len(segments)} original segments")
        
        # Debug: Show some examples of the sentence merging
        if len(sentence_segments) > 0:
            log(f"📝 Example sentence 1: '{sentence_segments[0]['text'][:100]}...'")
            if len(sentence_segments) > 1:
                log(f"📝 Example sentence 2: '{sentence_segments[1]['text'][:100]}...'")
        
        return sentence_segments
        
    except Exception as e:
        log(f"❌ Transcription failed: {e}")
        return []


def process_audio_file(audio_obj, s3_client, bucket_name, skip_existing=True):
    """
    Process a single InterviewAudio file into sentence segments.
    
    Args:
        audio_obj: InterviewAudio database object
        s3_client: boto3 S3 client
        bucket_name: S3 bucket name
        skip_existing: If True, skip audio files that already have segments
    
    Returns:
        Number of segments created, or 0 if skipped/failed
    """
    # Check if already processed
    if skip_existing and audio_obj.segments.exists():
        log(f"  ⏭️  Audio {audio_obj.id} already has {audio_obj.segments.count()} segments - skipping")
        return 0
    
    log(f"  Processing Audio ID: {audio_obj.id}")
    
    # Get S3 key
    s3_key = audio_obj.audio_file.name
    if not s3_key.startswith('media/'):
        s3_key = f"media/{s3_key}"
    
    # Download audio from S3
    try:
        audio_buffer = BytesIO()
        s3_client.download_fileobj(bucket_name, s3_key, audio_buffer)
        audio_buffer.seek(0)
        log(f"  ✅ Downloaded from S3 ({len(audio_buffer.getvalue())} bytes)")
    except Exception as e:
        log(f"  ❌ Failed to download from S3: {e}")
        return 0
    
    # Transcribe audio
    transcription = transcribe_audio(audio_buffer)
    if not transcription:
        return 0
    
    # Create sentence segments (transcription now returns sentence segments directly)
    sentence_segments = transcription
    if not sentence_segments:
        log(f"  ❌ No sentence segments created")
        return 0
    
    # Load full audio for splitting
    try:
        audio_buffer.seek(0)
        full_audio = AudioSegment.from_file(audio_buffer, format="wav")
        log(f"  ✅ Loaded audio for splitting ({len(full_audio)/1000:.2f}s)")
    except Exception as e:
        log(f"  ❌ Failed to load audio: {e}")
        return 0
    
    # Process each sentence segment
    created_count = 0
    for seg in sentence_segments:
        try:
            start_time = seg['start']
            end_time = seg['end']
            text = seg['text'].strip()
            word_count = seg.get('word_count', None)
            seq_num = seg['id'] + 1  # 1-indexed
            
            # Extract audio segment
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            audio_segment = full_audio[start_ms:end_ms]
            
            # Export to BytesIO
            segment_buffer = BytesIO()
            audio_segment.export(segment_buffer, format="wav")
            segment_buffer.seek(0)
            
            # Read the bytes immediately to avoid I/O issues
            segment_bytes = segment_buffer.read()
            
            # Construct S3 path
            question = audio_obj.question
            s3_path = f"InterviewAudios/interview{question.interview.id}/module{question.module.id}/question{question.id}/user_{audio_obj.id}/sentence_{seq_num:03d}.wav"
            
            # Upload to S3 using a new BytesIO object
            s3_buffer = BytesIO(segment_bytes)
            log(f"    📤 Uploading to S3: {s3_path}")
            try:
                s3_client.upload_fileobj(
                    s3_buffer,
                    bucket_name,
                    f"media/{s3_path}",
                    ExtraArgs={'ContentType': 'audio/wav'}
                )
                log(f"    ✅ S3 upload successful")
            except Exception as e:
                log(f"    ❌ S3 upload failed: {e}")
                raise
            
            # Create database record
            segment_obj = InterviewSegment.objects.create(
                audio=audio_obj,
                start_time=start_time,
                end_time=end_time,
                segment_text=text,
                sequence_number=seq_num,
                word_count=word_count
            )
            
            # Save the file reference using a new BytesIO object
            django_buffer = BytesIO(segment_bytes)
            segment_obj.segment_audio_file.save(
                f"sentence_{seq_num:03d}.wav",
                ContentFile(django_buffer.read()),
                save=True
            )
            
            created_count += 1
            log(f"    ✅ Sentence {seq_num}: {start_time:.2f}s-{end_time:.2f}s ({len(text)} chars)")
            
        except Exception as e:
            log(f"    ❌ Failed to process segment {seg['id']}: {e}")
            continue
    
    log(f"  ✅ Created {created_count}/{len(sentence_segments)} segments for Audio {audio_obj.id}")
    return created_count


def process_interview(interview, s3_client, bucket_name, skip_existing=True):
    """
    Process all audio files for a single interview.
    
    Args:
        interview: Interview database object
        s3_client: boto3 S3 client
        bucket_name: S3 bucket name
        skip_existing: If True, skip audio files that already have segments
    
    Returns:
        Dictionary with processing statistics
    """
    log(f"\n{'='*80}")
    log(f"Processing Interview {interview.id}")
    log(f"  Participant: {interview.participant.username if interview.participant else 'N/A'}")
    log(f"  Script: {interview.script_v}")
    log(f"{'='*80}")
    
    # Get all user audio files for this interview
    questions = interview.interviewquestion_set.all()
    all_audio = InterviewAudio.objects.filter(
        question__in=questions,
        user_speech=True  # Only process user speech, not interviewer
    ).order_by('created')
    
    log(f"Found {all_audio.count()} user audio files")
    
    stats = {
        'interview_id': interview.id,
        'total_audio_files': all_audio.count(),
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'total_segments': 0
    }
    
    for audio in all_audio:
        segments_created = process_audio_file(audio, s3_client, bucket_name, skip_existing)
        
        if segments_created > 0:
            stats['processed'] += 1
            stats['total_segments'] += segments_created
        elif skip_existing and audio.segments.exists():
            stats['skipped'] += 1
        else:
            stats['failed'] += 1
    
    log(f"\n{'='*80}")
    log(f"Interview {interview.id} Summary:")
    log(f"  Audio files processed: {stats['processed']}")
    log(f"  Audio files skipped: {stats['skipped']}")
    log(f"  Audio files failed: {stats['failed']}")
    log(f"  Total segments created: {stats['total_segments']}")
    log(f"{'='*80}\n")
    
    return stats


def process_all_interviews(skip_existing=True, limit=None):
    """
    Process all completed interviews.
    
    Args:
        skip_existing: If True, skip audio files that already have segments
        limit: Optional limit on number of interviews to process
    
    Returns:
        List of statistics dictionaries for each interview
    """
    log("="*80)
    log("SENTENCE SEGMENT PROCESSING - Starting")
    log("="*80)
    
    # Setup S3
    s3_client = boto3.client('s3')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    log(f"S3 Bucket: {bucket_name}")
    
    # Get completed interviews
    interviews = Interview.objects.filter(completed=True).order_by('id')
    if limit:
        interviews = interviews[:limit]
    
    log(f"Found {interviews.count()} completed interviews to process")
    log(f"Skip existing: {skip_existing}")
    log("")
    
    all_stats = []
    
    for idx, interview in enumerate(interviews, 1):
        log(f"\n[Interview {idx}/{interviews.count()}]")
        
        try:
            stats = process_interview(interview, s3_client, bucket_name, skip_existing)
            all_stats.append(stats)
        except Exception as e:
            log(f"❌ Failed to process interview {interview.id}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Final summary
    log("\n" + "="*80)
    log("FINAL SUMMARY")
    log("="*80)
    total_processed = sum(s['processed'] for s in all_stats)
    total_skipped = sum(s['skipped'] for s in all_stats)
    total_failed = sum(s['failed'] for s in all_stats)
    total_segments = sum(s['total_segments'] for s in all_stats)
    
    log(f"Interviews processed: {len(all_stats)}")
    log(f"Audio files processed: {total_processed}")
    log(f"Audio files skipped: {total_skipped}")
    log(f"Audio files failed: {total_failed}")
    log(f"Total segments created: {total_segments}")
    log("="*80)
    
    return all_stats


def process_single_interview(interview_id, skip_existing=True):
    """Process a single interview by ID"""
    try:
        interview = Interview.objects.get(id=interview_id)
    except Interview.DoesNotExist:
        log(f"❌ Interview {interview_id} not found")
        return None
    
    # Setup S3
    s3_client = boto3.client('s3')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    return process_interview(interview, s3_client, bucket_name, skip_existing)


if __name__ == "__main__":
    
    # List of interview IDs to process 
    INTERVIEW_IDS = [212]
    
    
    # Processing options
    SKIP_EXISTING = False  # Set to True to skip already processed audio files
    LIMIT_PER_INTERVIEW = None  # Set to number to limit audio files per interview (None = no limit)
    
    # ============================================================================
    # PROCESSING LOGIC
    # ============================================================================
    
    if INTERVIEW_IDS:
        # Process the specified interview IDs
        log(f"🎯 Processing {len(INTERVIEW_IDS)} interviews: {INTERVIEW_IDS}")
        
        total_stats = {
            'processed': 0, 
            'skipped': 0, 
            'failed': 0, 
            'segments_created': 0,
            'audio_files_processed': 0
        }
        
        for interview_id in INTERVIEW_IDS:
            log(f"\n{'='*80}")
            log(f"Processing Interview {interview_id}")
            log(f"{'='*80}")
            
            try:
                if LIMIT_PER_INTERVIEW:
                    stats = process_single_interview(interview_id=interview_id, skip_existing=SKIP_EXISTING, limit=LIMIT_PER_INTERVIEW)
                else:
                    stats = process_single_interview(interview_id=interview_id, skip_existing=SKIP_EXISTING)
                
                if stats:
                    total_stats['processed'] += 1
                    total_stats['segments_created'] += stats.get('segments_created', 0)
                    total_stats['audio_files_processed'] += stats.get('audio_files_processed', 0)
                    log(f"✅ Interview {interview_id}: {stats.get('segments_created', 0)} segments created")
                else:
                    total_stats['failed'] += 1
                    log(f"❌ Interview {interview_id}: No segments created")
            except Exception as e:
                log(f"❌ Failed to process interview {interview_id}: {e}")
                total_stats['failed'] += 1
        
        # Final summary
        log(f"\n{'='*80}")
        log(f"FINAL SUMMARY")
        log(f"{'='*80}")
        log(f"✅ Successfully processed: {total_stats['processed']} interviews")
        log(f"❌ Failed: {total_stats['failed']} interviews")
        log(f"📊 Total segments created: {total_stats['segments_created']}")
        log(f"🎵 Total audio files processed: {total_stats['audio_files_processed']}")
        log(f"{'='*80}")
        
    else:
        # No interview IDs specified - show instructions
        log("⚠️  No interview IDs specified")
    
    log("\n✅ Script completed!")

