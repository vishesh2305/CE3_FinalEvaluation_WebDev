import os
import sys
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields, ValidationError
import logging

# Django Setup
# Ensure the path to your Django project is correct
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'quizkaroo')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quizkaro.settings') # Ensure 'quizkaro.settings' is correct
import django
django.setup()

# Import Django models AFTER django.setup()
from quizapplication.models import Quiz, Question, Answer, Topic # Assuming Topic might be needed for topic_id validation or creation

app = Flask(__name__)
# Ensure the path to your SQLite database is correct relative to this flask_quiz_api directory
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), '..', 'quizkaroo', 'db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # This SQLAlchemy instance is not used if you're only using Django ORM

# Logger Setup
logging.basicConfig(level=logging.DEBUG) # Set to INFO for production
logger = app.logger

# ------------------ Schemas ------------------

class AnswerSchema(Schema):
    id = fields.Integer(dump_only=True)
    text = fields.String(required=True)
    # Use 'load_default' for default value during deserialization (loading) if field is not present.
    # Removed redundant 'load_default'.
    is_correct = fields.Boolean(required=False, load_default=False)

class QuestionSchema(Schema):
    id = fields.Integer(dump_only=True)
    text = fields.String(required=True)
    # Use 'load_default' for default value during deserialization.
    # Removed redundant 'load_default'.
    question_type = fields.String(required=False, load_default='SC')
    order = fields.Integer(required=False)

    # For LOADING answers from input JSON (e.g., when creating a quiz via POST /quizzes)
    # This field will expect a key "answers" in the input question object.
    # Marshmallow will use AnswerSchema to validate each item in this list.
    answers_input = fields.List(
        fields.Nested(AnswerSchema),
        data_key="answers",    # Expects "answers" key in the input JSON for a question
        load_only=True,        # This field definition is only used during schema.load()
        required=False         # Set to True if every question must have answers during creation
    )

    # For DUMPING answers to output JSON (e.g., when fetching a quiz via GET /quizzes)
    # This field will generate a key "answers" in the output JSON by calling the serialize_answers method.
    answers_output = fields.Method(
        "serialize_answers",
        dump_only=True,        # This field definition is only used during schema.dump()
        data_key="answers"     # The key in the output JSON will be "answers"
    )

    def serialize_answers(self, question_obj):
        """
        Serializes the answers related to a Django Question model instance.
        It fetches all related answer objects using the reverse ForeignKey manager.
        """
        answer_queryset = None
        # Django's default reverse accessor is 'answer_set' if related_name isn't specified
        # on the ForeignKey from Answer to Question.
        if hasattr(question_obj, 'answer_set') and hasattr(question_obj.answer_set, 'all'):
            answer_queryset = question_obj.answer_set.all()
        # If you have defined related_name='answers' on the ForeignKey in Answer model:
        elif hasattr(question_obj, 'answers') and hasattr(question_obj.answers, 'all'):
            answer_queryset = question_obj.answers.all()
        else:
            obj_id = getattr(question_obj, 'id', 'N/A (object not saved or no ID)')
            app.logger.warning(
                f"Question (ID: {obj_id}) does not have a recognizable related manager "
                f"for answers (checked 'answer_set' and 'answers'). Returning empty list for answers."
            )
            return []
        
        return AnswerSchema(many=True).dump(answer_queryset)

class QuizSchema(Schema):
    id = fields.Integer(dump_only=True)
    title = fields.String(required=True)
    description = fields.String(allow_none=True, load_default='') # Default to empty string if not provided
    topic_id = fields.Integer(required=True) # Ensure this topic_id exists in your Django Topic model
    created_by_id = fields.Integer(dump_only=True) # Assuming this is set by the server

    # For LOADING questions from input JSON (e.g., POST /quizzes)
    # It expects a key "questions_data" in the input JSON.
    questions_data = fields.List(
        fields.Nested(QuestionSchema), # Uses the updated QuestionSchema for each question
        required=True
        # data_key="questions_data" is implicit if the field name matches the JSON key.
        # If your JSON key is different, uncomment and set: data_key="your_json_key_for_questions"
    )

    # For DUMPING questions to output JSON (e.g., GET /quizzes)
    # This generates a "questions" key in the output JSON by calling serialize_questions.
    questions = fields.Method("serialize_questions", dump_only=True)

    def serialize_questions(self, quiz_obj):
        """
        Serializes the questions related to a Django Quiz model instance.
        """
        # 'questions' is the default related_name for a ForeignKey from Question to Quiz
        # if you haven't specified a custom related_name.
        if hasattr(quiz_obj, 'questions') and hasattr(quiz_obj.questions, 'all'):
            question_list = quiz_obj.questions.all()
            return QuestionSchema(many=True).dump(question_list) # Uses updated QuestionSchema for dumping
        else:
            app.logger.warning(f"Quiz (ID: {quiz_obj.id}) does not have a 'questions' related manager.")
            return []

# ------------------ Routes ------------------

