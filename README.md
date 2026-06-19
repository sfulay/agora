# Agora

Agora is an interactive tool that enables users to iteratively refine policy proposals while receiving real-time AI predictions about public support. Users can edit policy recommendations, see live predictions of how real people would respond based on their interview data, and explore detailed participant perspectives through audio clips and summaries.

https://github.com/user-attachments/assets/26398693-0928-4ffc-be77-d36a7c0fa401

## Core Features

- **Interactive Policy Editor**: Edit policy recommendations in real-time with a 500-character limit
- **Live AI Predictions**: Streaming predictions using GPT-4 to estimate participant support (0-100% agreement)
- **Support Visualization**: Interactive plot showing participant avatars positioned by predicted agreement
- **Participant Profiles**: Detailed views with support scores, AI-generated reasoning, audio clips, and narrative summaries
- **Meta-Medleys**: Group audio summaries combining perspectives from participants who are "Against", "On the fence", or "For" the policy
- **Leaderboard System**: Tracking of user performance in maximizing consensus

## Prerequisites

- Python 3.11
- PostgreSQL (production) or SQLite (development)
- OpenAI API key (GPT-4 access required)
- AWS account (for S3 storage - optional for local dev)
- Google Cloud Speech API credentials (for audio transcription - optional)

## Setup Instructions

### 1. SSH Key Setup
Add `agora.pem` to your `.ssh` folder:
```bash
cp agora.pem ~/.ssh/
chmod 400 ~/.ssh/agora.pem
```

### 2. Environment Variables
Create a `.env` file with:
```bash
OPENAI_API_KEY=your-openai-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
```
**Note:** Use the AWS key with proper permissions (proper permission setup pending).

### 3. Create Conda Environment
```bash
conda create -n agora python=3.11
conda activate agora
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
conda install -c conda-forge awscli
```

### 5. Connect to Production Database

First, set the Elastic Beanstalk environment:
```bash
eb use agora-prolific
```

**Get the current EC2 IP address** (changes when instance restarts):
```bash
eb ssh --dry-run
```

This will output something like:
```
INFO: Running ssh -i /Users/Suyash/.ssh/agora.pem -o IdentitiesOnly yes ec2-user@44.223.23.188
```

Copy the IP address from the output (e.g., `44.223.23.188`).

**SSH with port forwarding:**
```bash
ssh -i ~/.ssh/agora.pem ec2-user@<EC2_IP_ADDRESS> -L 6543:<RDS_DATABASE_HOST>:5432
```

For example:
```bash
ssh -i ~/.ssh/agora.pem ec2-user@<EC2_IP_ADDRESS> -L 6543:<RDS_DATABASE_HOST>:5432
```

**What this does:**
- Connects to the EC2 instance (IP changes when instance restarts)
- Forwards local port `6543` to the RDS PostgreSQL database (port `5432`)
- Allows your local Django app to connect to the production database

**Note:** The EC2 IP address is **dynamic** and will change whenever the Elastic Beanstalk environment is restarted or redeployed. Always check with `eb ssh --dry-run` first.

### 6. Run Development Server
In a new terminal (keep the SSH tunnel running):
```bash
conda activate agora
python manage.py runserver
```

### 7. Access the Editor
Open your browser to:
- `http://localhost:8000/editor/<recommendation_id>/`
- Example: `http://localhost:8000/editor/273/`

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

Agora uses these key models:

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

**InterviewUtterance**: Individual speaker turns from interview transcripts
- `question`: Link to InterviewQuestion
- `utterance_text`: The text of this speaker turn
- `audio_id`: **Required** - References the `id` of the corresponding `InterviewAudio` record
- `is_interviewer`: True if interviewer spoke this, False if participant
- `sequence_number`: Order within the question

**Note:** Each utterance represents a complete speaker turn, not individual sentences. A turn may contain multiple sentences.

**InterviewAudio**: Full audio files for questions
- `question`: Link to InterviewQuestion
- `user_speech`: True if participant speech, False if interviewer
- `audio_file`: Path to audio file in S3 (uploaded by user)

**Relationship:** Each `InterviewUtterance` must have an `audio_id` that points to an `InterviewAudio.id`. When constructing audio URLs, the system uses:
```python
f"InterviewAudios/interview{interview_id}/module{module_id}/question{question_id}/user_{audio_id}.wav"
```

**InterviewSegment**: Sentence-level audio segments within an utterance
- `audio`: Link to InterviewAudio (the parent audio for the full utterance)
- `start_time`: Start time in seconds (within the parent audio)
- `end_time`: End time in seconds (within the parent audio)
- `segment_text`: Transcribed text for this segment (typically one sentence)
- `segment_audio_file`: Path to individual segment audio file in S3
- `sequence_number`: Order within the parent audio file

