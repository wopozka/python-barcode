import pytest
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__), '../barcode'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from codex import Gs1_128_AI

TEST_VAL_AI_FIXED_L = (
    (('310', '123456',),  ('3100', '123456',)),
)

@pytest.mark.parametrize('target, answer', TEST_VAL_AI_FIXED_L)
def test_get_val_for_ai_with_fixed_length_decimals(target, answer):
    gs1_128 = Gs1_128_AI('')
    assert gs1_128.get_val_for_ai_with_fixed_length_decimals(target[0], target[1]) == answer
