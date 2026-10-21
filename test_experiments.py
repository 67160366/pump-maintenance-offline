import unittest
import numpy as np
import pandas as pd
from sklearn.base import clone
from experiments import SensorFeatures, threshold_for_accuracy
import pump

class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.x=pd.DataFrame([[0,0,0,0,0,0],[1,2,3,4,5,6]],columns=pump.FEATURES)
        self.x['Pump_ID']=[1,2]
    def test_features_finite_and_column_order_invariant(self):
        transform=SensorFeatures(engineered=True,pump_id=True).fit(self.x)
        actual=transform.transform(self.x)
        self.assertTrue(np.isfinite(actual).all())
        self.assertEqual(actual.shape,(2,41))
        np.testing.assert_array_equal(actual,transform.transform(self.x[list(reversed(self.x.columns))]))
    def test_target_is_not_feature(self):
        f=SensorFeatures(True,True).fit(self.x)
        changed=self.x.copy()
        changed[pump.TARGET]=[1,0]
        np.testing.assert_array_equal(f.transform(self.x),f.transform(changed))
    def test_unknown_pump_does_not_learn_at_transform(self):
        f=SensorFeatures(pump_id=True).fit(self.x)
        changed=self.x.copy()
        changed['Pump_ID']=999
        self.assertFalse(f.transform(changed)[:,-2:].any())
        self.assertEqual(f.pumps_,[1,2])
        self.assertFalse(hasattr(clone(f),'pumps_'))
    def test_accuracy_threshold_does_not_force_all_positive(self):
        y=np.array([0,0,1,1])
        s=np.array([0.1,0.4,0.6,0.9])
        t=threshold_for_accuracy(y,s)
        np.testing.assert_array_equal(s>=t,y)

if __name__=='__main__':
    unittest.main()
