import pytest
from pydantic import ValidationError

from src.data_models.regression_response import RegressionResponse

def test_accepts_positive_int():
    rr = RegressionResponse(Glucose=1)

    assert isinstance(rr.Glucose, int)
    assert rr.Glucose == 1

def test_accepts_zero():
    rr = RegressionResponse(Glucose=0)

    assert isinstance(rr.Glucose, int)
    assert rr.Glucose == 0

def test_rejects_negatives():
    with pytest.raises(ValidationError):
        RegressionResponse(Glucose=-1)

@pytest.mark.parametrize("value", [
    'abc',
    1.0,
    1.5,
    True,
    ['list'],
    (1,2,3),
    None,
    {1,2,4},
    {'a':1}
])
def test_rejects_non_int_types(value):
    with pytest.raises(ValidationError):
        RegressionResponse(Glucose=value)