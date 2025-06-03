# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Donor(Base):
    __tablename__ = 'donors'
    
    spendernummer = Column(String, primary_key=True)
    name = Column(String)
    notes = Column(Text)
    
    # Relationship
    analyses = relationship("Analysis", back_populates="donor")
    
    def __repr__(self):
        return f"<Donor(spendernummer='{self.spendernummer}', name='{self.name}')>"

class Analysis(Base):
    __tablename__ = 'analyses'
    
    id = Column(Integer, primary_key=True)
    spendernummer = Column(String, ForeignKey('donors.spendernummer'))
    timestamp = Column(DateTime, default=func.now())
    lot_number = Column(Text, nullable=True)  # Explicitly nullable for legacy rows
    liss_json = Column(Text)  # Raw table after Step 1
    status_json = Column(Text)  # status_map + exclusion info
    user_sel_json = Column(Text)  # user selections
    report_pdf = Column(LargeBinary)  # PDF report
    
    # Relationship
    donor = relationship("Donor", back_populates="analyses")
    
    def get_liss_data(self):
        """Safely retrieve LISS data from JSON field"""
        try:
            return json.loads(self.liss_json) if self.liss_json else None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error decoding LISS data for analysis {self.id}: {e}")
            return None
    
    def set_liss_data(self, data):
        """Safely store LISS data to JSON field"""
        try:
            self.liss_json = json.dumps(data) if data is not None else None
        except (TypeError, ValueError) as e:
            logger.error(f"Error encoding LISS data for analysis {self.id}: {e}")
            self.liss_json = None
    
    def get_status_data(self):
        """Safely retrieve status data from JSON field"""
        try:
            return json.loads(self.status_json) if self.status_json else None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error decoding status data for analysis {self.id}: {e}")
            return None
    
    def set_status_data(self, data):
        """Safely store status data to JSON field"""
        try:
            self.status_json = json.dumps(data) if data is not None else None
        except (TypeError, ValueError) as e:
            logger.error(f"Error encoding status data for analysis {self.id}: {e}")
            self.status_json = None
    
    def get_user_selections(self):
        """Safely retrieve user selections from JSON field"""
        try:
            return json.loads(self.user_sel_json) if self.user_sel_json else None
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error decoding user selections for analysis {self.id}: {e}")
            return None
    
    def set_user_selections(self, data):
        """Safely store user selections to JSON field"""
        try:
            self.user_sel_json = json.dumps(data) if data is not None else None
        except (TypeError, ValueError) as e:
            logger.error(f"Error encoding user selections for analysis {self.id}: {e}")
            self.user_sel_json = None
    
    def __repr__(self):
        return f"<Analysis(id={self.id}, spendernummer='{self.spendernummer}', timestamp='{self.timestamp}')>"

# Database connection
DATABASE_URL = "sqlite:///antigen_analysis.db"  # Can be changed to PostgreSQL
engine = create_engine(DATABASE_URL, echo=False)  # Set echo=True for SQL debugging
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def safe_create_all():
    """Safely create database tables without losing existing data"""
    try:
        # Check if tables already exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            logger.info(f"Found existing tables: {existing_tables}")
            # Tables exist, perform safe migration
            Base.metadata.create_all(bind=engine, checkfirst=True)
            logger.info("Database migration completed safely")
        else:
            # Fresh database, create all tables
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        raise

def init_database():
    """Initialize database tables safely without data loss"""
    logger.info("Initializing database...")
    safe_create_all()

def get_db():
    """Get database session with proper cleanup"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def check_database_health():
    """Check if database is accessible and healthy"""
    try:
        db = SessionLocal()
        # Simple query to check connectivity
        donor_count = db.query(Donor).count()
        analysis_count = db.query(Analysis).count()
        db.close()
        
        logger.info(f"Database health check: {donor_count} donors, {analysis_count} analyses")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

def migrate_legacy_data():
    """Migrate any legacy data if needed"""
    try:
        db = SessionLocal()
        
        # Check for analyses without lot_number (legacy data)
        legacy_analyses = db.query(Analysis).filter(Analysis.lot_number.is_(None)).all()
        
        if legacy_analyses:
            logger.info(f"Found {len(legacy_analyses)} legacy analyses without lot numbers")
            # We could set default lot numbers here if needed
            # For now, just log the count
        
        db.close()
        
    except Exception as e:
        logger.error(f"Error during legacy data migration: {e}")

# Initialize on import
init_database()

# Run health check
if not check_database_health():
    logger.warning("Database health check failed during initialization")

# Check for legacy data migration
migrate_legacy_data()