# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import json
from datetime import datetime

Base = declarative_base()

class Donor(Base):
    __tablename__ = 'donors'
    
    spendernummer = Column(String, primary_key=True)
    name = Column(String)
    notes = Column(Text)
    
    # Relationship
    analyses = relationship("Analysis", back_populates="donor")

class Analysis(Base):
    __tablename__ = 'analyses'
    
    id = Column(Integer, primary_key=True)
    spendernummer = Column(String, ForeignKey('donors.spendernummer'))
    timestamp = Column(DateTime, default=func.now())
    lot_number = Column(String)
    liss_json = Column(Text)  # Raw table after Step 1
    status_json = Column(Text)  # status_map + exclusion info
    user_sel_json = Column(Text)  # user selections
    report_pdf = Column(LargeBinary)  # PDF report
    
    # Relationship
    donor = relationship("Donor", back_populates="analyses")
    
    def get_liss_data(self):
        return json.loads(self.liss_json) if self.liss_json else None
    
    def set_liss_data(self, data):
        self.liss_json = json.dumps(data)
    
    def get_status_data(self):
        return json.loads(self.status_json) if self.status_json else None
    
    def set_status_data(self, data):
        self.status_json = json.dumps(data)
    
    def get_user_selections(self):
        return json.loads(self.user_sel_json) if self.user_sel_json else None
    
    def set_user_selections(self, data):
        self.user_sel_json = json.dumps(data)

# Database connection
DATABASE_URL = "sqlite:///antigen_analysis.db"  # Can be changed to PostgreSQL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()