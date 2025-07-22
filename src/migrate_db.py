"""
Database migration to add Ollama feedback fields
"""
from sqlalchemy import create_engine, text
from database import DATABASE_URL

def migrate_database():
    """Add new columns for Ollama feedback"""
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Add new columns for Ollama feedback
            try:
                conn.execute(text("ALTER TABLE responses ADD COLUMN ai_feedback TEXT"))
                print("Added ai_feedback column")
            except Exception as e:
                print(f"ai_feedback column might already exist: {e}")
            
            try:
                conn.execute(text("ALTER TABLE responses ADD COLUMN ai_confidence REAL"))
                print("Added ai_confidence column")
            except Exception as e:
                print(f"ai_confidence column might already exist: {e}")
            
            try:
                conn.execute(text("ALTER TABLE responses ADD COLUMN ai_strengths TEXT"))
                print("Added ai_strengths column")
            except Exception as e:
                print(f"ai_strengths column might already exist: {e}")
            
            try:
                conn.execute(text("ALTER TABLE responses ADD COLUMN ai_weaknesses TEXT"))
                print("Added ai_weaknesses column")
            except Exception as e:
                print(f"ai_weaknesses column might already exist: {e}")
            
            # Change ai_score to REAL for decimal scores
            try:
                # Create new table with correct schema
                conn.execute(text("""
                    CREATE TABLE responses_new (
                        id INTEGER PRIMARY KEY,
                        student_id INTEGER,
                        question_id INTEGER,
                        answer TEXT NOT NULL,
                        score REAL DEFAULT 0,
                        corrected_answer TEXT,
                        is_correct BOOLEAN DEFAULT 0,
                        ai_score REAL DEFAULT 0,
                        lecturer_score REAL DEFAULT 0,
                        ai_feedback TEXT,
                        ai_confidence REAL,
                        ai_strengths TEXT,
                        ai_weaknesses TEXT,
                        FOREIGN KEY (student_id) REFERENCES students(id),
                        FOREIGN KEY (question_id) REFERENCES questions(id)
                    )
                """))
                
                # Copy data from old table
                conn.execute(text("""
                    INSERT INTO responses_new 
                    (id, student_id, question_id, answer, score, corrected_answer, 
                     is_correct, ai_score, lecturer_score)
                    SELECT id, student_id, question_id, answer, score, corrected_answer,
                           is_correct, ai_score, lecturer_score
                    FROM responses
                """))
                
                # Drop old table and rename new one
                conn.execute(text("DROP TABLE responses"))
                conn.execute(text("ALTER TABLE responses_new RENAME TO responses"))
                
                print("Updated responses table schema")
                
            except Exception as e:
                print(f"Schema update might have failed (table might already be correct): {e}")
            
            conn.commit()
            print("Database migration completed successfully")
            
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_database()
