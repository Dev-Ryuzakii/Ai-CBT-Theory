from flask import Flask, request, render_template, redirect, url_for, flash, session
import joblib
import pandas as pd
from preprocessing import preprocess_text
from database import SessionLocal, Question, Student, Response
from ollama_service import ollama_service, fallback_similarity_score
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
import os
import docx
import logging
from datetime import datetime
import uuid
from api_service import register_api_routes

app = Flask(__name__)
app.secret_key = 'a4cb44f1bd507ee6f856d6977ffacc60'  # Set your secret key here

# Store active sessions to prevent multiple logins
active_sessions = {}

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Try to load the old model as fallback, but don't fail if it doesn't exist
model = None
vectorizer = None
try:
    model = joblib.load('../models/marking_model.pkl')
    vectorizer = joblib.load('../models/vectorizer.pkl')
    logging.info("Loaded traditional ML model as fallback")
except Exception as e:
    logging.warning(f"Could not load traditional model: {e}. Will use Ollama only.")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_user_logged_in(matric_number):
    """Check if a user is already logged in"""
    return matric_number in active_sessions

def create_session(matric_number, student_id, user_type='student'):
    """Create a new session for a user"""
    session_id = str(uuid.uuid4())
    active_sessions[matric_number] = {
        'session_id': session_id,
        'student_id': student_id,
        'user_type': user_type,
        'login_time': datetime.now(),
        'last_activity': datetime.now()
    }
    session['session_id'] = session_id
    session['matric_number'] = matric_number
    session['student_id'] = student_id
    session['user_type'] = user_type
    return session_id

def validate_session():
    """Validate if current session is still active"""
    if 'session_id' not in session or 'matric_number' not in session:
        return False
    
    matric_number = session['matric_number']
    session_id = session['session_id']
    
    if matric_number not in active_sessions:
        return False
    
    if active_sessions[matric_number]['session_id'] != session_id:
        return False
    
    # Update last activity
    active_sessions[matric_number]['last_activity'] = datetime.now()
    return True

def logout_user(matric_number=None):
    """Remove user session"""
    if matric_number is None:
        matric_number = session.get('matric_number')
    
    if matric_number and matric_number in active_sessions:
        del active_sessions[matric_number]
    
    session.clear()

def require_login(f):
    """Decorator to require valid login"""
    def decorated_function(*args, **kwargs):
        if not validate_session():
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def score_with_ollama(student_answer: str, marking_guide: str, question_text: str = "") -> dict:
    """
    Score student answer using Ollama with fallback options
    """
    # First try Ollama
    if ollama_service.check_connection():
        try:
            result = ollama_service.score_answer(student_answer, marking_guide, question_text)
            logging.info("Scored using Ollama")
            return result
        except Exception as e:
            logging.error(f"Ollama scoring failed: {e}")
    
    # Fallback to traditional model if available
    if model is not None and vectorizer is not None:
        try:
            processed_answer = preprocess_text(student_answer)
            vectorized_answer = vectorizer.transform([processed_answer])
            vectorized_guide = vectorizer.transform([marking_guide])
            
            X_combined = pd.concat([
                pd.DataFrame(vectorized_answer.toarray()), 
                pd.DataFrame(vectorized_guide.toarray())
            ], axis=1)
            score = model.predict(X_combined)[0]
            score = max(0, min(1, score))
            
            # Convert to integer scale (0-5)
            score = int(score * 5)
            
            logging.info("Scored using traditional ML model")
            return {
                "score": score,
                "confidence": 0.7,
                "feedback": "Scored using traditional ML model (converted to 0-5 scale)",
                "strengths": [],
                "weaknesses": []
            }
        except Exception as e:
            logging.error(f"Traditional model scoring failed: {e}")
    
    # Ultimate fallback - simple similarity
    score = fallback_similarity_score(student_answer, marking_guide)
    logging.info("Scored using simple similarity fallback")
    return {
        "score": score,
        "confidence": 0.5,
        "feedback": "Scored using simple text similarity (basic fallback)",
        "strengths": [],
        "weaknesses": []
    }

def parse_excel(file_path):
    df = pd.read_excel(file_path)
    questions = []
    for _, row in df.iterrows():
        question_text = row.get('question_text', '').strip()
        marking_guide = row.get('marking_guide', '').strip()
        if question_text and marking_guide:
            questions.append({'question_text': question_text, 'marking_guide': marking_guide})
    return questions

def parse_word(file_path):
    doc = docx.Document(file_path)
    questions = []
    current_question = {'question_text': '', 'marking_guide': ''}
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text.startswith('Question:'):
            if current_question['question_text']:  # Save the previous question if it exists
                questions.append(current_question)
            current_question = {'question_text': text[len('Question:'):].strip(), 'marking_guide': ''}
        elif text.startswith('Answer:'):
            current_question['marking_guide'] = text[len('Answer:'):].strip()
    if current_question['question_text']:  # Append the last question
        questions.append(current_question)
    return questions

