#!/usr/bin/env python3
"""
Script to download interview segments from the database for manual review.

Usage:
    python generating_v2/download_segments.py --interview_id 2
"""

import os
import sys
import django
import boto3
import json
from pathlib import Path

# Setup Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from pages.models import Interview, InterviewSegment, InterviewAudio
from django.conf import settings


def download_interview_segments(interview_id, output_dir="generating_v2/downloaded_segments"):
    """
    Download all segments for a specific interview.
    
    Args:
        interview_id: The interview ID to download segments for
        output_dir: Directory to save the segments
    """
    print(f"{'='*80}")
    print(f"Downloading segments for Interview {interview_id}")
    print(f"{'='*80}\n")
    
    # Get the interview
    try:
        interview = Interview.objects.get(id=interview_id)
    except Interview.DoesNotExist:
        print(f"❌ Interview {interview_id} not found!")
        return
    
    print(f"Interview: {interview.id}")
    print(f"Participant: {interview.participant.username if interview.participant else 'N/A'}")
    print(f"Script: {interview.script_v}\n")
    
    # Get all audio files for this interview
    questions = interview.interviewquestion_set.all()
    audio_files = InterviewAudio.objects.filter(
        question__in=questions,
        user_speech=True
    ).order_by('created')
    
    # Get all segments for these audio files
    all_segments = InterviewSegment.objects.filter(
        audio__in=audio_files
    ).select_related('audio', 'audio__question').order_by('audio__created', 'sequence_number')
    
    print(f"Found {all_segments.count()} segments across {audio_files.count()} audio files\n")
    
    if all_segments.count() == 0:
        print("❌ No segments found for this interview!")
        return
    
    # Create output directory structure
    base_dir = Path(output_dir)
    interview_dir = base_dir / f"interview_{interview_id}"
    interview_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup S3
    s3_client = boto3.client('s3')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # Download segments and collect metadata
    segments_metadata = []
    audio_groups = {}
    
    for segment in all_segments:
        audio_id = segment.audio.id
        
        if audio_id not in audio_groups:
            audio_groups[audio_id] = {
                'audio_id': audio_id,
                'question_id': segment.audio.question.id,
                'global_question_id': segment.audio.question.global_question_id,
                'segments': []
            }
        
        # Prepare metadata
        segment_info = {
            'segment_id': segment.id,
            'audio_id': audio_id,
            'sequence_number': segment.sequence_number,
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'duration': segment.duration,
            'text': segment.segment_text,
            'word_count': segment.word_count,
            'created': segment.created.isoformat()
        }
        
        # Download from S3
        try:
            # Get S3 path
            s3_key = segment.segment_audio_file.name
            if not s3_key.startswith('media/'):
                s3_key = f"media/{s3_key}"
            
            # Create local filename
            local_filename = f"audio_{audio_id}_sentence_{segment.sequence_number:03d}.wav"
            local_path = interview_dir / local_filename
            
            # Download
            s3_client.download_file(bucket_name, s3_key, str(local_path))
            
            segment_info['local_file'] = local_filename
            segment_info['status'] = 'downloaded'
            
            print(f"✅ Audio {audio_id} Sentence {segment.sequence_number}: {segment.duration:.2f}s - {local_filename}")
            
        except Exception as e:
            segment_info['status'] = 'failed'
            segment_info['error'] = str(e)
            print(f"❌ Failed to download Audio {audio_id} Sentence {segment.sequence_number}: {e}")
        
        audio_groups[audio_id]['segments'].append(segment_info)
        segments_metadata.append(segment_info)
    
    # Save metadata to JSON
    metadata_file = interview_dir / "segments_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump({
            'interview_id': interview_id,
            'participant': interview.participant.username if interview.participant else 'N/A',
            'script': interview.script_v,
            'total_segments': len(segments_metadata),
            'total_audio_files': len(audio_groups),
            'audio_groups': list(audio_groups.values()),
            'segments': segments_metadata
        }, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✅ Download Complete!")
    print(f"{'='*80}")
    print(f"Directory: {interview_dir}")
    print(f"Total segments: {len(segments_metadata)}")
    print(f"Metadata saved to: {metadata_file}")
    
    # Create a simple HTML viewer for easy playback
    create_html_viewer(interview_dir, interview_id, audio_groups)
    
    return interview_dir


def create_html_viewer(directory, interview_id, audio_groups):
    """Create a simple HTML file to play back all segments"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Interview {interview_id} - Segment Review</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        .audio-group {{
            background: white;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .audio-header {{
            background: #007bff;
            color: white;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 15px;
        }}
        .segment {{
            background: #f8f9fa;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .segment-header {{
            font-weight: bold;
            color: #28a745;
            margin-bottom: 8px;
        }}
        .segment-meta {{
            color: #666;
            font-size: 0.9em;
            margin: 5px 0;
        }}
        .segment-text {{
            background: white;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-style: italic;
        }}
        audio {{
            width: 100%;
            margin: 10px 0;
        }}
        .stats {{
            background: #e7f3ff;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <h1>Interview {interview_id} - Segment Review</h1>
    
    <div class="stats">
        <strong>Total Audio Files:</strong> {len(audio_groups)}<br>
        <strong>Total Segments:</strong> {sum(len(g['segments']) for g in audio_groups.values())}
    </div>
"""
    
    for audio_id, group in audio_groups.items():
        html_content += f"""
    <div class="audio-group">
        <div class="audio-header">
            <strong>Audio ID {audio_id}</strong> | 
            Question ID: {group['question_id']} | 
            Global Question: {group['global_question_id']} |
            Segments: {len(group['segments'])}
        </div>
"""
        
        for seg in group['segments']:
            if seg.get('status') == 'downloaded':
                html_content += f"""
        <div class="segment">
            <div class="segment-header">Sentence {seg['sequence_number']}</div>
            <div class="segment-meta">
                ⏱️ Time: {seg['start_time']:.2f}s - {seg['end_time']:.2f}s 
                ({seg['duration']:.2f}s duration)
                | 📝 {seg['word_count']} words
            </div>
            <audio controls>
                <source src="{seg['local_file']}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
            <div class="segment-text">"{seg['text']}"</div>
        </div>
"""
        
        html_content += """
    </div>
"""
    
    html_content += """
</body>
</html>
"""
    
    html_file = directory / f"review_interview_{interview_id}.html"
    with open(html_file, 'w') as f:
        f.write(html_content)
    
    print(f"📄 HTML viewer created: {html_file}")
    print(f"   Open this file in your browser to review all segments!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Download interview segments for review')
    parser.add_argument('--interview_id', type=int, default=2, help='Interview ID to download')
    parser.add_argument('--output_dir', type=str, default='generating_v2/downloaded_segments', 
                       help='Output directory for downloaded segments')
    
    args = parser.parse_args()
    
    download_interview_segments(args.interview_id, args.output_dir)


