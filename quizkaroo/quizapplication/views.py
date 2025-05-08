import logging
import requests
logging.basicConfig(level=logging.INFO)  # Adjusted logging level for production
logger = logging.getLogger(__name__)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib.auth.models import Group
import json
from django.core.exceptions import FieldError
from django.views.generic import ListView, DetailView
from .models import Category, Topic, Quiz, Question, Answer, QuizAttempt, QuizReference, QuizResult, UserQuizActivity
from django.contrib import messages
from django.db.models import Q
from decouple import config
import google.generativeai as genai
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .forms import SignupForm, UserProfileForm



FLASK_API_URL = 'http://127.0.0.1:5000'


User = get_user_model()

def landingpage(request):
    return render(request, 'quizzes/landingpage.html')

@login_required
def profilepage(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            success = True
        else:
            success = False
    else:
        form = UserProfileForm(instance=request.user)
        success = None

    return render(request, 'quizzes/profile_page.html', {
        'form': form,
        'success': success
    })

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('quizapplication:profile_page')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'quizzes/profile_page.html', {'form': form})

class CategoryListView(ListView):
    model = Category
    template_name = 'quizzes/category_list.html'
    context_object_name = 'categories'

class TopicListView(ListView):
    model = Topic
    template_name = 'quizzes/topic_list.html'
    context_object_name = 'topics'

    def get_queryset(self):
        self.category = get_object_or_404(Category, pk=self.kwargs['category_id'])
        return Topic.objects.filter(category=self.category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        return context

class QuizListView(ListView):
    model = Quiz
    template_name = 'quizzes/quiz_list.html'
    context_object_name = 'quizzes'

    def get_queryset(self):
        self.topic = get_object_or_404(Topic, pk=self.kwargs['topic_id'])
        return Quiz.objects.filter(topic=self.topic)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topic'] = self.topic
        context['category'] = self.topic.category
        return context

class QuizDetailView(DetailView):
    model = Quiz
    template_name = 'quizzes/quiz_detail.html'
    context_object_name = 'quiz'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.questions.all().order_by('order')
        for question in context['questions']:
            question.answers_list = question.answers.all()
        logger.debug(f"Questions for quiz {self.object.id}: {[q.id for q in context['questions']]}")
        logger.debug(f"Answers for questions: {[(q.id, [a.id for a in q.answers_list]) for q in context['questions']]}")
        return context

def start_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    UserQuizActivity.objects.get_or_create(user=request.user, quiz=quiz)
    request.session[f'quiz_{quiz_id}_start_time'] = timezone.now().isoformat()
    return redirect('quiz_detail', pk=quiz_id)

@login_required
def submit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to submit a quiz.")
        return redirect(reverse('quizapplication:quiz_detail', kwargs={'pk': quiz.id}))

    if request.method == 'POST':
        start_time = request.session.get(f'quiz_{quiz.id}_start_time')
        if start_time:
            time_taken = timezone.now() - timezone.datetime.fromisoformat(start_time)
        else:
            time_taken = timedelta(seconds=0)

        score = 0
        total_questions = quiz.questions.count()

        user_answers = {}
        correct_answers = {}

        for question in quiz.questions.all():
            if question.question_type == Question.SINGLE_CHOICE:
                selected_answer_id = request.POST.get(f'question_{question.id}')
                if not selected_answer_id:
                    messages.error(request, f"Please answer: {question.text}")
                    return redirect(reverse('quizapplication:quiz_detail', kwargs={'pk': quiz.id}))
                selected_answer = get_object_or_404(Answer, id=selected_answer_id)
                user_answers[question.id] = int(selected_answer_id)
                correct_answers[question.id] = question.answers.filter(is_correct=True).first().id if question.answers.filter(is_correct=True).first() else None
                if selected_answer.is_correct:
                    score += 1
            else:
                selected_answer_ids = request.POST.getlist(f'question_{question.id}')
                if not selected_answer_ids:
                    messages.error(request, f"Please answer: {question.text}")
                    return redirect(reverse('quizapplication:quiz_detail', kwargs={'pk': quiz.id}))
                correct_answers_list = list(question.answers.filter(is_correct=True).values_list('id', flat=True))
                selected_answers = [int(id) for id in selected_answer_ids]
                user_answers[question.id] = selected_answers
                correct_answers[question.id] = correct_answers_list
                if set(selected_answers) == set(correct_answers_list):
                    score += 1

        percentage = (score / total_questions) * 100 if total_questions > 0 else 0
        passed = percentage >= quiz.passing_score

        QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            score=score,
            time_taken=time_taken,
            passed=passed
        )

        QuizResult.objects.create(
            user=request.user,
            quiz_name=quiz.title,
            score=score,
        )

        request.session['quiz_results'] = {
            'user_answers': user_answers,
            'correct_answers': correct_answers,
            'quiz_id': quiz_id,
        }

        if passed:
            messages.success(request, f'Passed! Your score: {score}/{total_questions} ({percentage:.2f}%)')
        else:
            messages.warning(request, f'Failed. Your score: {score}/{total_questions} ({percentage:.2f}%)')

            teacher_reference = QuizReference.objects.filter(quiz=quiz, created_by_teacher=True).first()
            if teacher_reference:
                messages.info(request, f"Reference: {teacher_reference.content}")
            else:
                ai_reference = "Check out this helpful explanation based on your mistakes (Gemini output here)."
                messages.info(request, f"AI Reference: {ai_reference}")

        activity, created = UserQuizActivity.objects.get_or_create(user=request.user, quiz=quiz)
        activity.completed = True
        activity.completion_time = timezone.now()
        activity.save()

        share_url = request.build_absolute_uri(reverse('quizapplication:quiz_review'))
        share_text = f"I scored {score}/{total_questions} on the {quiz.title} quiz!"

        request.session['share_info'] = {
            'url': share_url,
            'text': share_text,
        }

        return redirect(reverse('quizapplication:quiz_review'))
    return redirect(reverse('quizapplication:quiz_detail', kwargs={'pk': quiz.id}))






