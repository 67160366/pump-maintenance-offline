import unittest
import numpy as np
import pandas as pd
from ai4i import AI4IFeatures, INPUTS, SENSORS, MODES, TARGET

class AI4ITests(unittest.TestCase):
    def setUp(self):
        self.df=pd.DataFrame([['L',300.,310.,1500.,40.,100.],['H',301.,312.,1400.,45.,150.]],columns=INPUTS)
    def test_physics_values_and_units(self):
        values=AI4IFeatures(True).fit_transform(self.df)
        self.assertEqual(values.shape,(2,11))
        np.testing.assert_allclose(values[0,-3:],[10.,40*1500*2*np.pi/60,4000.])
    def test_failure_targets_and_identifiers_are_excluded(self):
        changed=self.df.copy()
        for c in [TARGET]+MODES+['UID','UDI','Product ID']:
            changed[c]=[999,888]
        f=AI4IFeatures(True)
        np.testing.assert_array_equal(f.fit_transform(self.df),f.transform(changed))
    def test_column_order_invariant(self):
        f=AI4IFeatures(True)
        np.testing.assert_array_equal(f.transform(self.df),f.transform(self.df[list(reversed(INPUTS))]))
    def test_onehot_types(self):
        values=AI4IFeatures().fit_transform(self.df)
        np.testing.assert_array_equal(values[:,5:],[ [1,0,0], [0,0,1] ])

if __name__=='__main__': unittest.main()
