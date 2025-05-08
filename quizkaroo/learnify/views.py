# learnify/views.py

from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
import requests


GEMINI_API_KEY = 'AIzaSyB-DMnNQo2w5ZLM7UHMdVr_v1Mgn_pBagE'


def search_topic(request):
    return render(request, 'learnify/search.html')





@csrf_exempt
def show_result(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }

        data = {
            "contents": [{
                "parts": [{
                    "text": f"Explain the topic '{topic}' in a simple and detailed way suitable for a student. Present the information in clear, concise summary . Cover each topic on which a quiz is possible . Do not include any symbol except '. or ,' in the response. "
                }]
            }]
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result_data = response.json()
            result_text = result_data['candidates'][0]['content']['parts'][0]['text']
        else:
            result_text = "Error fetching content from Gemini API."

        request.session['current_topic'] = topic
        request.session['current_result'] = result_text

        return render(request, 'learnify/result.html', {'result': result_text, 'topic': topic})
    
    return render(request, 'learnify/search.html')




def learn_more(request):
    if request.method == 'POST':
        topic = request.POST.get('topic') or request.session.get('current_topic')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }

        data = {
            "contents": [{
                "parts": [{
                    "text": f"Provide more detailed insights or advanced concepts about the topic '{topic}' in an engaging way. You should consider that i am searching for quiz or education related content. Only provide me content related to education. Give the content in steps or points. There should also be a summary of the Content in the end."
                }]
            }]
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result_data = response.json()
            result_text = result_data['candidates'][0]['content']['parts'][0]['text']
        else:
            result_text = "Error fetching additional content from Gemini API."

        return render(request, 'learnify/result.html', {'result': result_text, 'topic': topic})
    return render(request, 'learnify/search.html')


def create_quiz(request):
    if request.method == 'POST':
        topic = request.POST.get('topic') or request.session.get('current_topic')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }

        prompt = (
            f"Create a 5 question multiple-choice quiz on the topic '{topic}'. "
            f"For each question, include 4 options (A, B, C, D) and specify the correct answer clearly."
        )

        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result_data = response.json()
            quiz_text = result_data['candidates'][0]['content']['parts'][0]['text']
        else:
            quiz_text = "Error generating quiz from Gemini API."

        return render(request, 'learnify/quiz.html', {'quiz': quiz_text, 'topic': topic})
    return render(request, 'learnify/search.html')