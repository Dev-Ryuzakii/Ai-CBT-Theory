from flask import Flask, request, jsonify
from database import SessionLocal, Question, Student, Response
from ollama_service import ollama_service, fallback_similarity_score
from preprocessing import preprocess_text
import joblib
import pandas as pd
import logging
import uuid
from datetime import datetime
from functools import wraps

# API Authentication decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        # Simple API key validation (you can enhance this with database storage)
        valid_api_keys = {
            'dev_key_123': 'Development Key',
            'prod_key_456': 'Production Key',
            'test_key_789': 'Testing Key'
        }
        
        if not api_key or api_key not in valid_api_keys:
            return jsonify({
                'error': 'Invalid or missing API key',
                'message': 'Please provide a valid API key in X-API-Key header or api_key parameter'
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function

def score_with_ollama_api(student_answer: str, marking_guide: str, question_text: str = "") -> dict:
    """
    API version of scoring function with enhanced error handling
    """
    try:
        # First try Ollama
        if ollama_service.check_connection():
            result = ollama_service.score_answer(student_answer, marking_guide, question_text)
            logging.info("API: Scored using Ollama")
            return {
                'success': True,
                'scoring_method': 'ollama',
                'data': result
            }
        
        # Fallback to traditional model if available
        try:
            model = joblib.load('../models/marking_model.pkl')
            vectorizer = joblib.load('../models/vectorizer.pkl')
            
            processed_answer = preprocess_text(student_answer)
            vectorized_answer = vectorizer.transform([processed_answer])
            vectorized_guide = vectorizer.transform([marking_guide])
            
            X_combined = pd.concat([
                pd.DataFrame(vectorized_answer.toarray()), 
                pd.DataFrame(vectorized_guide.toarray())
            ], axis=1)
            score = model.predict(X_combined)[0]
            score = max(0, min(1, score))
            score = int(score * 5)  # Convert to 0-5 scale
            
            logging.info("API: Scored using traditional ML model")
            return {
                'success': True,
                'scoring_method': 'ml_model',
                'data': {
                    "score": score,
                    "confidence": 0.7,
                    "feedback": "Scored using traditional ML model",
                    "strengths": [],
                    "weaknesses": []
                }
            }
        except Exception as e:
            logging.error(f"API: Traditional model scoring failed: {e}")
        
        # Ultimate fallback
        score = fallback_similarity_score(student_answer, marking_guide)
        logging.info("API: Scored using simple similarity fallback")
        return {
            'success': True,
            'scoring_method': 'similarity_fallback',
            'data': {
                "score": score,
                "confidence": 0.5,
                "feedback": "Scored using text similarity fallback",
                "strengths": [],
                "weaknesses": []
            }
        }
        
    except Exception as e:
        logging.error(f"API: Scoring failed completely: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'All scoring methods failed'
        }

def register_api_routes(app):
    """Register all API routes"""
    
    @app.route('/api/v1/health', methods=['GET'])
    def api_health():
        """API Health Check"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'services': {
                'ollama': ollama_service.check_connection(),
                'database': True  # We assume DB is working if we got here
            }
        })
    
    @app.route('/api/v1/score', methods=['POST'])
    @require_api_key
    def api_score_answer():
        """
        Score a student answer against a marking guide
        
        Expected JSON payload:
        {
            "student_answer": "The answer text",
            "marking_guide": "The expected answer or rubric",
            "question_text": "Optional question context"
        }
        """
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            student_answer = data.get('student_answer', '').strip()
            marking_guide = data.get('marking_guide', '').strip()
            question_text = data.get('question_text', '').strip()
            
            if not student_answer or not marking_guide:
                return jsonify({
                    'error': 'Missing required fields',
                    'message': 'Both student_answer and marking_guide are required'
                }), 400
            
            # Score the answer
            result = score_with_ollama_api(student_answer, marking_guide, question_text)
            
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'request_id': str(uuid.uuid4()),
                **result
            })
            
        except Exception as e:
            logging.error(f"API score endpoint error: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/questions', methods=['GET'])
    @require_api_key
    def api_get_questions():
        """Get all available questions"""
        try:
            session_db = SessionLocal()
            questions = session_db.query(Question).all()
            session_db.close()
            
            questions_data = []
            for q in questions:
                questions_data.append({
                    'id': q.id,
                    'question_text': q.question_text,
                    'marking_guide': q.marking_guide,
                    'created_at': q.created_at.isoformat() if hasattr(q, 'created_at') else None
                })
            
            return jsonify({
                'questions': questions_data,
                'total_count': len(questions_data),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logging.error(f"API get questions error: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/questions', methods=['POST'])
    @require_api_key
    def api_create_question():
        """Create a new question"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            question_text = data.get('question_text', '').strip()
            marking_guide = data.get('marking_guide', '').strip()
            
            if not question_text or not marking_guide:
                return jsonify({
                    'error': 'Missing required fields',
                    'message': 'Both question_text and marking_guide are required'
                }), 400
            
            session_db = SessionLocal()
            new_question = Question(
                question_text=question_text,
                marking_guide=marking_guide
            )
            session_db.add(new_question)
            session_db.commit()
            
            question_id = new_question.id
            session_db.close()
            
            return jsonify({
                'success': True,
                'message': 'Question created successfully',
                'question_id': question_id,
                'timestamp': datetime.now().isoformat()
            }), 201
            
        except Exception as e:
            logging.error(f"API create question error: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/students', methods=['POST'])
    @require_api_key
    def api_create_student():
        """Create or get a student"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            name = data.get('name', '').strip()
            matric_number = data.get('matric_number', '').strip()
            
            if not name or not matric_number:
                return jsonify({
                    'error': 'Missing required fields',
                    'message': 'Both name and matric_number are required'
                }), 400
            
            session_db = SessionLocal()
            
            # Check if student already exists
            existing_student = session_db.query(Student).filter_by(matric_number=matric_number).first()
            
            if existing_student:
                session_db.close()
                return jsonify({
                    'success': True,
                    'message': 'Student already exists',
                    'student_id': existing_student.id,
                    'student': {
                        'id': existing_student.id,
                        'name': existing_student.name,
                        'matric_number': existing_student.matric_number,
                        'score': existing_student.score
                    },
                    'timestamp': datetime.now().isoformat()
                })
            
            # Create new student
            student = Student(name=name, matric_number=matric_number, score=0)
            session_db.add(student)
            session_db.commit()
            student_id = student.id
            session_db.close()
            
            return jsonify({
                'success': True,
                'message': 'Student created successfully',
                'student_id': student_id,
                'student': {
                    'id': student_id,
                    'name': name,
                    'matric_number': matric_number,
                    'score': 0
                },
                'timestamp': datetime.now().isoformat()
            }), 201
            
        except Exception as e:
            logging.error(f"API create student error: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/submit-response', methods=['POST'])
    @require_api_key
    def api_submit_response():
        """Submit and score a student response"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            student_id = data.get('student_id')
            question_id = data.get('question_id')
            answer = data.get('answer', '').strip()
            
            if not all([student_id, question_id, answer]):
                return jsonify({
                    'error': 'Missing required fields',
                    'message': 'student_id, question_id, and answer are required'
                }), 400
            
            session_db = SessionLocal()
            
            # Verify student and question exist
            student = session_db.query(Student).filter_by(id=student_id).first()
            question = session_db.query(Question).filter_by(id=question_id).first()
            
            if not student:
                session_db.close()
                return jsonify({'error': 'Student not found'}), 404
            
            if not question:
                session_db.close()
                return jsonify({'error': 'Question not found'}), 404
            
            # Score the response
            scoring_result = score_with_ollama_api(answer, question.marking_guide, question.question_text)
            
            if not scoring_result['success']:
                session_db.close()
                return jsonify({
                    'error': 'Scoring failed',
                    'message': scoring_result.get('message', 'Unknown scoring error')
                }), 500
            
            score_data = scoring_result['data']
            score = score_data["score"]
            ai_feedback = score_data["feedback"]
            ai_confidence = score_data["confidence"]
            ai_strengths = str(score_data["strengths"])
            ai_weaknesses = str(score_data["weaknesses"])
            
            # Save the response
            response = Response(
                student_id=student_id,
                question_id=question_id,
                answer=answer,
                score=score,
                ai_score=score,
                ai_feedback=ai_feedback,
                ai_confidence=ai_confidence,
                ai_strengths=ai_strengths,
                ai_weaknesses=ai_weaknesses
            )
            session_db.add(response)
            session_db.commit()
            
            # Update student's total score
            student.score += score
            session_db.commit()
            
            response_id = response.id
            session_db.close()
            
            return jsonify({
                'success': True,
                'message': 'Response submitted and scored successfully',
                'response_id': response_id,
                'scoring': {
                    'score': score,
                    'max_score': 5,
                    'feedback': ai_feedback,
                    'confidence': ai_confidence,
                    'strengths': ai_strengths,
                    'weaknesses': ai_weaknesses,
                    'method': scoring_result['scoring_method']
                },
                'student_total_score': student.score,
                'timestamp': datetime.now().isoformat()
            }), 201
            
        except Exception as e:
            logging.error(f"API submit response error: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/student/<int:student_id>/responses', methods=['GET'])
    @require_api_key
    def api_get_student_responses(student_id):
        """Get all responses for a specific student"""
        try:
            session_db = SessionLocal()
            
            student = session_db.query(Student).filter_by(id=student_id).first()
            if not student:
                session_db.close()
                return jsonify({'error': 'Student not found'}), 404
            
            responses = (session_db.query(Response, Question)
                        .join(Question, Response.question_id == Question.id)
                        .filter(Response.student_id == student_id)
                        .all())
            
            response_data = []
            for response, question in responses:
                response_data.append({
                    'response_id': response.id,
                    'question': {
                        'id': question.id,
                        'text': question.question_text,
                        'marking_guide': question.marking_guide
                    },
                    'answer': response.answer,
                    'score': response.score,
                    'ai_score': response.ai_score,
                    'ai_feedback': response.ai_feedback,
                    'ai_confidence': response.ai_confidence,
                    'ai_strengths': response.ai_strengths,
                    'ai_weaknesses': response.ai_weaknesses,
                    'submitted_at': response.created_at.isoformat() if hasattr(response, 'created_at') else None
                })
            
            session_db.close()
            
            return jsonify({
                'student': {
                    'id': student.id,
                    'name': student.name,
                    'matric_number': student.matric_number,
                    'total_score': student.score
                },
                'responses': response_data,
                'total_responses': len(response_data),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logging.error(f"API get student responses error: {e}")
            return jsonify({
                'error': 'Internal server error',
                'message': str(e)
            }), 500
    
    @app.route('/api/v1/docs', methods=['GET'])
    def api_documentation():
        """API Documentation"""
        docs = {
            'title': 'AI-CBT Assessment API',
            'version': '1.0.0',
            'description': 'AI-powered Computer-Based Testing API for educational assessment systems',
            'base_url': request.host_url + 'api/v1',
            'authentication': {
                'type': 'API Key',
                'methods': [
                    'Header: X-API-Key: your_api_key',
                    'Query Parameter: ?api_key=your_api_key'
                ],
                'test_keys': {
                    'development': 'dev_key_123',
                    'testing': 'test_key_789'
                }
            },
            'endpoints': {
                'GET /health': {
                    'description': 'Check API health status',
                    'auth_required': False,
                    'response': 'Health status and service availability'
                },
                'POST /score': {
                    'description': 'Score a student answer against marking guide',
                    'auth_required': True,
                    'payload': {
                        'student_answer': 'string (required)',
                        'marking_guide': 'string (required)',
                        'question_text': 'string (optional)'
                    },
                    'response': 'Scoring result with feedback'
                },
                'GET /questions': {
                    'description': 'Get all available questions',
                    'auth_required': True,
                    'response': 'List of questions'
                },
                'POST /questions': {
                    'description': 'Create a new question',
                    'auth_required': True,
                    'payload': {
                        'question_text': 'string (required)',
                        'marking_guide': 'string (required)'
                    }
                },
                'POST /students': {
                    'description': 'Create or get a student',
                    'auth_required': True,
                    'payload': {
                        'name': 'string (required)',
                        'matric_number': 'string (required)'
                    }
                },
                'POST /submit-response': {
                    'description': 'Submit and score a student response',
                    'auth_required': True,
                    'payload': {
                        'student_id': 'integer (required)',
                        'question_id': 'integer (required)',
                        'answer': 'string (required)'
                    }
                },
                'GET /student/{id}/responses': {
                    'description': 'Get all responses for a student',
                    'auth_required': True,
                    'response': 'Student info and their responses'
                }
            },
            'examples': {
                'score_answer': {
                    'url': '/api/v1/score',
                    'method': 'POST',
                    'headers': {'X-API-Key': 'dev_key_123'},
                    'body': {
                        'student_answer': 'Photosynthesis is the process by which plants make food using sunlight.',
                        'marking_guide': 'Photosynthesis is the process where plants convert light energy into chemical energy using chlorophyll.',
                        'question_text': 'Explain the process of photosynthesis.'
                    }
                }
            }
        }
        
        return jsonify(docs)
