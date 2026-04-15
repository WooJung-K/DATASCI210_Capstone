import datetime, pytest

from fastapi.testclient import TestClient
from testcontainers.redis import RedisContainer

from src import glucose_api

### Fixtures
@pytest.fixture(scope="module")
def redis_container():
    # Uses version 8.6 of redis, because that is what our docker image uses
    with RedisContainer("redis:8.6") as container:
        yield container

@pytest.fixture(scope='module')
def redis_client(redis_container):
    client = Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        db=0,
        decode_responses=True
    )
    yield client

@pytest.fixture(scope='module')
def client(redis_container): 
    # Point the app's lifespan config at the testcontainer BEFORE startup
    glucose_api.REDIS_HOST_URL = redis_container.get_container_host_ip()
    glucose_api.REDIS_HOST_PORT = int(redis_container.get_exposed_port(6379))

    with TestClient(glucose_api.app) as c:
        yield c

### health endpoint
# test get('/health') returns ISO8601 formatted datetime object named 'time'
def test_health_returns_datetime(client):
    r = client.get('/health')
    time = datetime.datetime.fromisoformat(r.json()['time'])
    assert 'time' in r.json().keys()
    assert isinstance(time, datetime.datetime)
