# Habermas Game - AI-Powered Policy Deliberation Platform

The Habermas Game is an interactive policy deliberation tool that enables users to iteratively refine policy proposals while receiving real-time AI predictions about public support. Users can edit policy recommendations, see live predictions of how real people would respond based on their interview data, and explore detailed participant perspectives through audio clips and narrative summaries.

## Core Features

- **Interactive Policy Editor**: Edit policy recommendations in real-time with a 500-character limit
- **Live AI Predictions**: Streaming predictions using GPT-4 to estimate participant support (0-100% agreement)
- **Support Visualization**: Interactive scatter plot showing participant avatars positioned by predicted agreement
- **Participant Profiles**: Detailed views with support scores, AI-generated reasoning, audio clips, and narrative summaries
- **Meta-Medleys**: Group audio summaries combining perspectives from participants who are "Against", "On the fence", or "For" the policy
- **Leaderboard System**: Gamified tracking of user performance in maximizing consensus

## Prerequisites

- Python 3.11
- PostgreSQL (production) or SQLite (development)
- OpenAI API key (GPT-4 access required)
- AWS account (for S3 storage - optional for local dev)
- Google Cloud Speech API credentials (for audio transcription - optional)

## Quick Start

```bash
# Clone and install
git clone [repository-url]
cd agora
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=your-key-here
export DJANGO_SETTINGS_MODULE=gabm_infra.settings.local

# Setup database
python manage.py migrate

# Run server
python manage.py runserver

# Access editor at:
# http://localhost:8000/editor/<recommendation_id>/
```

## Technical Architecture

### Stack Overview

- **Backend**: Django 4.2.5, Python 3.11
- **Database**: PostgreSQL (production), SQLite (local development)
- **AI/ML**: OpenAI GPT-4 and GPT-4o-mini, Anthropic Claude
- **Audio Processing**: Google Cloud Speech API, PyAudio, pydub
- **Storage**: AWS S3 (via django-storages)
- **Deployment**: AWS Elastic Beanstalk with Gunicorn

### Key Components

1. **Prediction Engine** (`generating_v2/rec_prediction.py`)
   - Predicts participant agreement scores (0-100)
   - Extracts supporting/opposing evidence from transcripts
   - Evaluates relevance and depth of participant experiences
   - Generates narrative summaries connecting life stories to policies

2. **Audio Processing Pipeline** (`generating_v2/`)
   - Processes interview audio into sentence-level segments
   - Creates individual 60s medleys per participant
   - Generates group meta-medleys for different support levels

3. **Visualization Layer** (`templates/pages/recommendations/recommendation_editor.html`)
   - Real-time prediction streaming with progress indicators
   - Interactive support scatter plot
   - Modal participant profiles with audio playback

### Core Database Models

The Habermas Game uses these key models:

#### **Recommendation**
Policy recommendations that users can edit and deliberate on.

**Key fields:**
- `rec_text`: The policy recommendation text
- `base_rec`: Link to the original recommendation (if this is an edited version)
- `participant_who_edited`: Who made this edit
- `ai_rec_text`: AI-generated consensus recommendation
- `ai_predicted_support`: Average support for AI recommendation

