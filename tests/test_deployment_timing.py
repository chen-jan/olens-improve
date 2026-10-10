"""No-model timing protocol and observation restoration checks."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('timing_driver',Path(__file__).parents[1]/'scripts/deployment_timing.py')
driver = importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)


class TimingTests(unittest.TestCase):
    def test_frozen_profiles_and_explicit_controls(self):
        body={'status':'root_reviewed_timing_profiles','freeze_sha256':'a'*64,
              'profiles':[{'id':'chosen','method':'specificity_mean_prune','n':32,'maximum_loss':.005}]}
        with self.assertRaisesRegex(ValueError,'controls|control'):
            driver.checked_profiles(body,False)
        self.assertEqual(driver.checked_profiles(body,True),body['profiles'])
        for patch in ({'n':64},{'method':'capped_n1','n':32},{'maximum_loss':float('nan')},{'id':'../escape'}):
            bad=body|{'profiles':[body['profiles'][0]|patch]}
            with self.assertRaises(ValueError):driver.checked_profiles(bad,True)

    def test_observation_preserves_classmethod_arguments_and_restores(self):
        class Fake:
            @classmethod
            def load(cls,value):return cls.__name__,value
            def encode(self,value):return value+1
        seen=[]
        restore=driver.observe_method(Fake,'load',lambda original:lambda cls,*a,**kw:(seen.append(a),original(*a,**kw))[1])
        self.assertEqual(Fake.load(7),('Fake',7));self.assertEqual(seen,[(7,)])
        restore();self.assertEqual(Fake.load(8),('Fake',8));self.assertEqual(seen,[(7,)])
        restore=driver.observe_method(Fake,'encode',lambda original:lambda self,*a,**kw:original(self,*a,**kw))
        self.assertEqual(Fake().encode(2),3);restore();self.assertEqual(Fake().encode(2),3)


if __name__=='__main__':unittest.main()
