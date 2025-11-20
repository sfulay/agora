# Delib - Interview Analysis Platform

Delib is a Django-based web application designed for analyzing and processing interview data. The platform provides tools for interview transcription, analysis, and recommendation generation.

## Features

- Interview transcription and analysis
- Recommendation generation
- User authentication and management

## Prerequisites

- Python 3.11
- PostgreSQL (for production)
- AWS account (for deployment)
- OpenAI API key (for interviewer and  recommendation generation)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd delib
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
Required environment variables:
- OPENAI_API_KEY: Your OpenAI API key for recommendation generation
- Other configuration variables as needed
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Start the development server:
```bash
python manage.py runserver
```

## Deployment

The application is configured for deployment on AWS Elastic Beanstalk. The deployment process is managed through the `.ebextensions` and `.platform` directories.

### Deployment Steps:

1. Install the AWS Elastic Beanstalk CLI
2. Configure your AWS credentials
3. Deploy using:
```bash
eb deploy
```

## Project Structure

- `gabm_infra/`: Main Django project configuration
- `pages/`: Application pages and views
- `templates/`: HTML templates
- `static_dirs/`: Static files
- `media_root/`: User-uploaded media files
- `interviewer_agent/`: Interview analysis components
- `.ebextensions/`: AWS Elastic Beanstalk configuration
- `.platform/`: Platform-specific configurations