def generate_dynamic_quiz(request):
    return render(request, 'quizzes/dynamic_quiz.html')

def call_gemini_api(query):
    try:
        genai.configure(api_key=config('GEMINI_API_KEY'))
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"""
        Generate a JSON object representing a multiple-choice quiz based on the topic '{query}'. If the topic is empty, choose any general topic.
        The quiz should have:
        - title: A short quiz title (e.g., "{query.capitalize()} Quiz").
        - questions: A list of exactly 2 questions. Each question should have:
            - text: The question text, specific to '{query}'.
            - options: A list of 4 distinct options, relevant to '{query}'.
            - correct_option_index: Index (0, 1, 2, or 3) indicating the correct option.
        Respond with ONLY the JSON object. No explanations or preamble.
        """
        logger.debug(f"Prompt sent to Gemini: {prompt}")
        response = model.generate_content(prompt)
        logger.debug(f"Raw response from Gemini: {response.text}")
        response_text = response.text.strip().strip("```json").strip("```")
        logger.debug(f"Processed response text: {response_text}")
        quiz_data = json.loads(response_text)
        logger.debug(f"Parsed quiz data: {quiz_data}")
        return quiz_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON Parsing Failed: {e}, Response: {response.text if 'response' in locals() else 'No response'}")
        return None  # Remove mock response for production
    except Exception as e:
        logger.error(f"Error during quiz generation: {e}")
        return None

