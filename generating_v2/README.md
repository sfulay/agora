# Generation Systems

This directory contains two main generation systems for analyzing participant interview transcripts:

## 1. Life Narrative Generation System

Extracts and summarizes life-related information from participant interview transcripts.

### Structure

- `life_narrative.py` - Main generator class and functionality
- `run_life_narratives.py` - Example script showing how to use the generator
- `prompts/` - Directory containing prompt templates
  - `life_utterances.txt` - Prompt for selecting life-related utterances
  - `life_explanation.txt` - Prompt for generating explanations with highlighted phrases
  - `life_summary.txt` - Prompt for generating life summaries

## 2. Recommendation Prediction System

Analyzes participant transcripts to predict agreement with recommendations and extract relevant evidence.

### Structure

- `rec_prediction.py` - Main generator class and functionality
- `run_rec_predictions.py` - Example script showing how to use the generator
- `prompts/` - Directory containing prompt templates
  - `rec_prediction.txt` - Prompt for predicting participant agreement
  - `rec_evidence.txt` - Prompt for extracting best supporting evidence
  - `rec_exp_relevance.txt` - Prompt for evaluating evidence relevance and depth
  - `rec_exp_summary.txt` - Prompt for summarizing evidence

## Usage

### Life Narrative Generation

#### Basic Usage

```python
from life_narrative import LifeNarrativeGenerator

# Initialize generator
generator = LifeNarrativeGenerator()

# Process a single participant
result = generator.process_participant("username")

# Process multiple participants
usernames = ["user1", "user2", "user3"]
results = generator.save_life_narratives(usernames)
```

#### Running the Script

```bash
# Run for all participants
python life_narrative.py

# Or use the example script
python run_life_narratives.py
```

### Recommendation Prediction

#### Basic Usage

```python
from rec_prediction import RecommendationPredictionGenerator

# Initialize generator
generator = RecommendationPredictionGenerator()

# Process a single participant-recommendation combination
result = generator.process_participant_recommendation("username", "recommendation text", "display name")

# Process multiple participants for multiple recommendations
usernames = ["user1", "user2", "user3"]
recommendation_ids = [74, 75, 76]
results = generator.save_recommendation_summaries(usernames, recommendation_ids)
```

#### Running the Script

```bash
# Run for all participants
python rec_prediction.py

# Or use the example script
python run_rec_predictions.py
```

## Prompt Files Explained

The prompts are stored in `generating_v2/prompts/` as text files. Each prompt controls a specific aspect of the AI generation process:

### Life Narrative Prompts

#### `life_utterances.txt`
- **Purpose**: Selects the most relevant utterances that help understand the participant's life
- **Output**: List of utterance IDs and text that capture interesting personal experiences
- **Key Features**: Biases towards personal experiences, selects up to 2 utterances
- **Variables**: `{display_name}`, `{transcript}`

#### `life_explanation.txt`
- **Purpose**: Generates explanations for selected utterances with highlighted key phrases
- **Output**: Bolded utterance text and AI explanation
- **Key Features**: Highlights key phrases using `<b>` tags, provides short summaries
- **Variables**: `{utterance}`, `{display_name}`

#### `life_summary.txt`
- **Purpose**: Creates a comprehensive life summary from multiple utterances
- **Output**: Concise summary of the participant's life and background
- **Key Features**: Uses participant's name, stays under 50 words, focuses on experiences
- **Variables**: `{display_name}`, `{utterances}`

### Recommendation Prediction Prompts

#### `rec_prediction.txt`
- **Purpose**: Predicts how much a participant would agree with a specific recommendation
- **Output**: Agreement level (0-100), confidence score, and reasoning
- **Key Features**: Analyzes transcript for evidence, provides brief explanation
- **Variables**: `{transcript}`, `{rec_text}`, `{display_name}`

#### `rec_evidence.txt`
- **Purpose**: Identifies the best supporting evidence from the transcript
- **Output**: Top 2 most relevant utterances with bolding and explanations
- **Key Features**: Biases towards personal experiences, avoids opinion statements, highlights key phrases
- **Variables**: `{transcript}`, `{reasoning}`, `{rec_text}`

#### `rec_exp_relevance.txt`
- **Purpose**: Evaluates how relevant and deep the evidence is to the recommendation
- **Output**: Relevance score (0-100), depth score, and explanation
- **Key Features**: Assesses direct relevance and meaningfulness of experiences
- **Variables**: `{experiences}`, `{rec_text}`

#### `rec_exp_summary.txt`
- **Purpose**: Creates a summary of the evidence in relation to the recommendation
- **Output**: Concise summary of how evidence relates to the recommendation
- **Key Features**: Focuses on relevance to recommendation, maintains participant voice
- **Variables**: `{experiences}`

## Customizing Prompts

Each prompt uses Python string formatting with variables like `{display_name}`, `{transcript}`, `{rec_text}`, etc. You can modify these files to change the behavior of the AI:

- **Selection criteria**: Modify prompts to change what types of utterances are selected
- **Output format**: Adjust prompts to change the structure of AI responses
- **Bias preferences**: Change prompts to prioritize different types of content
- **Length constraints**: Modify word limits and summary lengths

## Output

### Life Narrative System
The system generates:
1. **Life narratives** stored in the `ParticipantNarrative` model
2. **Narrative parts** stored in the `ParticipantNarrativePart` model
3. **Life summaries** stored in the `global_summary` field

Each narrative part includes:
- Original utterance text with highlighted key phrases
- AI-generated explanation
- Reference to the original utterance

### Recommendation Prediction System
The system generates:
1. **Recommendation summaries** stored in the `RecommendationParticipantSummary` model
2. **Predictions** including agreement level, confidence score, and reasoning
3. **Evidence extraction** identifying the best supporting evidence (top 2 utterances)
4. **Quality assessments** for evidence relevance and depth
5. **Comprehensive summaries** of how evidence relates to the recommendation

Each summary includes:
- Predicted agreement level (0-100)
- Confidence score (0-100)
- Reasoning for the prediction
- Relevance score for evidence
- Depth score for evidence quality
- Best supporting utterance
- Comprehensive summary text
- Bolded evidence text with highlighted key phrases

## Key Features

### Text Bolding
Both systems include text bolding functionality that highlights key phrases in utterances using `<b>` tags. This improves readability and helps identify the most relevant parts of the transcript.

### Experience Bias
The recommendation prediction system is specifically designed to bias towards personal experiences rather than opinion statements, focusing on how recommendations would impact participants' lives.

### Modular Design
All prompts are stored as separate text files, making it easy to modify and experiment with different approaches without changing the core code.

## Dependencies

- Django models from `pages.models`
- OpenAI API for GPT-4 generation
- pandas for data loading 