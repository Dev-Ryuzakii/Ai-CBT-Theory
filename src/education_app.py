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

# Create Flask app for educational system
education_app = Flask(__name__)
education_app.secret_key = 'education_secret_key_2025'  # Different secret key

# Store active sessions to prevent multiple logins
active_sessions = {}

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'docx'}
education_app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    }
    session['matric_number'] = matric_number
    session['student_id'] = student_id
    session['user_type'] = user_type
    session['session_id'] = session_id
    return session_id

def remove_session(matric_number):
    """Remove a user's session"""
    if matric_number in active_sessions:
        del active_sessions[matric_number]
    session.clear()

def check_session_validity():
    """Check if the current session is valid"""
    if 'matric_number' not in session:
        return False
    
    matric_number = session['matric_number']
    session_id = session.get('session_id')
    
    if matric_number not in active_sessions:
        return False
    
    if active_sessions[matric_number]['session_id'] != session_id:
        return False
    
    return True

def extract_text_from_docx(file_path):
    """Extract text from a DOCX file"""
    try:
        doc = docx.Document(file_path)
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return '\n'.join(text)
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {e}")
        return ""

def parse_questions_from_text(text):
    """Parse questions from uploaded text"""
    questions = []
    lines = text.split('\n')
    current_question = {'question_text': '', 'marking_guide': ''}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.lower().startswith('question:') or line.lower().startswith('q:'):
            if current_question['question_text']:  # Save previous question
                questions.append(current_question)
            current_question = {'question_text': '', 'marking_guide': ''}
            current_question['question_text'] = line[line.find(':') + 1:].strip()
        elif line.lower().startswith('answer:') or line.lower().startswith('a:'):
            current_question['marking_guide'] = line[line.find(':') + 1:].strip()
        elif current_question['question_text'] and not current_question['marking_guide']:
            current_question['question_text'] += ' ' + line
        elif current_question['marking_guide']:
            current_question['marking_guide'] += ' ' + line
        else:
            if line.lower().startswith('answer:'):
                current_question['marking_guide'] = text[len('Answer:'):].strip()
    if current_question['question_text']:  # Append the last question
        questions.append(current_question)
    return questions

@education_app.route('/')
def education_home():
    """Education system home page"""
    return render_template('education_home.html')

@education_app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matric_number = request.form.get('matric_number')
        full_name = request.form.get('full_name')
        
        if not matric_number or not full_name:
            flash('Both name and matric number are required', 'error')
            return render_template('login.html')
        
        # Check if user is already logged in
        if is_user_logged_in(matric_number):
            flash('You are already logged in from another session. Please logout from the other session first.', 'warning')
            return render_template('login.html')
        
        # Create session in database
        db = SessionLocal()
        try:
            # Check if student exists, if not create them with the provided name
            student = db.query(Student).filter(Student.matric_number == matric_number).first()
            if not student:
                student = Student(matric_number=matric_number, name=full_name)
                db.add(student)
                db.commit()
                db.refresh(student)
            else:
                # Update name if different
                if student.name != full_name:
                    student.name = full_name
                    db.commit()
            
            # Create session
            create_session(matric_number, student.id)
            
            flash(f'Welcome, {full_name}!', 'success')
            return redirect(url_for('student_page'))
        except Exception as e:
            db.rollback()
            flash(f'Login failed: {str(e)}', 'error')
            return render_template('login.html')
        finally:
            db.close()
    
    return render_template('login.html')

@education_app.route('/logout')
def logout():
    if 'matric_number' in session:
        remove_session(session['matric_number'])
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('education_home'))

@education_app.route('/student')
@education_app.route('/student/<int:question_id>')
def student_page(question_id=None):
    if not check_session_validity():
        flash('Please log in to access the student area.', 'warning')
        return redirect(url_for('login'))
    
    db = SessionLocal()
    try:
        questions = db.query(Question).all()
        student_id = session.get('student_id')
        
        if not questions:
            return render_template('student_professional.html', 
                                 question=None, 
                                 questions=questions, 
                                 responses={})
        
        # If no question_id specified, show the first question
        if question_id is None:
            current_question = questions[0]
        else:
            current_question = db.query(Question).filter(Question.id == question_id).first()
            if not current_question:
                flash('Question not found', 'error')
                return redirect(url_for('student_page'))
        
        # Get student's responses
        responses = db.query(Response).filter(Response.student_id == student_id).all()
        response_dict = {resp.question_id: resp for resp in responses}
        
        # Get student information
        student = db.query(Student).filter(Student.id == student_id).first()
        
        # Find current question index for navigation
        question_ids = [q.id for q in questions]
        current_index = question_ids.index(current_question.id)
        
        # Calculate previous and next question IDs
        prev_question_id = question_ids[current_index - 1] if current_index > 0 else None
        next_question_id = question_ids[current_index + 1] if current_index < len(question_ids) - 1 else None
        
        return render_template('student_professional.html', 
                             question=current_question,
                             questions=questions, 
                             responses=response_dict,
                             prev_question_id=prev_question_id,
                             next_question_id=next_question_id,
                             student=student)
    finally:
        db.close()