@app.route('/quizzes', methods=['GET'])
def get_quizzes():
    quizzes = Quiz.objects.all()
    # logger.debug(f"Quizzes from DB: {quizzes}") # For debugging
    return jsonify(QuizSchema(many=True).dump(quizzes)), 200

@app.route('/quizzes/<int:quiz_id>', methods=['GET'])
def get_quiz(quiz_id):
    try:
        quiz = Quiz.objects.get(pk=quiz_id)
        # logger.debug(f"Quiz from DB: {quiz}") # For debugging
        return jsonify(QuizSchema().dump(quiz)), 200
    except Quiz.DoesNotExist:
        logger.warning(f"Quiz with ID {quiz_id} not found.")
        return jsonify({'message': 'Quiz not found'}), 404

@app.route('/quizzes', methods=['POST'])
def create_quiz():
    json_data = request.get_json()
    if not json_data:
        logger.error("No input data provided for create_quiz.")
        return jsonify({'message': 'No input data provided'}), 400

    schema = QuizSchema()
    try:
        # Validate the incoming JSON data against the schema
        validated_data = schema.load(json_data)
        logger.debug(f"Validated data for quiz creation: {validated_data}")
    except ValidationError as err:
        logger.error(f"Validation error during quiz creation: {err.messages}")
        return jsonify(err.messages), 400

    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.error("User ID is required in X-User-Id header for create_quiz.")
            return jsonify({'message': 'User ID is required in X-User-Id header'}), 400
        
        # Optional: Check if topic_id exists
        try:
            Topic.objects.get(pk=validated_data['topic_id'])
        except Topic.DoesNotExist:
            logger.error(f"Topic with ID {validated_data['topic_id']} not found.")
            return jsonify({'message': f"Topic with ID {validated_data['topic_id']} not found."}), 400


        quiz = Quiz.objects.create(
            title=validated_data['title'],
            description=validated_data.get('description', ''), # Uses 'load_default' default from schema if not present
            topic_id=validated_data['topic_id'],
            is_dynamic=False,  # Assuming default, adjust if needed
            created_by_id=user_id # Make sure your Quiz model has 'created_by_id' or similar
        )
        logger.info(f"Quiz created with ID: {quiz.id}")

        # Iterate through the validated questions_data
        # Each item in validated_data['questions_data'] is a dictionary
        # that has passed QuestionSchema validation, including 'answers_input'.
        for question_payload in validated_data.get('questions_data', []):
            question = Question.objects.create(
                quiz=quiz,
                text=question_payload['text'],
                question_type=question_payload.get('question_type', 'SC'), # Uses 'load_default' default
                order=question_payload.get('order', 1) # Assuming default order
            )
            logger.info(f"Question created with ID: {question.id} for Quiz ID: {quiz.id}")

            # Iterate through the 'answers_input' that was loaded and validated by QuestionSchema
            # The key 'answers_input' comes from the field name in QuestionSchema
            for answer_payload in question_payload.get('answers_input', []):
                Answer.objects.create(
                    question=question,
                    text=answer_payload['text'],
                    is_correct=answer_payload.get('is_correct', False) # Uses 'load_default' default
                )
                logger.info(f"Answer created for Question ID: {question.id}")

        return jsonify({'message': 'Quiz created successfully', 'quiz_id': quiz.id}), 201

    except Exception as e:
        logger.error(f"Error creating quiz in database: {e}", exc_info=True)
        # Consider Django transactions if multiple objects are created:
        # from django.db import transaction
        # with transaction.atomic():
        #    ... your creation logic ...
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500


@app.route('/quizzes/<int:quiz_id>', methods=['PUT'])
def update_quiz(quiz_id):
    json_data = request.get_json()
    if not json_data:
        return jsonify({'message': 'No input data provided'}), 400

    try:
        quiz = Quiz.objects.get(pk=quiz_id)
    except Quiz.DoesNotExist:
        return jsonify({'message': 'Quiz not found'}), 404

    # For PUT, you might want a different schema or to use partial=True
    # For simplicity, we'll manually update fields. A schema for updates is better.
    # schema = QuizSchema(partial=True) # If you want to validate partial updates
    # try:
    #     validated_data = schema.load(json_data)
    # except ValidationError as err:
    #     return jsonify(err.messages), 400

    try:
        quiz.title = json_data.get('title', quiz.title)
        quiz.description = json_data.get('description', quiz.description)
        
        if 'topic_id' in json_data:
            try:
                Topic.objects.get(pk=json_data['topic_id'])
                quiz.topic_id = json_data['topic_id']
            except Topic.DoesNotExist:
                 return jsonify({'message': f"Topic with ID {json_data['topic_id']} not found."}), 400
        
        quiz.save()
        logger.info(f"Quiz metadata updated for ID: {quiz_id}")

        # If 'questions' are provided in the payload for PUT, replace all existing questions.
        # Note: The key in JSON for PUT is 'questions' as per your original update_quiz
        if 'questions' in json_data: # This should ideally match 'questions_data' for consistency or use a specific update schema
            quiz.questions.all().delete() # Delete old questions
            logger.info(f"Deleted existing questions for Quiz ID: {quiz_id}")
            
            # Assuming the structure of 'questions' in PUT is similar to 'questions_data' in POST
            # It would be better to validate this structure with a schema.
            for q_data in json_data['questions']:
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data['text'],
                    question_type=q_data.get('question_type', 'SC'),
                    order=q_data.get('order', 1)
                )
                logger.info(f"Created new Question ID: {question.id} for Quiz ID: {quiz_id} during update")
                for a_data in q_data.get('answers', []):
                    Answer.objects.create(
                        question=question,
                        text=a_data['text'],
                        is_correct=a_data.get('is_correct', False)
                    )
                    logger.info(f"Created new Answer for Question ID: {question.id} during update")
        
        return jsonify(QuizSchema().dump(quiz)), 200 # Return the updated quiz
    except Exception as e:
        logger.error(f"Error updating quiz ID {quiz_id}: {e}", exc_info=True)
        return jsonify({'message': str(e)}), 500

