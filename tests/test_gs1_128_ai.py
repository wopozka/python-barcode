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
    gs1_128 = Gs1_128_AI('')
    assert gs1_128.get_val_for_ai_with_fixed_length_decimals(target[0], target[1]) == answer

VISUAL_TO_TUPLE = (
    ('(01)08720299927469(11)240621(17)250621(10)20240621/0001', (('01', '08720299927469',), ('11', '240621',), ('17', '250621',), ('10', '20240621/0001',),)),
)
@pytest.mark.parametrize('target, answer', VISUAL_TO_TUPLE)
def test_get_ai_and_vals_from_brackets(target, answer):
    assert Gs1_128_AI.get_ai_and_vals_from_brackets(target) == answer

CODE_CORRECTNESS = (
    ('(01)08720299927469(11)240621(17)250621(10)20240621/0001', True,),
    ('((01)08720299927469(11)240621(17)250621(10)20240621/0001', False,),
)
@pytest.mark.parametrize('target, answer', CODE_CORRECTNESS)
def test_get_ai_and_vals_from_brackets(target, answer):
    assert Gs1_128_AI.check_if_code_correct(target) == answer

CREATE_CODE = (
    ('(01)08720299927469(11)240621(17)250621(10)20240621/0001', '010872029992746911240621172506211020240621/0001',),
    ('(01)08720299927469(11)240621(17)250621(10)20240621/0001(21)xyz', '010872029992746911240621172506211020240621/0001' + Gs1_128_AI.FC_CHAR + '21xyz',),

)

@pytest.mark.parametrize('target, answer', CREATE_CODE)
def test_create_code(target, answer):
    gs1_128 = Gs1_128_AI(target)
    assert gs1_128.create_code() == gs1_128.FNC1_CHAR + answer