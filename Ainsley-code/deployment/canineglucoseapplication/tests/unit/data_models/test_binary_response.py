import pytest
from pydantic import ValidationError

from src.data_models.binary_response import BinaryResponse

# Check response accepts string parameters of length 1 or longer
def test_accepts_nonempty_strings():
    br = BinaryResponse(Label='s') # s for safe

    assert isinstance(br.Label, str)
    assert len(br.Label) > 0

def test_rejects_empty_strings():
    with pytest.raises(ValidationError):
        BinaryResponse(Label='')

@pytest.mark.parametrize("value", [
    1,
    1.0,
    True,
    ['list'],
    (1,2,3),
    None,
    {1,2,4},
    {'a':1}
])
def test_rejects_non_string_types(value):
    with pytest.raises(ValidationError):
        BinaryResponse(Label=value)