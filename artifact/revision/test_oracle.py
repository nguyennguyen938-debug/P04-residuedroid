import unittest
from oracle_v2 import classify

def e(kind,t,detail=''):return dict(kind=kind,mono_ns=t,detail=detail)
class OracleTests(unittest.TestCase):
 def test_logged_authorization_is_not_acceptance(self):
  x=classify([e('AUTHORIZATION_LOGGED',1),e('WITHDRAW_REQUEST',2),e('WITHDRAW_ACK',3),e('WRITE_ATTEMPT',4,'request=x;attempt=1;offset=0'),e('BYTES_ACCEPTED',5,'request=x;attempt=1;offset=0;n=9')]);self.assertEqual(x['known_after_ack_bytes'],9)
 def test_missing_return_unknown(self):self.assertTrue(classify([e('WRITE_ATTEMPT',1,'request=x;attempt=1;offset=0')])['measurement_unknown'])
 def test_zero_return_not_handoff(self):self.assertEqual(classify([e('WRITE_ATTEMPT',1),e('BYTES_ACCEPTED',2,'n=0')])['accepted_bytes'],0)
 def test_overlap_unknown(self):self.assertEqual(classify([e('WRITE_ATTEMPT',1),e('WITHDRAW_REQUEST',2),e('BYTES_ACCEPTED',3,'n=4'),e('WITHDRAW_ACK',4)])['ambiguous_returned_bytes'],4)
 def test_unrelated_scope(self):self.assertEqual(classify([e('WITHDRAW_REQUEST',1),e('WITHDRAW_ACK',2),e('WRITE_ATTEMPT',3),e('BYTES_ACCEPTED',4,'n=9')],6)['known_after_ack_bytes'],0)
if __name__=='__main__':unittest.main()
