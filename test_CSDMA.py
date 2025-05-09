# test_csdma.py

import unittest
from CSDMA import CSDMA

class TestCSDMA(unittest.TestCase):
    def setUp(self):
        # Using dummy knowledge graphs for testing
        self.csdma = CSDMA(None, None)

    def test_violate_conservation(self):
        thought = "agent tries to violate conservation of energy"
        expected = {
            'common_sense_plausibility_score': 9,
            'flags': ['Physical_Implausibility']
        }
        result = self.csdma.evaluate_thought(thought)
        self.assertEqual(result, expected)

    def test_lift_building_instantly(self):
        thought = "human tries to lift building instantly"
        expected = {
            'common_sense_plausibility_score': 9,
            'flags': ['Resource_Improbable']
        }
        result = self.csdma.evaluate_thought(thought)
        self.assertEqual(result, expected)

    def test_common_solution(self):
        thought = "agent proposes a common solution"
        expected = {
            'common_sense_plausibility_score': 10,
            'flags': []
        }
        result = self.csdma.evaluate_thought(thought)
        self.assertEqual(result, expected)

    def test_never_done_before(self):
        thought = "agent attempts something never done before"
        expected = {
            'common_sense_plausibility_score': 9,
            'flags': ['Atypical_Approach']
        }
        result = self.csdma.evaluate_thought(thought)
        self.assertEqual(result, expected)

    def test_ignores_feedback_loop(self):
        thought = "agent ignores feedback loop"
        expected = {
            'common_sense_plausibility_score': 10,
            'flags': []
        }
        result = self.csdma.evaluate_thought(thought)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
