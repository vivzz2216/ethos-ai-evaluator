import sys
sys.path.insert(0, 'backend')

from ethos_testing.api import router
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Initialize router and app
app = FastAPI()
app.include_router(router)

client = TestClient(app)

# Test automated endpoint
response = client.post('/ethos/test/automated', json={
    'code': 'def test(): return "hello"',
    'response_count': 2
})

print('Automated test response status:', response.status_code)
print('Response:', response.json())