def save_dynamic_quiz(query, quiz_data):
    if not quiz_data or 'title' not in quiz_data or 'questions' not in quiz_data:
        logger.error(f"Invalid quiz_data received: {quiz_data}")
        return None

    try:
        category_name = query.capitalize() + " General"
        category, _ = Category.objects.get_or_create(name=category_name, defaults={'description': f'Quizzes about {query}'})
        logger.debug(f"Created/Retrieved category: {category}")

        topic_name = query.capitalize()
        topic, _ = Topic.objects.get_or_create(name=topic_name, category=category)
        logger.debug(f"Created/Retrieved topic: {topic}")

        quiz = Quiz.objects.create(title=quiz_data['title'], topic=topic, is_dynamic=True)
        logger.debug(f"Created quiz: {quiz}")

        questions = quiz_data.get('questions', [])
        logger.debug(f"Number of questions to process: {len(questions)}, Questions data: {questions}")
        if not questions:
            logger.error(f"No questions found in quiz_data for quiz {quiz.id}")
            return quiz

        for idx, q in enumerate(questions):
            if not all(key in q for key in ['text', 'options', 'correct_option_index']):
                logger.error(f"Invalid question data at index {idx} skipped: {q}")
                continue
            try:
                question = Question.objects.create(quiz=quiz, text=q['text'], question_type=Question.SINGLE_CHOICE, order=idx + 1)
                logger.debug(f"Created question {idx + 1}: {question}")
                for i, option_text in enumerate(q.get('options', [])):
                    try:
                        is_correct = (i == q.get('correct_option_index', 0))
                        answer = Answer.objects.create(question=question, text=option_text, is_correct=is_correct)
                        logger.debug(f"Created answer for question {question.id}: {answer}, is_correct: {is_correct}")
                    except Exception as answer_error:
                        logger.error(f"Error creating answer for question {question.id}: {answer_error}")
            except Exception as question_error:
                logger.error(f"Error creating question at index {idx}: {question_error}")
        return quiz
    except Exception as e:
        logger.error(f"Database error for quiz {quiz.id if 'quiz' in locals() else 'N/A'}: {e}")
        return None

class QuizSearchView(ListView):
    model = Quiz
    template_name = 'quizzes/quiz_list.html'
    context_object_name = 'quizzes'

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if not query:
            return Quiz.objects.all()

        try:
            queryset = Quiz.objects.filter(
                Q(title__icontains=query) |
                Q(topic__name__icontains=query) |
                Q(topic__category__name__icontains=query)
            )
        except FieldError:
            queryset = Quiz.objects.none()

        if not queryset.exists():
            try:
                quiz_data = call_gemini_api(query)
                if quiz_data:
                    new_quiz = save_dynamic_quiz(query, quiz_data)
                    if new_quiz:
                        messages.info(self.request, f"Generated a new quiz: {new_quiz.title}")
                        return Quiz.objects.filter(id=new_quiz.id)
                    else:
                        messages.error(self.request, "Failed to save generated quiz.")
                else:
                    messages.error(self.request, "Failed to generate quiz from Gemini API.")
            except Exception as e:
                messages.error(self.request, f"Could not generate quiz: {str(e)}")
            return Quiz.objects.filter(
                Q(title__icontains=query) |
                Q(topic__name__icontains=query) |
                Q(topic__category__name__icontains=query)
            ).distinct()

        return queryset

@login_required
def my_quizzes(request):
    try:
        headers = {'Content-Type': 'application/json', 'X-User-Id': str(request.user.id)}
        response = requests.get(f'{FLASK_API_URL}/quizzes', headers=headers)
        response.raise_for_status()
        quizzes_data = response.json()
        my_quizzes = [quiz for quiz in quizzes_data if quiz.get('created_by_id') == request.user.id]
        logger.debug(f"My quizzes data: {my_quizzes}")
        return render(request, 'quizzes/my_quizzes.html', {'quizzes': my_quizzes})
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching quizzes: {e}")
        messages.error(request, f"Could not retrieve quizzes: {e}")
        return render(request, 'quizzes/my_quizzes.html', {'quizzes': []})

def logout_view(request):
    logout(request)
    return redirect('login')

def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.cleaned_data['password']
            user.set_password(password)
            user.save()

            role = form.cleaned_data['role']
            if role == 'student':
                group = Group.objects.get(name='student')
                user.groups.add(group)
            elif role == 'teacher':
                group = Group.objects.get(name='teacher')
                user.groups.add(group)
            return redirect('login')
    else:
        form = SignupForm()
    return render(request, 'registration/signup.html', {'form': form})

