"""Synthetic fixtures only. Test data never touches the normal data/ workspace."""
import os
import tempfile
from pathlib import Path

_temporary = tempfile.TemporaryDirectory(prefix='talentiq-tests-', ignore_cleanup_errors=True)
os.environ['TALENTIQ_DATA_DIR'] = _temporary.name
os.environ['TALENTIQ_AUTO_WARM'] = '0'
os.environ['TALENTIQ_AI_PROVIDER'] = 'local'

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import Base, engine, migrate

def pytest_sessionfinish(session, exitstatus):
    import gc
    gc.collect()
    engine.dispose()
    _temporary.cleanup()

@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine); migrate()
    yield

@pytest.fixture
def client():
    with TestClient(app,headers={'X-TalentIQ-Request':'1'}) as c:
        r=c.post('/api/auth/setup',json={'name':'Synthetic HR Reviewer','username':'testadmin','password':'test-password-12345'})
        assert r.status_code==200
        yield c

@pytest.fixture
def profile_payload():
    return {'depth':'Standard','model':'qwen3:4b-instruct','name':'Synthetic Python Engineer','job_title':'Python Engineer','department':'Engineering','description':'Maintain production Python services.','criteria':[{'id':'skills','name':'Technical skills','weight':60,'enabled':True,'mandatory':True,'instructions':'Documented Python experience.'},{'id':'education','name':'Education','weight':40,'enabled':True,'mandatory':False,'instructions':'Documented computer science degree.'}],'requirements':[{'description':'Documented Python experience','type':'Skill','classification':'Required','expected_value':'Python','verification':'CV and interview','notes':''}]}

@pytest.fixture
def project(client,profile_payload):
    p=client.post('/api/profiles',json=profile_payload).json()
    return client.post('/api/projects',json={'name':'Synthetic engineering test','profile_id':p['id'],'department':'Engineering'}).json()