@education_app.route('/admin')
def admin_page():
    """Admin page for managing the education system"""
    return render_template('lecturer_professional.html')

@education_app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page (currently just redirects to admin)"""
    if request.method == 'POST':
        # For now, any admin login just goes to admin page
        return redirect(url_for('admin_page'))
    return render_template('admin_login.html')

@education_app.route('/manage_questions')
def manage_questions():
    """Manage questions page"""
    db = SessionLocal()
    try:
        questions = db.query(Question).all()
        return render_template('questions_professional.html', questions=questions)
    finally:
        db.close()

@education_app.route('/upload_questions', methods=['POST'])
def upload_questions():
    """Upload questions from file"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('manage_questions'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('manage_questions'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(education_app.config['UPLOAD_FOLDER'], filename)
        
        # Create upload directory if it doesn't exist
        os.makedirs(education_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file.save(filepath)
        
        # Extract text based on file type
        if filename.endswith('.docx'):
            text_content = extract_text_from_docx(filepath)
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                text_content = f.read()
        
        # Parse questions
        questions = parse_questions_from_text(text_content)
        
        # Save to database
        db = SessionLocal()
        try:
            for q_data in questions:
                if q_data['question_text'] and q_data['marking_guide']:
                    question = Question(
                        question_text=q_data['question_text'],
                        marking_guide=q_data['marking_guide']
                    )
                    db.add(question)
            db.commit()
            flash(f'Successfully uploaded {len(questions)} questions!', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error saving questions: {str(e)}', 'error')
        finally:
            db.close()
        
        # Clean up uploaded file
        os.remove(filepath)
    else:
        flash('Invalid file type. Please upload DOCX or text files.', 'error')
    
    return redirect(url_for('manage_questions'))

@education_app.route('/add_question', methods=['POST'])
def add_question():
    """Add a single question"""
    question_text = request.form.get('question_text')
    marking_guide = request.form.get('marking_guide')
    
    if not question_text or not marking_guide:
        flash('Both question text and marking guide are required.', 'error')
        return redirect(url_for('manage_questions'))
    
    db = SessionLocal()
    try:
        question = Question(
            question_text=question_text,
            marking_guide=marking_guide
        )
        db.add(question)
        db.commit()
        flash('Question added successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error adding question: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(url_for('manage_questions'))

@education_app.route('/submit_answer', methods=['POST'])
def submit_answer():
    """Submit student answer for background AI processing"""
    if not check_session_validity():
        flash('Session invalid. Please log in again.', 'error')
        return redirect(url_for('login'))
    
    try:
        question_id = request.form.get('question_id')
        student_answer = request.form.get('student_answer')
        current_question_id = request.form.get('current_question_id')
        student_id = session.get('student_id')
        
        if not all([question_id, student_answer, student_id]):
            flash('Missing required fields', 'error')
            return redirect(url_for('student_page', question_id=current_question_id))
        
        db = SessionLocal()
        try:
            # Get question
            question = db.query(Question).filter(Question.id == question_id).first()
            if not question:
                flash('Question not found', 'error')
                return redirect(url_for('student_page'))
            
            # Check if existing response exists
            existing_response = db.query(Response).filter(
                Response.student_id == student_id,
                Response.question_id == question_id
            ).first()
            
            if existing_response:
                # Update existing response and reset processing status
                existing_response.answer = student_answer
                existing_response.is_processed = False
                existing_response.admin_approved = False
                existing_response.final_score = None
            else:
                # Create new response - initially not processed
                response = Response(
                    student_id=student_id,
                    question_id=question_id,
                    answer=student_answer,
                    is_processed=False,
                    admin_approved=False
                )
                db.add(response)
            
            db.commit()
            
            # Start background AI processing
            process_answer_in_background(student_id, question_id, student_answer, question.marking_guide, question.question_text)
            
            flash('Answer submitted successfully! AI processing started in background.', 'success')
            
        except Exception as e:
            db.rollback()
            logging.error(f"Error submitting answer: {e}")
            flash('Failed to save answer. Please try again.', 'error')
        finally:
            db.close()
            
        # Redirect back to the current question
        return redirect(url_for('student_page', question_id=current_question_id))
            
    except Exception as e:
        logging.error(f"Error in submit_answer: {e}")
        flash('Internal server error. Please try again.', 'error')
        return redirect(url_for('student_page'))

def process_answer_in_background(student_id, question_id, student_answer, marking_guide, question_text):
    """Process answer with AI in background thread"""
    import threading
    
    def background_task():
        try:
            # Try Ollama scoring
            score, confidence, feedback = ollama_service.score_answer(
                student_answer=student_answer,
                marking_guide=marking_guide,
                question=question_text
            )
            
            # Update response with AI results
            db = SessionLocal()
            try:
                response = db.query(Response).filter(
                    Response.student_id == student_id,
                    Response.question_id == question_id
                ).first()
                
                if response:
                    response.ai_score = score
                    response.ai_confidence = confidence
                    response.ai_feedback = feedback
                    response.score = score  # Set initial score to AI score
                    response.is_processed = True
                    db.commit()
                    logging.info(f"AI processing completed for student {student_id}, question {question_id}")
                    
            except Exception as e:
                db.rollback()
                logging.error(f"Error updating AI results: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logging.error(f"Background AI processing failed: {e}")
            # Mark as processed but with error
            db = SessionLocal()
            try:
                response = db.query(Response).filter(
                    Response.student_id == student_id,
                    Response.question_id == question_id
                ).first()
                
                if response:
                    response.is_processed = True
                    response.ai_feedback = f"AI processing failed: {str(e)}"
                    db.commit()
            except:
                pass
            finally:
                db.close()
    
    # Start background thread
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()

@education_app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    """Delete a question"""
    db = SessionLocal()
    try:
        question = db.query(Question).filter(Question.id == question_id).first()
        if question:
            # Also delete associated responses
            db.query(Response).filter(Response.question_id == question_id).delete()
            db.delete(question)
            db.commit()
            flash('Question deleted successfully!', 'success')
        else:
            flash('Question not found!', 'error')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting question: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(url_for('manage_questions'))

@education_app.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    """Edit a question"""
    db = SessionLocal()
    try:
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            flash('Question not found!', 'error')
            return redirect(url_for('manage_questions'))
        
        if request.method == 'POST':
            question.question_text = request.form.get('question_text')
            question.marking_guide = request.form.get('marking_guide')
            db.commit()
            flash('Question updated successfully!', 'success')
            return redirect(url_for('manage_questions'))
        
        return render_template('edit_question.html', question=question)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('manage_questions'))
    finally:
        db.close()

@education_app.route('/view_responses')
def view_responses():
    """View all student responses for admin review"""
    db = SessionLocal()
    try:
        # Get all responses with student and question information
        responses = db.query(Response).join(Student).join(Question).order_by(
            Response.is_processed.desc(),  # Show processed ones first
            Response.id.desc()  # Then by most recent
        ).all()
        
        # Separate processed and unprocessed responses
        processed_responses = [r for r in responses if r.is_processed]
        unprocessed_responses = [r for r in responses if not r.is_processed]
        
        return render_template('admin_review_responses.html', 
                             processed_responses=processed_responses,
                             unprocessed_responses=unprocessed_responses)
    finally:
        db.close()

@education_app.route('/admin_approve_response', methods=['POST'])
def admin_approve_response():
    """Admin approve or override AI score"""
    response_id = request.form.get('response_id')
    action = request.form.get('action')  # 'approve' or 'override'
    manual_score = request.form.get('manual_score')
    admin_comments = request.form.get('admin_comments', '')
    
    if not response_id or not action:
        flash('Missing required fields', 'error')
        return redirect(url_for('view_responses'))
    
    db = SessionLocal()
    try:
        response = db.query(Response).filter(Response.id == response_id).first()
        if not response:
            flash('Response not found', 'error')
            return redirect(url_for('view_responses'))
        
        if action == 'approve':
            # Approve AI score
            response.admin_approved = True
            response.final_score = response.ai_score
            response.admin_comments = admin_comments
            flash('AI score approved successfully!', 'success')
            
        elif action == 'override':
            # Override with manual score
            if not manual_score:
                flash('Manual score is required for override', 'error')
                return redirect(url_for('view_responses'))
            
            try:
                manual_score = float(manual_score)
                if manual_score < 0 or manual_score > 10:
                    flash('Score must be between 0 and 10', 'error')
                    return redirect(url_for('view_responses'))
                
                response.admin_approved = True
                response.final_score = manual_score
                response.lecturer_score = manual_score
                response.admin_comments = admin_comments
                flash(f'Score overridden to {manual_score}/10', 'success')
                
            except ValueError:
                flash('Invalid score format', 'error')
                return redirect(url_for('view_responses'))
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        flash(f'Error processing request: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(url_for('view_responses'))

if __name__ == '__main__':
    # Run education system on port 5002
    print("🎓 AI-CBT Education System")
    print("📚 Student Portal: http://localhost:5002/")
    print("👨‍💼 Admin Panel: http://localhost:5002/admin")
    print("🔗 Main API Service: http://localhost:5001/")
    education_app.run(debug=True, port=5002)