def user_progress(request):
    if request.user.is_authenticated:
        results = QuizResult.objects.filter(user=request.user).order_by('-timestamp')
    else:
        results = QuizResult.objects.all().order_by('-timestamp')

    return render(request, 'quizzes/user_progress.html', {'results': results})

@login_required
def quiz_review(request):
    quiz_results = request.session.get('quiz_results')
    if not quiz_results:
        return redirect('quizapplication:quiz_list')  # Redirect if no results

    quiz = get_object_or_404(Quiz, pk=quiz_results['quiz_id'])
    questions = quiz.questions.all()

    review_data = []
    for question in questions:
        user_answer = quiz_results['user_answers'].get(question.id)
        correct_answer = quiz_results['correct_answers'].get(question.id)
        review_data.append({
            'question': question,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'answers': question.answers.all(),
        })

    return render(request, 'quizzes/quiz_review.html', {'review_data': review_data})

@login_required
def user_activity(request):
    activities = UserQuizActivity.objects.filter(user=request.user).order_by('-start_time')
    return render(request, 'quizzes/user_activity.html', {'activities': activities})




@login_required
def update_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if request.method == 'POST':
        logger.debug(f"Received POST request to update quiz {quiz_id}")
        logger.debug(f"Request POST data: {request.POST}")  # Log the entire POST data

        quiz_data = {
            'title': request.POST.get('title'),
            'description': request.POST.get('description'),
            'passing_score': request.POST.get('passing_score'),
            'is_dynamic': request.POST.get('is_dynamic'),
            'questions': []
        }
        num_questions = int(request.POST.get('num_questions', 1))
        logger.debug(f"Number of questions from request: {num_questions}")

        for i in range(1, num_questions + 1):
            question_data = {
                'text': request.POST.get(f'question_{i}_text'),
                'question_type': request.POST.get(f'question_{i}_type'),
                'order': i,
                'answers': []
            }
            for j in range(1, 5):
                answer_data = {
                    'text': request.POST.get(f'question_{i}_answer_{j}_text'),
                    'is_correct': request.POST.get(f'question_{i}_answer_{j}_correct') == 'on'
                }
                question_data['answers'].append(answer_data)
            quiz_data['questions'].append(question_data)
        logger.debug(f"Constructed quiz_data to send to Flask: {json.dumps(quiz_data, indent=2)}")

        try:
            headers = {'Content-Type': 'application/json', 'X-User-Id': str(request.user.id)}
            response = requests.put(f'{FLASK_API_URL}/quizzes/{quiz_id}', data=json.dumps(quiz_data), headers=headers)
            response.raise_for_status()
            logger.debug(f"Flask API response: Status Code: {response.status_code}, Content: {response.text}")
            messages.success(request, "Quiz updated successfully!")
            return redirect(reverse('quizapplication:quiz_detail', kwargs={'pk': quiz_id}))
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating quiz: {e}")
            if e.response:
                logger.error(f"Flask response details: {e.response.status_code}, {e.response.text}")
            messages.error(request, f"Failed to update quiz: {e}")
            return render(request, 'quizzes/quiz_update.html', {'quiz': quiz})
    else:
        try:
            flask_response = requests.get(f'{FLASK_API_URL}/quizzes/{quiz_id}')
            flask_response.raise_for_status()
            quiz_data = flask_response.json()
            logger.debug(f"Fetched quiz data from Flask for editing: {json.dumps(quiz_data, indent=2)}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch quiz data from Flask: {e}. Using Django data.")
            quiz_data = {
                'title': quiz.title,
                'description': quiz.description,
                'questions': [{
                    'text': q.text,
                    'question_type': q.question_type,
                    'order': q.order,
                    'answers': [{'text': a.text, 'is_correct': a.is_correct} for a in q.answers.all()]
                } for q in quiz.questions.all()]
            }
        return render(request, 'quizzes/quiz_update.html', {'quiz': quiz, 'quiz_data': quiz_data})