@app.route('/')
def index():
    return render_template('landing_page.html')

@app.route('/api-dashboard')
def api_dashboard():
    """API Service Dashboard"""
    return render_template('api_dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to appropriate page
    if validate_session():
        user_type = session.get('user_type', 'student')
        if user_type == 'admin':
            return redirect(url_for('admin_page'))
        else:
            return redirect(url_for('student'))
    
    if request.method == 'POST':
        name = request.form['name']
        matric_number = request.form['matric_number']
        user_type = request.form.get('user_type', 'student')  # Default to student
        
        # Check if user is already logged in elsewhere
        if is_user_logged_in(matric_number):
            flash(f'User with matric number {matric_number} is already logged in. Please logout from the other session first.', 'error')
            return render_template('login.html')
        
        session_db = SessionLocal()
        try:
            # Only handle students in regular login
            # For admin, check if they already exist
            existing_student = session_db.query(Student).filter_by(matric_number=matric_number).first()
            
            if existing_student:
                # Student exists, log them in
                session_id = create_session(matric_number, existing_student.id, 'student')
                flash(f'Welcome back, {existing_student.name}!', 'success')
                return redirect(url_for('student'))
            else:
                # Create new student
                student = Student(name=name, matric_number=matric_number, score=0)
                session_db.add(student)
                session_db.commit()
                student_id = student.id
                session_id = create_session(matric_number, student_id, 'student')
                flash(f'Welcome, {name}! Your account has been created.', 'success')
                return redirect(url_for('student'))
                    
        except IntegrityError:
            session_db.rollback()
            flash('An error occurred. Please try again.', 'error')
        except Exception as e:
            session_db.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
        finally:
            session_db.close()
    
    return render_template('login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    # If admin is already logged in, redirect to admin page
    if validate_session() and session.get('user_type') == 'admin':
        return redirect(url_for('admin_page'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Simple admin credentials check (you can enhance this later)
        if username == 'admin' and password == 'admin123':
            # Check if admin is already logged in elsewhere
            if is_user_logged_in('ADMIN001'):
                flash('Admin is already logged in elsewhere. Please logout first.', 'error')
                return render_template('admin_login.html')
            
            # Create admin session
            session_id = create_session('ADMIN001', None, 'admin')
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_page'))
        else:
            flash('Invalid admin credentials.', 'error')
            return render_template('admin_login.html')
    
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    matric_number = session.get('matric_number')
    logout_user(matric_number)
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            if filename.endswith('.xlsx'):
                questions = parse_excel(file_path)
            elif filename.endswith('.docx'):
                questions = parse_word(file_path)
            session_db = SessionLocal()
            for q in questions:
                new_question = Question(
                    question_text=q['question_text'],
                    marking_guide=q['marking_guide']
                )
                session_db.add(new_question)
            session_db.commit()
            session_db.close()
            flash('Questions successfully uploaded')
            return redirect(url_for('upload'))
    return render_template('upload.html')

@app.route('/questions', methods=['GET', 'POST'])
def manage_questions():
    session_db = SessionLocal()
    
    if request.method == 'POST':
        if 'file' in request.files:
            # Handle file upload
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                if filename.endswith('.xlsx'):
                    questions = parse_excel(file_path)
                elif filename.endswith('.docx'):
                    questions = parse_word(file_path)
                for q in questions:
                    new_question = Question(
                        question_text=q['question_text'],
                        marking_guide=q['marking_guide']
                    )
                    session_db.add(new_question)
                session_db.commit()
                flash('Questions successfully uploaded')
                return redirect(url_for('manage_questions'))
        else:
            # Handle new question form submission
            question_text = request.form['question_text']
            marking_guide = request.form['marking_guide']
            new_question = Question(
                question_text=question_text,
                marking_guide=marking_guide
            )
            session_db.add(new_question)
            session_db.commit()
            flash('Question successfully added')
            return redirect(url_for('manage_questions'))
    
    questions = session_db.query(Question).all()
    session_db.close()
    return render_template('questions_professional.html', questions=questions)

@app.route('/review_responses', methods=['GET', 'POST'])
def review_responses():
    session_db = SessionLocal()

    if request.method == 'POST':
        # Handle corrections
        response_id = request.form.get('response_id')
        corrected_answer = request.form.get('corrected_answer')
        is_correct = request.form.get('is_correct') == 'on'
        
        response = session_db.query(Response).filter_by(id=response_id).first()
        if response:
            response.corrected_answer = corrected_answer
            response.is_correct = is_correct
            session_db.commit()
            flash('Response successfully updated')
        else:
            flash('Response not found')

    # Redirect to lecturer dashboard which shows all responses
    session_db.close()
    return redirect(url_for('lecturer_page'))


@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    session_db = SessionLocal()
    question = session_db.query(Question).filter_by(id=question_id).first()
    if question:
        session_db.delete(question)
        session_db.commit()
        flash('Question successfully deleted')
    session_db.close()
    return redirect(url_for('manage_questions'))

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    session_db = SessionLocal()
    
    # Find student by ID
    student = session_db.query(Student).filter_by(id=student_id).first()
    
    if student:
        # Delete the student and their responses
        session_db.query(Response).filter_by(student_id=student_id).delete()  # Remove associated responses
        session_db.delete(student)  # Delete the student
        session_db.commit()
        flash(f'Student {student.name} (ID: {student.id}) has been successfully deleted.', 'success')
    else:
        flash(f'Student with ID {student_id} not found.', 'error')
    
    session_db.close()
    return redirect(url_for('lecturer_page'))


@app.route('/edit_score/<int:student_id>', methods=['POST'])
def edit_score(student_id):
    # Extract form data
    lecturer_score = request.form.get('lecturer_score')
    action = request.form.get('action')  # Approve, Reject, or Edit

    session_db = SessionLocal()
    
    # Fetch the student's response based on the student ID
    student_response = session_db.query(Response).filter_by(student_id=student_id).first()

    if student_response:
        if action == 'Approve':
            student_response.lecturer_score = lecturer_score
            flash(f'Score for student {student_id} approved.', 'success')
        elif action == 'Reject':
            student_response.lecturer_score = None  # Reset lecturer score if rejected
            flash(f'Score for student {student_id} rejected.', 'error')
        else:
            flash(f'Invalid action for student {student_id}.', 'error')
        
        session_db.commit()
    else:
        flash(f'No response found for student {student_id}.', 'error')
    
    session_db.close()
    return redirect(url_for('lecturer_page'))

from sqlalchemy.orm import Session

@app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    session_db = SessionLocal()  # Create a new session
    if request.method == 'POST':
        new_text = request.form['question_text']
        new_marking_guide = request.form['marking_guide']
        
        question = session_db.query(Question).filter_by(id=question_id).first()
        if question is None:
            session_db.close()
            return "Question not found", 404
        
        question.question_text = new_text
        question.marking_guide = new_marking_guide
        session_db.commit()
        session_db.close()
        return redirect(url_for('manage_questions'))  # Redirect to manage_questions after update
    
    # If GET request, render the form with current data
    question = session_db.query(Question).filter_by(id=question_id).first()
    if question is None:
        session_db.close()
        return "Question not found", 404

    session_db.close()
    return render_template('edit_question.html', question=question)

@app.route('/student', methods=['GET', 'POST'])
@require_login
def student():
    # Additional check for student role
    if session.get('user_type') != 'student':
        flash('Access denied. Student access required.', 'error')
        return redirect(url_for('login'))
    
    student_id = session.get('student_id')
    if not student_id:
        flash('Invalid session. Please log in again.', 'error')
        return redirect(url_for('login'))

    session_db = SessionLocal()

    if request.method == 'POST':
        question_id = request.form.get('question_id')
        answer = request.form.get('answer')

        if not question_id:
            flash('Question ID is missing')
            return redirect(url_for('student'))

        question = session_db.query(Question).filter_by(id=question_id).first()
        if not question:
            flash('Question not found')
            return redirect(url_for('student'))

        # Use Ollama for scoring
        scoring_result = score_with_ollama(answer, question.marking_guide, question.question_text)
        
        score = scoring_result["score"]
        ai_feedback = scoring_result["feedback"]
        ai_confidence = scoring_result["confidence"]
        ai_strengths = str(scoring_result["strengths"])  # Convert to string for storage
        ai_weaknesses = str(scoring_result["weaknesses"])  # Convert to string for storage

        # Save the response with Ollama feedback
        response = Response(
            student_id=student_id,
            question_id=question_id,
            answer=answer,
            score=score,
            ai_score=score,  # Initially same as score
            ai_feedback=ai_feedback,
            ai_confidence=ai_confidence,
            ai_strengths=ai_strengths,
            ai_weaknesses=ai_weaknesses
        )
        session_db.add(response)
        session_db.commit()

        # Update the student's total score
        student = session_db.query(Student).filter_by(id=student_id).first()
        student.score += score
        session_db.commit()

        # Flash success message with feedback
        flash(f'Answer submitted! Score: {score:.2f}/1.0. {ai_feedback}', 'success')

        # Handling navigation between questions
        questions = session_db.query(Question).all()
        current_index = next((index for (index, d) in enumerate(questions) if d.id == int(question_id)), 0)
        next_index = current_index + 1 if current_index + 1 < len(questions) else None
        prev_index = current_index - 1 if current_index > 0 else None

        next_question_id = questions[next_index].id if next_index is not None else None
        prev_question_id = questions[prev_index].id if prev_index is not None else None

        session_db.close()

        return render_template('student_professional.html', question=question, next_question_id=next_question_id, prev_question_id=prev_question_id)

    # If it's a GET request, fetch the first or requested question
    question_id = request.args.get('question_id')
    if question_id:
        question = session_db.query(Question).filter_by(id=question_id).first()
    else:
        question = session_db.query(Question).first()

    if not question:
        flash('No questions available')
        session_db.close()
        return redirect(url_for('login'))

    # Fetching all questions for navigation
    questions = session_db.query(Question).all()
    current_index = next((index for (index, d) in enumerate(questions) if d.id == question.id), 0)
    next_index = current_index + 1 if current_index + 1 < len(questions) else None
    prev_index = current_index - 1 if current_index > 0 else None

    next_question_id = questions[next_index].id if next_index is not None else None
    prev_question_id = questions[prev_index].id if prev_index is not None else None

    session_db.close()

    return render_template('student_professional.html', question=question, next_question_id=next_question_id, prev_question_id=prev_question_id)


@app.route('/ollama-status')
def ollama_status():
    """Check Ollama service status"""
    is_connected = ollama_service.check_connection()
    available_models = ollama_service.get_available_models() if is_connected else []
    
    return {
        "connected": is_connected,
        "current_model": ollama_service.model,
        "available_models": available_models,
        "service_url": ollama_service.base_url
    }

@app.route('/admin')
def admin_page():
    # No login required for admin access as requested
    session_db = SessionLocal()
    
    # Fetch all student responses and related details with explicit joins
    student_responses = (session_db.query(Student, Response, Question)
                        .join(Response, Student.id == Response.student_id)
                        .join(Question, Response.question_id == Question.id)
                        .all())
    
    # Prepare data to be passed to the template
    data = []
    student_scores = {}

    for student, response, question in student_responses:
        if student.id not in student_scores:
            student_scores[student.id] = {
                'id': student.id,
                'name': student.name,
                'matric_no': student.matric_number,
                'total_ai_score': 0,  # Initialize total AI score for the student
                'responses': []
            }
        
        # Add each response and its details
        student_scores[student.id]['responses'].append({
            'response_id': response.id,  # Add response ID for editing
            'question': question.question_text,
            'student_answer': response.answer,
            'correct_answer': question.marking_guide,
            'ai_score': response.ai_score,
            'lecturer_score': response.lecturer_score,
            'ai_feedback': response.ai_feedback,
            'ai_confidence': response.ai_confidence,
            'ai_strengths': response.ai_strengths,
            'ai_weaknesses': response.ai_weaknesses
        })
        
        # Sum AI scores to get the total AI score for this student
        if response.ai_score is not None:
            student_scores[student.id]['total_ai_score'] += response.ai_score
    
    # Convert the dictionary to a list for easier use in the template
    for student_id, details in student_scores.items():
        for response in details['responses']:
            data.append({
                'id': student_id,
                'response_id': response['response_id'],
                'name': details['name'],
                'matric_no': details['matric_no'],
                'question': response['question'],
                'student_answer': response['student_answer'],
                'correct_answer': response['correct_answer'],
                'ai_score': response['ai_score'],
                'lecturer_score': response['lecturer_score'],
                'ai_feedback': response['ai_feedback'],
                'ai_confidence': response['ai_confidence'],
                'ai_strengths': response['ai_strengths'],
                'ai_weaknesses': response['ai_weaknesses'],
                'total_ai_score': details['total_ai_score']  # Total AI score for the student
            })

    # Get questions and responses for the new professional template
    questions = session_db.query(Question).all()
    responses = session_db.query(Response).join(Question).join(Student).all()
    
    # Format responses for the professional template
    formatted_responses = []
    for response in responses:
        formatted_responses.append({
            'student_name': response.student.name,
            'question': response.question,
            'score': response.score,
            'ai_confidence': response.ai_confidence,
            'answer': response.answer,
            'ai_feedback': response.ai_feedback,
            'ai_strengths': response.ai_strengths,
            'ai_weaknesses': response.ai_weaknesses
        })
    
    session_db.close()
    return render_template('lecturer_professional.html', responses=formatted_responses, questions=questions)



@app.route('/update_lecturer_score/<int:response_id>', methods=['POST'])
def update_lecturer_score(response_id):
    session_db = SessionLocal()
    new_score = request.json['new_score']

    response = session_db.query(Response).get(response_id)
    if response:
        response.score = new_score  # Update the score with the new lecturer score
        session_db.commit()

    session_db.close()
    return '', 204  # No content response



if __name__ == '__main__':
    # Register API routes
    register_api_routes(app)
    
    app.run(host='0.0.0.0', port=5001, debug=True)