**Relationship:** Since an `InterviewUtterance` (speaker turn) may contain multiple sentences, `InterviewSegment` objects break down the utterance's audio into sentence-level chunks. Multiple segments can belong to one `InterviewAudio` record.

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

This section explains how to add new participants, interview data, and policy recommendations to Agora.

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

Interview data should be structured as `InterviewUtterance` objects. Each utterance represents a complete speaker turn (which may contain multiple sentences).

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

# Add utterances (speaker turns) from the interview
# Each utterance is a complete turn - may contain multiple sentences
utterances = [
    ("What kind of work have you done?", True),  # Interviewer turn
    ("I've worked in retail for 5 years. The pay was always minimum wage.", False),  # Participant turn
    ("How did that affect you?", True),  # Interviewer turn
    ("It was really hard to make ends meet. I had to work two jobs.", False),  # Participant turn
]

for i, (text, is_interviewer) in enumerate(utterances):
    InterviewUtterance.objects.create(
        question=question,
        utterance_text=text,
        is_interviewer=is_interviewer,
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
          {"text": "What kind of work have you done?", "is_interviewer": true},
          {"text": "I've worked in retail for 5 years. The pay was always minimum wage.", "is_interviewer": false},
          {"text": "How did that affect you?", "is_interviewer": true},
          {"text": "It was really hard to make ends meet.", "is_interviewer": false}
        ]
      }
    ]
  }
}
```

Note: Each utterance represents one complete speaker turn.

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

### Step 3: Add Audio Files

Audio files are essential for Agora to work. Here's how to upload and connect them:

**Step 3.1: Upload Audio to S3**

Upload audio files to S3 following the expected path structure:
```
s3://your-bucket/InterviewAudios/interview{interview_id}/module{module_id}/question{question_id}/user_{audio_id}.wav
```

**Step 3.2: Create InterviewAudio Records**

For each audio file, create an `InterviewAudio` record:

```python
from pages.models import InterviewAudio, InterviewQuestion

# Get the question this audio is for
question = InterviewQuestion.objects.get(id=question_id)

# Create the audio record
audio = InterviewAudio.objects.create(
    question=question,
    user_speech=True,  # True if participant speaking, False if interviewer
    audio_file="InterviewAudios/interview123/module1/question5/user_42.wav"
)

# Note the audio.id - you'll need this for InterviewUtterance
print(f"Created InterviewAudio with id: {audio.id}")
```

**Step 3.3: Link Utterances to Audio**

When creating `InterviewUtterance` objects (from Step 2), set the `audio_id` to reference the `InterviewAudio.id`:

```python
from pages.models import InterviewUtterance

# The audio_id must match an InterviewAudio.id
# Remember: Each utterance is a complete speaker turn
InterviewUtterance.objects.create(
    question=question,
    utterance_text="I've worked in retail for 5 years. The pay was always minimum wage.",
    audio_id=audio.id,  # <-- This is the InterviewAudio.id from Step 3.2
    is_interviewer=False,
    sequence_number=0,
)
```

**Step 3.4: Process Sentence-Level Segments**

**Required for Agora to function properly.**

Since each `InterviewUtterance` (speaker turn) may contain multiple sentences, you need to break down the audio into sentence-level `InterviewSegment` objects:

```bash
cd generating_v2
python 05_process_sentence_segments.py
```

This script:
1. Loads each `InterviewAudio` record
2. Uses Google Cloud Speech API to transcribe with word-level timestamps
3. Detects sentence boundaries within the utterance
4. Splits the audio file into individual sentence segments
5. Creates `InterviewSegment` objects for each sentence with:
   - `start_time` and `end_time` (within the parent audio)
   - `segment_text` (one sentence from the utterance)
   - `segment_audio_file` (individual WAV file)
6. Stores segment files in S3 at: `InterviewAudios/interview{id}/module{id}/question{id}/user_{audio_id}/sentence_{seq}.wav`

**Why this is required:** Agora uses these segments to create Medleys (60-second audio summaries). Medleys select specific sentences from across an utterance, which requires sentence-level segmentation.

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
│   ├── views.py         # View logic (recommendation editor in views.py:2849-3100)
│   ├── admin.py         # Django admin config
│   └── management/      # Django management commands
├── templates/           # HTML templates
│   └── pages/
│       └── recommendations/
│           ├── recommendation_editor.html  # Main Agora UI
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
