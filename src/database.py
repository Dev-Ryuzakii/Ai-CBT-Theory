from flask import Flask, render_template, request, redirect, url_for, session
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.secret_key = 'your_secret_key'

Base = declarative_base()

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    marking_guide = Column(Text, nullable=False)

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    matric_number = Column(String, unique=True, nullable=False)
    score = Column(Integer, default=0)
    responses = relationship("Response", back_populates="student")

class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    question_id = Column(Integer, ForeignKey('questions.id'))
    answer = Column(Text, nullable=False)
    score = Column(Integer, default=0)
    corrected_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, default=False)
    ai_score = Column(Integer, default=0)  # Add this line
    lecturer_score = Column(Integer, default=0)  # Added column
    
    student = relationship("Student", back_populates="responses")
    question = relationship("Question")

    
DATABASE_URL = 'sqlite:///data/database.db'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    if not db.query(Question).first():
        sample_question = Question(question_text="What is a computer?", marking_guide="A computer is an electronic device...")
        db.add(sample_question)
        db.commit()
    db.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        matric_number = request.form['matric_number']
        session_db = SessionLocal()

        # Check if the student already exists
        student = session_db.query(Student).filter_by(matric_number=matric_number).first()
        if student is None:
            # If the student doesn't exist, create a new record
            student = Student(name=name, matric_number=matric_number, score=0)
            session_db.add(student)
            try:
                session_db.commit()
            except IntegrityError:
                session_db.rollback()
                return "An error occurred while adding the student. Please try again."
        else:
            # If the student exists, you can log them in or handle accordingly
            session['student_id'] = student.id
            session_db.close()
            return redirect(url_for('student', student_id=student.id))

        session['student_id'] = student.id  # Store the student ID in session
        session_db.close()
        return redirect(url_for('student', student_id=student.id))
    return render_template('login.html')

@app.route('/student/<int:student_id>')
def student(student_id):
    session_db = SessionLocal()

    # Fetch student details
    student = session_db.query(Student).get(student_id)
    if student is None:
        return "Student not found", 404

    # Handle student's response logic here
    # Example: Save a response
    # Assume some question_id and answer are received from the request
    question_id = 1  # Replace with actual question ID
    answer = "Some answer"  # Replace with actual answer from form
    
    response = Response(
        student_id=student_id,
        question_id=question_id,
        answer=answer,
        score=0  # Initially set to 0, update after grading
    )
    session_db.add(response)
    session_db.commit()

    session_db.close()
    return f"Welcome, {student.name}. Your response has been recorded."

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
