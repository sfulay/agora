# Prompt Directory Configuration

This document explains how prompt directories are configured and used in the Agora system.

## Directory Structure

```
generating_v2/
├── prompts/              # Default prompts for Cortico data
│   ├── live_prediction.txt
│   ├── medley_selection.txt
│   └── meta_medley_selection.txt
└── prompts_sfulay/       # Alternative prompts for Sfulay data
    ├── live_prediction.txt
    ├── medley_selection.txt
    └── meta_medley_selection.txt
```

## Configuration

The prompt directory is automatically selected based on the `DATA_TYPE` setting in `gabm_infra/settings/base.py`:

```python
# Data type configuration
# Options: "cortico" or "sfulay"
DATA_TYPE = "cortico"

# Prompt directory configuration based on DATA_TYPE
# Cortico prompts: generating_v2/prompts/
# Sfulay prompts: generating_v2/prompts_sfulay/
if DATA_TYPE == "cortico":
    PROMPT_DIR = "generating_v2/prompts"
else:
    PROMPT_DIR = "generating_v2/prompts_sfulay"
```

## How It Works

1. **Settings Configuration** (`gabm_infra/settings/base.py`)
   - `DATA_TYPE` determines which dataset is being used
   - `PROMPT_DIR` is automatically set based on `DATA_TYPE`

2. **Usage in Code** (`pages/views.py`)
   - `process_single_participant()` receives `settings.PROMPT_DIR` as a parameter
   - Generators are initialized with the appropriate prompt directory:
     ```python
     generator = RecommendationPredictionGenerator(prompt_dir=prompt_dir)
     medley_generator = MedleyGenerator(prompt_dir=prompt_dir)
     ```

3. **Generator Classes**
   - `RecommendationPredictionGenerator` (in `generating_v2/rec_prediction.py`)
   - `MedleyGenerator` (in `generating_v2/medley_individual.py`)
   - Both accept `prompt_dir` parameter in their `__init__` methods

## Customizing Prompts

To customize prompts for a specific dataset:

1. **For Cortico data:**
   - Edit files in `generating_v2/prompts/`
   - Ensure `DATA_TYPE = "cortico"` in settings

2. **For Sfulay data:**
   - Edit files in `generating_v2/prompts_sfulay/`
   - Ensure `DATA_TYPE = "sfulay"` in settings

3. **To add a new prompt file:**
   - Add the `.txt` file to both directories
   - The file stem (filename without extension) becomes the prompt key
   - Access it via `self.prompts['filename']` in generator classes

## Prompt Files

### live_prediction.txt
Used for generating live predictions of participant agreement with recommendations.

### medley_selection.txt
Used for selecting audio segments to create individual participant medleys.

### meta_medley_selection.txt
Used for creating meta-medleys from multiple participants.

## Switching Between Datasets

To switch between Cortico and Sfulay datasets:

1. Open `gabm_infra/settings/base.py`
2. Change `DATA_TYPE = "cortico"` to `DATA_TYPE = "sfulay"` (or vice versa)
3. Restart the Django server
4. The system will automatically use the corresponding prompt directory

## Development Notes

- Prompt files are loaded once when the generator classes are instantiated
- Changes to prompt files require restarting the server or recreating the generator instances
- Both prompt directories should contain the same set of files to ensure consistency
- When adding new prompt files, update both directories