@login_required
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)  # Fetch the quiz object
    if request.method == 'POST':
        try:
            headers = {'Content-Type': 'application/json', 'X-User-Id': str(request.user.id)}
            response = requests.delete(f'{FLASK_API_URL}/quizzes/{quiz_id}', headers=headers)
            response.raise_for_status()
            messages.success(request, "Quiz deleted successfully!")
            return redirect(reverse('quizapplication:quiz_list', kwargs={'topic_id': quiz.topic.id}))  # Use quiz.topic.id
        except requests.exceptions.RequestException as e:
            logger.error(f"Error deleting quiz: {e}")
            messages.error(request, f"Failed to delete quiz: {e}")
            return redirect(reverse('quizapplication:quiz_detail', kwargs={'pk': quiz_id}))
    else:
        return render(request, 'quizzes/quiz_delete_confirm.html', {'quiz': quiz})  # Pass the quiz object





@login_required
def create_manual_quiz_from_django(request):
    if request.method == 'POST':
        logger.info("Manual quiz creation started.")
        quiz_data = {
            'title': request.POST.get('title'),
            'description': request.POST.get('description'),
            'questions_data': []
        }
        logger.info(f"Quiz data from form: {quiz_data}")
        num_questions = int(request.POST.get('num_questions', 1))
        logger.info(f"Number of questions: {num_questions}")

        for question_number in range(1, num_questions + 1):
            question_text = request.POST.get(f'question_{question_number}_text')
            if not question_text:
                logger.warning(f"Question {question_number} text is empty, skipping.")
                continue
            question_data = {
                'text': question_text,
                'question_type': request.POST.get(f'question_{question_number}_type', 'SC'),
                'order': question_number,
                'answers': []
            }
            logger.info(f"Question data: {question_data}")
            for answer_number in range(1, 5):
                answer_text = request.POST.get(f'question_{question_number}_answer_{answer_number}_text')
                if not answer_text:
                    logger.warning(f"Answer {answer_number} for question {question_number} is empty, skipping.")
                    continue
                is_correct = request.POST.get(f'question_{question_number}_answer_{answer_number}_correct_{question_number}_{answer_number}') == 'on'
                answer_data = {
                    'text': answer_text,
                    'is_correct': is_correct
                }
                logger.info(f"Answer data: {answer_data}")
                question_data['answers'].append(answer_data)
            quiz_data['questions_data'].append(question_data)

        logger.info(f"Final quiz data to send to Flask: {quiz_data}")

        try:
            headers = {'Content-Type': 'application/json', 'X-User-Id': str(request.user.id)}  # Send User ID
            # --- Django DB Saving for Topic (ONLY) ---
            category, _ = Category.objects.get_or_create(name="Manual Quizzes", defaults={'description': 'Manually created quizzes'})
            topic, _ = Topic.objects.get_or_create(name="General", category=category)

            # --- Send topic_id to Flask ---
            quiz_data['topic_id'] = topic.id  # Add topic_id to the data
            response = requests.post(f'{FLASK_API_URL}/quizzes', data=json.dumps(quiz_data), headers=headers)
            response.raise_for_status()
            flask_response_data = response.json()
            logger.info(f"Flask API response: {flask_response_data}")

            # --- Redirect ---
            #  Adjust the redirect as needed.  If Flask returns the new quiz's ID,
            #  you could redirect to the quiz detail page.
            return redirect(reverse('quizapplication:quiz_list', kwargs={'topic_id': topic.id}))

        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Flask API: {e}")
            return render(request, 'quizzes/create_quiz.html', {'error': f'Failed to create quiz: {e}'})
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return render(request, 'quizzes/create_quiz.html', {'error': f'Error: {e}'})

    else:
        return render(request, 'quizzes/create_quiz.html')





def my_quizzes(request):
    user_quizzes = Quiz.objects.filter(
            # Assuming you have a field like 'created_by' in your Quiz model
            # that stores the user who created the quiz.
            # Adjust this filter as needed based on your model.
    created_by=request.user  
        )
    return render(request, 'quizzes/my_quizzes.html', {'quizzes': user_quizzes})