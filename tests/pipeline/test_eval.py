import unittest
from datamate.eval.metrics import summarize
from datamate.eval.scorer import score


class EvaluationTests(unittest.TestCase):
    def test_score_types_and_abstain(self):
        ref={'id':'x','type':'number','answer':0}
        self.assertEqual(score({'id':'x','type':'number','answer':0},ref),'correct')
        self.assertEqual(score({'id':'x','type':'number','answer':1},ref),'wrong')
        self.assertEqual(score({'id':'x','type':'abstain'},ref),'abstain')
        self.assertEqual(score({'id':'x','type':'percent','answer':0},ref),'wrong')

    def test_penalized_metrics(self):
        result=summarize([{'outcome':x} for x in ('correct','wrong','abstain')])
        self.assertEqual(result['score'],0)
        self.assertEqual(result['coverage'],2/3)
        self.assertEqual(result['selective_risk'],0.5)