@app.route('/quizzes/<int:quiz_id>', methods=['DELETE'])
def delete_quiz(quiz_id):
    try:
        quiz = Quiz.objects.get(pk=quiz_id)
        quiz.delete()
        logger.info(f"Quiz ID: {quiz_id} deleted successfully.")
        return jsonify({'message': 'Quiz deleted'}), 200 # Or 204 No Content
    except Quiz.DoesNotExist:
        logger.warning(f"Attempted to delete non-existent Quiz ID: {quiz_id}")
        return jsonify({'message': 'Quiz not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting quiz ID {quiz_id}: {e}", exc_info=True)
        return jsonify({'message': str(e)}), 500

# ------------------ Question Endpoints (Example, may need schema adjustments) ------------------
# These are simplified and might need robust schema validation similar to Quiz creation

@app.route('/questions/<int:question_id>', methods=['GET'])
def get_question(question_id):
    try:
        question = Question.objects.get(pk=question_id)
        return jsonify(QuestionSchema().dump(question)), 200
    except Question.DoesNotExist:
        return jsonify({'message': 'Question not found'}), 404

@app.route('/questions', methods=['POST'])
def create_question(): # Typically questions are created as part of a quiz
    json_data = request.get_json()
    quiz_id = request.args.get('quiz_id') # Requires quiz_id as query param
    if not quiz_id:
        return jsonify({'message': 'quiz_id query parameter is required'}), 400

    try:
        quiz = Quiz.objects.get(pk=quiz_id)
    except Quiz.DoesNotExist:
        return jsonify({'message': f'Quiz with id {quiz_id} not found'}), 404

    # Simplified: Use QuestionSchema for validation
    schema = QuestionSchema()
    try:
        validated_data = schema.load(json_data) # This will load 'answers_input'
    except ValidationError as err:
        return jsonify(err.messages), 400
        
    try:
        question = Question.objects.create(
            quiz=quiz,
            text=validated_data['text'],
            question_type=validated_data.get('question_type', 'SC'),
            order=validated_data.get('order', 1)
        )
        for a_data in validated_data.get('answers_input', []): # Use validated answers_input
            Answer.objects.create(
                question=question,
                text=a_data['text'],
                is_correct=a_data.get('is_correct', False)
            )
        return jsonify(QuestionSchema().dump(question)), 201
    except Exception as e:
        logger.error(f"Error creating question: {e}", exc_info=True)
        return jsonify({'message': str(e)}), 500


@app.route('/questions/<int:question_id>', methods=['PUT'])
def update_question(question_id):
    # Similar to update_quiz, this should ideally use a schema for validation
    json_data = request.get_json()
    try:
        question = Question.objects.get(pk=question_id)
        question.text = json_data.get('text', question.text)
        question.question_type = json_data.get('question_type', question.question_type)
        question.order = json_data.get('order', question.order)
        question.save()

        if 'answers' in json_data: # Assuming 'answers' key for updates
            question.answer_set.all().delete()
            for a_data in json_data['answers']:
                Answer.objects.create(
                    question=question,
                    text=a_data['text'],
                    is_correct=a_data.get('is_correct', False)
                )
        return jsonify(QuestionSchema().dump(question)), 200
    except Question.DoesNotExist:
        return jsonify({'message': 'Question not found'}), 404
    except Exception as e:
        logger.error(f"Error updating question: {e}", exc_info=True)
        return jsonify({'message': str(e)}), 500

@app.route('/questions/<int:question_id>', methods=['DELETE'])
def delete_question(question_id):
    try:
        question = Question.objects.get(pk=question_id)
        question.delete()
        return jsonify({'message': 'Question deleted'}), 200 # Or 204
    except Question.DoesNotExist:
        return jsonify({'message': 'Question not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting question: {e}", exc_info=True)
        return jsonify({'message': str(e)}), 500

# ------------------ Main ------------------

if __name__ == '__main__':
    # Make sure the host and port are accessible if testing from another machine/container
    app.run(debug=True, host='0.0.0.0') # host='0.0.0.0' makes it accessible externally
