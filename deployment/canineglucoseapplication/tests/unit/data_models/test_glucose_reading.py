import pytest, datetime
from pydantic import ValidationError

from src.data_models.glucose_reading import GlucoseReading

def test_accepts_actual_reading():
    reading = GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44), # explicitly called here so we 'know' its valid. Test parsable strings later.
        RecordType=0,
        Glucose=469
        )

    assert reading.Device == "FreeStyle LibreLink"
    assert reading.SerialNumber == "E9A0CE98-AA19-4E58-8F27-31A26580354B"
    assert reading.DeviceTimestamp == datetime.datetime(2025, 3, 22, 17, 44)
    assert reading.RecordType == 0
    assert reading.Glucose == 469


# Test Device field

def test_rejects_empty_string_in_device_field():
    with pytest.raises(ValidationError):
        GlucoseReading(
            Device="",
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=469
            )

def test_rejects_null_string_in_device_field():
    with pytest.raises(ValidationError):
        GlucoseReading(
            Device=None,
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=469
            )
        
# Test Serial Number Field

def test_rejects_empty_string_in_serial_number_field():
    with pytest.raises(ValidationError):
        GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber="",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=469
        )

def test_rejects_null_string_in_serial_number_field():
    with pytest.raises(ValidationError):
        GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber=None,
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=469
        )

# Test DeviceTimestamp Field

# Should accept ISO format datetime strings
@pytest.mark.parametrize(
    "g",
    [
        "2025-03-22 17:44:00",
        "2025-03-22T17:44:00",
        "2025-03-22T17:44:00Z",
        "2025-03-22T17:44:00-04:00"
    ],
)
def test_accepts_parseable_datetime_strings_in_devicetimestamp_field(g):
    reading = GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=g,
        RecordType=0,
        Glucose=469
        )

    assert isinstance(reading.DeviceTimestamp, datetime.datetime)


# Test Record Type Field
@pytest.mark.parametrize('i', list(range(0,11)))
def test_accepts_non_negative_record_types(i):
    reading = GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
        RecordType=i,
        Glucose=469
        )
    
    assert reading.RecordType == i

@pytest.mark.parametrize('i', list(range(-10,0)))
def test_rejects_negative_record_types(i):
    with pytest.raises(ValidationError):
        reading = GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=i,
            Glucose=469
            )

@pytest.mark.parametrize("value", [
    1.0,
    1.5,
    True,
    ['list'],
    (1,2,3),
    None,
    {1,2,4},
    {'a':1}
])
def test_rejects_non_int_type_in_recordtype_field(value):
    with pytest.raises(ValidationError):
        GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=value,
            Glucose=469
            )

# Test Glucose Field

@pytest.mark.parametrize('i', list(range(0,11))+[500])
def test_accepts_non_negative_glucose_values(i):
    reading = GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
        RecordType=0,
        Glucose=i
        )
    
    assert reading.Glucose == i

@pytest.mark.parametrize('i', list(range(-10,0)))
def test_rejects_negative_glucose_values(i):
    with pytest.raises(ValidationError):
        reading = GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=i
            )
        
@pytest.mark.parametrize('i', list(range(501,511)))
def test_rejects_glucose_values_over_500(i):
    with pytest.raises(ValidationError):
        reading = GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=i
            )
        
@pytest.mark.parametrize("value", [
    ['list'],
    [469],
    (1,2,3),
    None,
    {143},
    {'a':1},
])
def test_rejects_non_int_type_in_glucose_field(value):
    with pytest.raises(ValidationError):
        GlucoseReading(
            Device="FreeStyle LibreLink",
            SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
            DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
            RecordType=0,
            Glucose=value
            )
        
# Check Extra Values Are Ignored
def test_ignores_extra_fields():
    reading = GlucoseReading(
        Device="FreeStyle LibreLink",
        SerialNumber="E9A0CE98-AA19-4E58-8F27-31A26580354B",
        DeviceTimestamp=datetime.datetime(2025, 3, 22, 17, 44),
        RecordType=0,
        Glucose=469,
        ExtraColumn="ignore me",
    )

    dumped = reading.model_dump()
    assert "ExtraColumn" not in dumped