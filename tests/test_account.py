"""Self-service account changes using disposable test accounts only."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app,password_valid
from backend.db import Session,User,Login,Audit,Setting

OLD='test-password-12345'
NEW='synthetic-new-password-56789'

def payload(**changes):return {'username':'updated-reviewer','current_password':OLD,'new_password':NEW,'confirm_new_password':NEW,**changes}

def test_change_both_credentials_rotates_session_and_keeps_current_login(client):
    previous=client.cookies.get('talentiq_session')
    with TestClient(app,headers={'X-TalentIQ-Request':'1'}) as other:
        assert other.post('/api/auth/login',json={'username':'testadmin','password':OLD}).status_code==200
        result=client.patch('/api/auth/account',json=payload())
        assert result.status_code==200,result.text
        assert result.json()['username']=='updated-reviewer' and 'password' not in result.json()
        assert client.cookies.get('talentiq_session')!=previous
        assert 'HttpOnly' in result.headers['set-cookie'] and 'SameSite=strict' in result.headers['set-cookie']
        assert client.get('/api/auth/me').status_code==200
        assert other.get('/api/auth/me').status_code==401
    with Session() as db:
        user=db.query(User).one();assert password_valid(NEW,user.password) and not password_valid(OLD,user.password)
        assert db.query(Login).filter_by(user_id=user.id).count()==1
        event=db.query(Audit).filter_by(action='Account sign-in updated').one()
        assert event.info=={'username_changed':True,'password_changed':True}
        assert OLD not in json.dumps(event.info) and NEW not in json.dumps(event.info)
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'username':'testadmin','password':OLD}).status_code==401
    assert client.post('/api/auth/login',json={'username':'updated-reviewer','password':NEW}).status_code==200

def test_username_only_keeps_password_and_workspace_settings(client):
    with Session() as db:db.add(Setting(id='sentinel',value={'unchanged':True}));db.commit()
    response=client.patch('/api/auth/account',json={'username':'  Renamed-Reviewer  ','current_password':OLD})
    assert response.status_code==200 and response.json()['username']=='renamed-reviewer'
    with Session() as db:
        assert password_valid(OLD,db.query(User).one().password)
        assert db.get(Setting,'sentinel').value=={'unchanged':True}

def test_password_only_keeps_username(client):
    response=client.patch('/api/auth/account',json=payload(username='testadmin'))
    assert response.status_code==200 and response.json()['username']=='testadmin'

@pytest.mark.parametrize('body,status',[
    (payload(current_password='wrong-synthetic-password'),400),
    (payload(confirm_new_password='not-the-same-password'),400),
    (payload(new_password='short',confirm_new_password='short'),422),
    (payload(username='bad username'),400),
    (payload(role='admin'),422),
    ({'username':'testadmin','current_password':OLD},400),
])
def test_invalid_changes_are_atomic_and_do_not_echo_passwords(client,body,status):
    with Session() as db:before=[(u.id,u.username,u.password,u.role) for u in db.query(User)]
    result=client.patch('/api/auth/account',json=body)
    assert result.status_code==status,result.text
    assert OLD not in result.text and NEW not in result.text and str(body.get('current_password','')) not in result.text
    with Session() as db:assert [(u.id,u.username,u.password,u.role) for u in db.query(User)]==before
    assert client.get('/api/auth/me').status_code==200

def test_username_collision_keeps_both_accounts(client):
    assert client.post('/api/users',json={'name':'Other reviewer','username':'other-reviewer','password':NEW,'role':'reviewer'}).status_code==200
    result=client.patch('/api/auth/account',json=payload(username='OTHER-REVIEWER'))
    assert result.status_code==409
    assert client.get('/api/auth/me').json()['username']=='testadmin'

def test_viewers_can_change_only_their_own_sign_in(client):
    client.post('/api/users',json={'name':'Viewer','username':'viewer-test','password':NEW,'role':'viewer'})
    client.post('/api/auth/logout');client.post('/api/auth/login',json={'username':'viewer-test','password':NEW})
    result=client.patch('/api/auth/account',json={'username':'renamed-viewer','current_password':NEW})
    assert result.status_code==200 and result.json()['role']=='viewer'
    assert client.get('/api/users').status_code==403
    with Session() as db:assert db.query(User).filter_by(username='testadmin').one().role=='admin'

def test_current_password_verification_is_rate_limited(client):
    for _ in range(8):assert client.patch('/api/auth/account',json=payload(current_password='wrong')).status_code==400
    assert client.patch('/api/auth/account',json=payload()).status_code==429

def test_account_changes_require_authentication(client):
    client.post('/api/auth/logout')
    assert client.patch('/api/auth/account',json=payload()).status_code==401
