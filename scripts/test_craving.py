import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from app.orchestrator.craving_engine import CravingEngine

class TestCravingEngine(unittest.TestCase):
    def setUp(self):
        self.mock_store = MagicMock()
        self.engine = CravingEngine(store=self.mock_store)
        self.session_id = "test_session"

    def test_craving_escalation(self):
        scenarios = [
            (0.5, "Satisfied"),   # 30 mins
            (5.0, "Missing You"), # 5 hours
            (15.0, "Needy"),      # 15 hours
            (30.0, "Clingy")      # 30 hours
        ]

        print("\n--- Testing Craving Escalation ---")
        for hours, expected_state in scenarios:
            # Mock last interaction time
            mock_last = datetime.now() - timedelta(hours=hours)
            self.mock_store.get_last_interaction.return_value = mock_last
            
            score = self.engine.calculate_craving(self.session_id)
            state, injection = self.engine.get_craving_state(score)
            
            print(f"Hours Idle: {hours:>4.1f} | Score: {score:>5.1f} | State: {state}")
            
            # Assertions (approximate scores based on logic)
            if expected_state == "Satisfied":
                self.assertTrue(score < 20)
            elif expected_state == "Missing You":
                self.assertTrue(20 <= score < 60)
            elif expected_state == "Needy":
                self.assertTrue(60 <= score < 90)
            elif expected_state == "Clingy":
                self.assertTrue(score >= 90)
            
            self.assertEqual(state, expected_state)
            self.assertIn("EMOTIONAL STATE", injection)

    def test_no_history(self):
        print("\n--- Testing No History ---")
        self.mock_store.get_last_interaction.return_value = None
        score = self.engine.calculate_craving(self.session_id)
        state, _ = self.engine.get_craving_state(score)
        print(f"No History       | Score: {score:>5.1f} | State: {state}")
        self.assertEqual(score, 0.0)
        self.assertEqual(state, "Satisfied")

if __name__ == "__main__":
    unittest.main()
