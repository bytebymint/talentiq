"""HR owns outcomes; AI provides source-backed job evidence only."""
import asyncio,json
from types import SimpleNamespace as NS
import pytest
from backend.hr import mark_review_ready,CHAT_SYSTEM
from backend.db import Session,Candidate,Document,Audit
from backend.ai import ollama

@pytest.mark.parametrize('stage',['Hired','Not Selected','On Hold','Under HR Review','Shortlisted','Interview Scheduled','Interview Completed'])
def test_automated_review_preserves_human_outcomes(stage):
    candidate=NS(status=stage);mark_review_ready(candidate);assert candidate.status==stage

def test_automated_reading_requests_review_for_new_candidates():
    candidate=NS(status='Imported');mark_review_ready(candidate);assert candidate.status=='Needs Review'

@pytest.mark.parametrize('outcome',['Hired','Not Selected','On Hold'])
def test_manual_outcomes_require_the_reviewers_action_and_audit_it(client,project,outcome):
    with Session() as db:
        c=Candidate(name='Fictional Ada',project_id=project['id']);db.add(c);db.commit();cid=c.id
    if outcome!='On Hold':
        for body in [{'status':outcome},{'status':outcome,'confirm_decision':True,'note':'   '},{'status':outcome,'note':'Human rationale'}]:
            assert client.patch('/api/candidates/'+cid,json=body).status_code==400
        assert client.get('/api/candidates/'+cid).json()['status']=='Imported'
    result=client.patch('/api/candidates/'+cid,json={'status':outcome,'confirm_decision':outcome!='On Hold','note':'Synthetic reviewer decision after checking source evidence.'})
    assert result.status_code==200 and result.json()['status']==outcome
    assert result.json()['notes'][-1]['author']=='Synthetic HR Reviewer'
    with Session() as db:
        events=db.query(Audit).filter_by(action='Human review updated').all()
        assert events and events[-1].info['changes']['status']==outcome

def test_hiring_question_returns_evidence_without_changing_status(client,project,monkeypatch):
    with Session() as db:
        c=Candidate(name='Fictional Ada',project_id=project['id'],status='On Hold');db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='fictional.pdf',display_name='fictional.pdf',storage_name='fictional.pdf',hash='hash',size=50,pages=[{'page':1,'text':'Fictional Ada\nPython engineer at Example Services, 2021 - 2024. Built Python APIs.'}]));db.commit()
    ollama.gate=asyncio.Lock();ollama.last_generation=None
    async def stream(messages):
        assert 'When HR asks whether to hire' in messages[0]['content']
        assert 'Should we hire this candidate?' in messages[-1]['content']
        yield 'Documented strength: Python API development. Education needs clarification. [S1]'
    async def check(*args):return json.dumps({'answer':'Python API development is documented; education is not established. [S1] Record your own outcome in Human review.'})
    monkeypatch.setattr(ollama,'stream',stream);monkeypatch.setattr(ollama,'chat',check)
    response=client.post('/api/chat',json={'project_id':project['id'],'candidate_id':cid,'query':'Should we hire this candidate?'})
    assert 'Python API development is documented' in response.text
    candidate=client.get('/api/candidates/'+cid).json()
    assert candidate['status']=='On Hold' and not candidate['shortlisted'] and not candidate['notes']
    task=next(t for t in client.get('/api/chat/playbook').json()['tasks'] if t['id']=='hiring')
    assert 'required and preferred' in task['prompt'] and 'do not recommend a hiring outcome' in task['prompt']
