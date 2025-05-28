# tests/test_database.py
import unittest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('..')  # Add parent directory to path

from database import Base, Donor, Analysis, init_database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Create a temporary database for testing"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.engine = create_engine(f'sqlite:///{self.temp_db.name}')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def tearDown(self):
        """Clean up temporary database"""
        self.session.close()
        os.unlink(self.temp_db.name)
    
    def test_donor_analysis_insertion_and_retrieval(self):
        """Test inserting and retrieving donor and analysis data"""
        # Create dummy donor
        dummy_donor = Donor(
            spendernummer="TEST123",
            name="Test Donor",
            notes="Test notes"
        )
        self.session.add(dummy_donor)
        self.session.commit()
        
        # Create dummy analysis
        dummy_analysis = Analysis(
            spendernummer="TEST123",
            lot_number="LOT-2024-TEST"
        )
        
        # Set JSON data
        liss_data = [{"Sp.Nr.": "TEST123", "LISS": "4+", "C": "+", "c": "0"}]
        status_data = {"status_map": {"C": "Bestätigt (3x +)"}, "system_excluded": []}
        user_selections = ["C", "E", "K"]
        
        dummy_analysis.set_liss_data(liss_data)
        dummy_analysis.set_status_data(status_data)
        dummy_analysis.set_user_selections(user_selections)
        
        self.session.add(dummy_analysis)
        self.session.commit()
        
        # Read back and assert
        retrieved_donor = self.session.query(Donor).filter_by(spendernummer="TEST123").first()
        self.assertIsNotNone(retrieved_donor)
        self.assertEqual(retrieved_donor.name, "Test Donor")
        self.assertEqual(retrieved_donor.notes, "Test notes")
        
        retrieved_analysis = self.session.query(Analysis).filter_by(spendernummer="TEST123").first()
        self.assertIsNotNone(retrieved_analysis)
        self.assertEqual(retrieved_analysis.lot_number, "LOT-2024-TEST")
        
        # Check JSON data
        self.assertEqual(retrieved_analysis.get_liss_data(), liss_data)
        self.assertEqual(retrieved_analysis.get_status_data(), status_data)
        self.assertEqual(retrieved_analysis.get_user_selections(), user_selections)
    
    def test_lot_number_nullable(self):
        """Test that lot_number can be null for legacy rows"""
        donor = Donor(spendernummer="LEGACY001")
        self.session.add(donor)
        
        # Create analysis without lot_number
        analysis = Analysis(spendernummer="LEGACY001")
        self.session.add(analysis)
        self.session.commit()
        
        retrieved = self.session.query(Analysis).filter_by(spendernummer="LEGACY001").first()
        self.assertIsNone(retrieved.lot_number)

if __name__ == '__main__':
    unittest.main()