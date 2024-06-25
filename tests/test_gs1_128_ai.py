import pytest
import sys
import os.path
# sys.path.append(os.path.join(os.path.dirname(__file__), '../barcode'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from barcode.codex import Gs1_128_AI

TEST_VAL_AI_FIXED_L = (
    (('310', '123456',),  ('3100', '123456',)),
    (('310', '23456',),  ('3100', '023456',)),
    (('310', '6',),  ('3100', '000006',)),
    (('310', '6a',),  ('3100', '6a',)),
    (('310', '6.12345',),  ('3105', '612345',)),
    (('310', '6.1234',), ('3105', '612340',)),
    (('310', '6123456.7',), ('3100', '612345',)),
    (('310', '6.1234567',), ('3105', '612345',)),

)

@pytest.mark.parametrize('target, answer', TEST_VAL_AI_FIXED_L)
def test_get_val_for_ai_with_fixed_length_decimals(target, answer):
    gs1_128 = Gs1_128_AI('', code_with_ais='')
    assert gs1_128.get_val_for_ai_with_fixed_length_decimals(target[0], target[1]) == answer
