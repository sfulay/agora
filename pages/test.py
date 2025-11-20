# Import the models
#%%
from pages.models import Interview, InterviewQuestion, InterviewUtterance

# Find all interviews that have questions with utterances
interviews_with_utterances = Interview.objects.filter(
    interviewquestion__utterances__isnull=False
).distinct()

# Print the count
print(f"Number of interviews with utterances: {interviews_with_utterances.count()}")

# To see the actual interviews and their utterances:
for interview in interviews_with_utterances:
    print(f"\nInterview ID: {interview.id}")
    print(f"Participant: {interview.participant.username}")
    print(f"Script version: {interview.script_v}")
    
    # Get questions with utterances for this interview
    questions = InterviewQuestion.objects.filter(
        interview=interview,
        utterances__isnull=False
    ).distinct()
    
    print(f"Number of questions with utterances: {questions.count()}")
    
    # Print first few utterances for each question
    for question in questions:
        print(f"\nQuestion {question.global_question_id}:")
        utterances = question.utterances.all()
        for utt in utterances:
            print(f"- {'Interviewer' if utt.is_interviewer else 'Interviewee'}: {utt.utterance_text[:50]}...")
# %%