#### **Participant**
User accounts (extends Django's AbstractUser).

**Key fields:**
- `username`: Unique username (usually prolific_id)
- `prolific_id`: Unique participant identifier
- `display_name`: Human-readable name
- `avatar`: Link to Avatar model for profile image
- `has_completed_interview`: Boolean flag

#### **LivePrediction**
Real-time predictions used in the recommendation editor interface.

**Key fields:**
- `recommendation`: Link to Recommendation
- `participant`: Link to Participant
- `predicted_agreement` (0-100): How much they'd support the policy
- `confidence_score` (0-100): AI's confidence in the prediction
- `reasoning`: AI explanation for the predicted stance

#### **Interview Models**

**Interview**: Container for all interview data for a participant
- `participant`: Link to Participant
- `script_v`: Interview script version used
- `completed`: Whether interview is finished

**InterviewQuestion**: Individual questions asked during the interview
- `interview`: Link to Interview
- `question_id`: Question number
- `q_content`: The question text
- `convo`: Full conversation transcript for this question

**InterviewUtterance**: Individual sentences from interview transcripts
- `question`: Link to InterviewQuestion
- `utterance_text`: The actual sentence text
- `audio_id`: Reference to audio file
- `is_interviewer`: True if interviewer spoke this, False if participant
- `sequence_number`: Order within the question

**InterviewAudio**: Full audio files for questions
- `question`: Link to InterviewQuestion
- `user_speech`: True if participant speech, False if interviewer
- `audio_file`: Path to audio file in S3

**InterviewSegment**: Sentence-level audio segments
- `audio`: Link to InterviewAudio
- `start_time`: Start time in seconds
- `end_time`: End time in seconds
- `segment_text`: Transcribed text for this segment
- `segment_audio_file`: Path to segmented audio file
- `sequence_number`: Order within the audio file

#### **Audio Summary Models**

**Medley**: Individual 60-second audio summaries per participant
- `participant`: Link to Participant
- `recommendation`: Link to Recommendation (optional)
- `segments`: ManyToMany with InterviewSegment
- `total_duration`: Actual duration in seconds
- `quality_score` (0-100): Quality of the medley
- `gpt_reasoning`: Why GPT selected these segments

**MetaMedley**: Group audio summaries combining multiple participants
- `recommendation`: Link to Recommendation
- `participants`: ManyToMany with Participant
- `source_medleys`: ManyToMany with Medley (top K by quality)
- `selected_segments`: JSON array of segments from across participants
- `total_duration`: Total duration (target: 60-90s)
- `gpt_reasoning`: GPT's explanation of narrative flow
- `participant_cache_key`: Hash for deduplication

### API Endpoints

```
GET  /editor/<rec_id>/                           # Main editor interface
POST /api/editor/<rec_id>/recompute-stream/      # Trigger batch predictions (EventSource)
GET  /api/meta-medley/<rec_id>/<type>/           # Group audio (bottom/middle/top)
GET  /api/editor/<rec_id>/participant/<username>/ # Participant profile modal
```

## Integrating New Data Sources

This section explains how to add new participants, interview data, and policy recommendations to the Habermas Game.

### Data Format Requirements

The system expects participant data in CSV format with the following structure:

```csv
prolific_id,name,age,location,occupation,...
6672bf56d51710391ce2164d,John Doe,35,New York,Teacher,...
```

Key fields:
- `prolific_id`: Unique participant identifier (used as username)
- Additional demographic fields are optional but recommended

### Step 1: Add Participants

Create participant accounts in the database:

```python
from pages.models import Participant
import pandas as pd

# Load your participant data
df = pd.read_csv("data/your_participants.csv")

for _, row in df.iterrows():
    participant, created = Participant.objects.get_or_create(
        prolific_id=row['prolific_id'],
        defaults={
            'username': row['prolific_id'],
            'email': f"{row['prolific_id']}@example.com",
            # Add other fields as needed
        }
    )
```

Or use Django admin at `http://localhost:8000/admin/` after creating a superuser:

```bash
python manage.py createsuperuser
```

### Step 2: Add Interview Transcripts

Interview data should be structured as `InterviewUtterance` objects. Each utterance represents one sentence spoken during the interview.

**Option A: Manual import via Python**

```python
from pages.models import InterviewUtterance, InterviewQuestion, Participant

# Create or get the interview question
participant = Participant.objects.get(prolific_id="6672bf56d51710391ce2164d")
question = InterviewQuestion.objects.create(
    interview=participant.interview,  # Assumes interview exists
    module=module_instance,
    question_id=1,
    q_content="Tell me about your work experience",
    # ... other fields
)

# Add utterances from the interview
utterances = [
    "I've worked in retail for 5 years.",
    "The pay was always minimum wage.",
    "It was hard to make ends meet.",
]

for i, text in enumerate(utterances):
    InterviewUtterance.objects.create(
        question=question,
        utterance_text=text,
        is_interviewer=False,  # False for participant, True for interviewer
        sequence_number=i,
    )
```

**Option B: Bulk import from JSON**

Structure your data as:

```json
{
  "6672bf56d51710391ce2164d": {
    "questions": [
      {
        "question_id": 1,
        "content": "Tell me about your work experience",
        "utterances": [
          {"text": "I've worked in retail for 5 years.", "is_interviewer": false},
          {"text": "The pay was always minimum wage.", "is_interviewer": false}
        ]
      }
    ]
  }
}
```

Then import:

```python
import json
from pages.models import InterviewUtterance, Participant

with open("data/interviews.json") as f:
    data = json.load(f)

for prolific_id, participant_data in data.items():
    participant = Participant.objects.get(prolific_id=prolific_id)
    # Process and create InterviewUtterance objects
    # (Full implementation depends on your data structure)
```

### Step 3: Add Audio Segments (Optional)

If you have audio files, process them into sentence-level segments:

```bash
# First, upload raw audio to S3 in the expected structure:
# s3://your-bucket/InterviewAudios/{prolific_id}/{question_id}/audio.wav

# Then run the audio processing script:
cd generating_v2
python 05_process_sentence_segments.py
```

This script will:
1. Transcribe audio using Google Cloud Speech API
2. Split into sentence-level segments
3. Create `InterviewSegment` objects with timestamps
4. Link segments to `InterviewUtterance` objects

### Step 4: Create Recommendations

Add policy recommendations for participants to deliberate on:

```python
from pages.models import Recommendation

recommendation = Recommendation.objects.create(
    title="Minimum Wage Policy",
    text="The federal minimum wage should be raised to $30 an hour.",
    description="Policy proposal to raise minimum wage",
    # Additional fields as needed
)
```

Or use Django admin to create recommendations via the web interface.

### Step 5: How Predictions Work

When a user edits a recommendation in the editor, the `recompute_recommendation_stream` view handles the real-time prediction generation.

**Location:** `pages/views.py:2977-3100`

**How it works:**

1. User edits recommendation text in the editor
2. Frontend calls `/api/editor/<rec_id>/recompute-stream/?rec_text=<new_text>`
3. `recompute_recommendation_stream` creates a new Recommendation object
4. Reads participant list from CSV (current hacky implementation):
   ```python
   participant_data = pd.read_csv("data/all_df_clean_pass_concept_measures_joined.csv")
   participant_data = participant_data[participant_data["assignment"].isin(["treatment", "control"])]
   participant_usernames = participant_data["PROLIFIC_PID"].tolist()
   ```
5. Processes participants in parallel (16 workers) using `process_single_participant`
6. For each participant:
   - Calls `RecommendationPredictionGenerator.process_participant_recommendation_fast()`
   - Generates `Medley` with quality score
   - Returns prediction data via Server-Sent Events
7. Saves predictions to `LivePrediction` model
8. Frontend updates visualization in real-time

**To customize which participants are included:**

Edit the CSV path or replace with a direct database query:

```python
# Instead of reading from CSV, query directly:
participants_with_data = Participant.objects.filter(
    has_completed_interview=True
    # Add your filters here
).distinct()
```

## Customizing AI Prompts

All AI prompts are stored in `generating_v2/prompts/`:

- `rec_prediction.txt` - Predicts participant agreement (0-100)
- `rec_evidence.txt` - Extracts supporting/opposing evidence
- `rec_exp_relevance.txt` - Evaluates relevance and depth (0-100)
- `rec_exp_summary.txt` - Generates narrative summary
- `life_narrative.txt` - Creates life story narratives
- `medley_selection.txt` - Selects audio segments for individual medleys
- `meta_medley_selection.txt` - Selects segments for group medleys

Edit these files to customize the AI's behavior. Changes take effect immediately.

## Configuration Options

### Prediction Settings

In `generating_v2/rec_prediction.py`:

```python
class RecommendationPredictionGenerator:
    def __init__(self):
        self.model = "gpt-4o-mini"  # or "gpt-4", "claude-3-5-sonnet"
        self.temperature = 0.7
        self.max_tokens = 2000
```

### Caching

The system caches predictions in `LivePrediction` models. Each time you edit a recommendation, it creates a new Recommendation object and generates fresh predictions. To clear old predictions:

```python
from pages.models import LivePrediction

# Delete existing predictions for a recommendation
LivePrediction.objects.filter(recommendation_id=74).delete()
```

## Deployment

### AWS Elastic Beanstalk

The project is configured for AWS EB deployment:

```bash
# Install EB CLI
pip install awsebcli

# Initialize (first time only)
eb init

# Deploy
eb deploy
```

Configuration files:
- `.ebextensions/` - EB configuration
- `.platform/` - Platform-specific hooks
- `Procfile` - Process configuration (Gunicorn + migrations)

### Environment Variables

Set production environment variables in EB:

```bash
eb setenv OPENAI_API_KEY=xxx
eb setenv AWS_STORAGE_BUCKET_NAME=xxx
eb setenv DJANGO_SETTINGS_MODULE=gabm_infra.settings.production
```

### Database Migration

The Procfile automatically runs migrations on deploy:

```yaml
web: gunicorn --bind :8000 --workers 3 --timeout 300 gabm_infra.wsgi:application
release: python manage.py migrate --noinput
```

## Project Structure

```
agora/
├── gabm_infra/           # Django project settings
│   ├── settings/
│   │   ├── base.py      # Base settings
│   │   ├── local.py     # Local development
│   │   └── production.py # Production settings
│   ├── urls.py          # URL routing
│   └── wsgi.py          # WSGI application
├── pages/               # Main Django app
│   ├── models.py        # Database models
│   ├── views.py         # View logic (Habermas Game in views.py:1060-3000)
│   ├── admin.py         # Django admin config
│   └── management/      # Django management commands
├── templates/           # HTML templates
│   └── pages/
│       └── recommendations/
│           ├── recommendation_editor.html  # Main Habermas Game UI
│           └── habermas_game.html         # Alternative interface
├── static_dirs/         # Static files (CSS, JS, images)
├── generating_v2/       # AI generation scripts
│   ├── rec_prediction.py           # Prediction engine
│   ├── life_narrative.py           # Life narrative generator
│   ├── medley_individual.py        # Individual medley creator
│   ├── meta_medley.py              # Group medley creator
│   ├── prompts/                    # AI prompts
│   └── 01_run_life_narratives.py   # Runner scripts
├── data/                # Data files
│   └── habermas_participants.csv   # Participant data
├── requirements.txt     # Python dependencies
└── .ebextensions/       # AWS EB configuration
```

## Key Dependencies

```
Django==4.2.5              # Web framework
openai==1.61.0             # OpenAI API
anthropic==0.51.0          # Claude API
langchain==0.3.27          # LLM framework
google-cloud-speech==2.23.0 # Audio transcription
pydub==0.25.1              # Audio processing
pandas==2.2.3              # Data manipulation
psycopg2-binary==2.9.9     # PostgreSQL adapter
boto3                      # AWS SDK
gunicorn==21.2.0           # WSGI server
```

## Troubleshooting

### Predictions not generating

Check:
1. OpenAI API key is set correctly
2. Participants have `InterviewUtterance` data
3. Check Django logs for API errors

### Audio not playing

Verify:
1. Audio files are uploaded to S3
2. S3 bucket CORS is configured
3. `InterviewSegment` objects have correct S3 paths

### Slow prediction generation

Solutions:
1. Use `gpt-4o-mini` instead of `gpt-4` (faster, cheaper)
2. Reduce number of participants processed
3. Use caching (predictions are cached by default)

## License

[Specify your license here]

## Support

For issues or questions, see `generating_v2/README.md` for additional documentation on AI generation details.
