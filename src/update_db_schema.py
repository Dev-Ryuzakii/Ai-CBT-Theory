from sqlalchemy import create_engine, Column, Integer, Text, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer)
    question_id = Column(Integer)
    answer = Column(Text, nullable=False)
    score = Column(Integer, default=0)
    corrected_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, default=False)
    ai_score = Column(Integer, default=0)  # Existing column
    lecturer_score = Column(Integer, default=0)  # Added column

DATABASE_URL = 'sqlite:///data/database.db'
engine = create_engine(DATABASE_URL)

# Drop the existing table and create the new one
Base.metadata.drop_all(bind=engine, tables=[Response.__table__])
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print("Database schema updated.")
