import logging
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

def my_quizzes(request):
    return render(request, 'quizzes/my_quizzes.html')

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