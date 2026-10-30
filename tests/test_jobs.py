"""Mock inference is restricted to automated tests. Production always calls Ollama."""
import asyncio
import json
import pytest
from backend.jobs import JobManager
from backend.ai import ollama
from backend.db import Session, Profile, Candidate, Document, Evaluation, Job
from backend.schemas import AnalysisResponse

@pytest.mark.asyncio
async def test_pause_resume_stop_preserve_completed_results(project,monkeypatch):
    manager=JobManager();ollama.gate=asyncio.Lock();entered=asyncio.Event();release=asyncio.Event();calls=[]
    with Session() as db:
        p=db.get(Profile,project['profile_id']);snapshot={**p.config,'profile_id':p.id};ids=[]
        for n in range(3):
            c=Candidate(project_id=project['id'],name=f'Synthetic {n}');db.add(c);db.flush();ids.append(c.id)
            db.add(Document(candidate_id=c.id,filename=f'{n}.pdf',display_name=f'{n}.pdf',hash=str(n),storage_name=f'{n}.pdf',size=100,pages=[{'page':1,'text':f'Synthetic candidate {n}. Built production services using Python.'}],warnings=[]))
        j=Job(project_id=project['id'],profile_snapshot=snapshot,profile_version=1,model='synthetic-test-only',items=[{'candidate_id':id,'name':f'Synthetic {n}','state':'pending'} for n,id in enumerate(ids)]);db.add(j);db.commit();jid=j.id
    async def fake_chat(model,messages,schema):
        payload=json.loads(messages[-1]['content']);calls.append(payload['source']['text'])
        assert all('weight' not in criterion for criterion in payload['rubric']['criteria'])
        if len(calls)==2: entered.set();await release.wait()
        return json.dumps({'f':[],'a':[{'i':'skills','s':'yes','n':90,'x':'Documented Python services.','q':['Built production services using Python.']},{'i':'education','s':'unknown','n':None,'x':'No education evidence is present in the supplied passage.','q':[]}],'r':[],'w':[],'j':[]})
    async def fake_embed(passages):return [[.1,.2,.3] for _ in passages]
    monkeypatch.setattr(ollama,'chat',fake_chat);monkeypatch.setattr(ollama,'embed',fake_embed)
    manager.launch(jid);await asyncio.wait_for(entered.wait(),5)
    await manager.control(jid,'pause');await manager.tasks[jid]
    with Session() as db:
        j=db.get(Job,jid);assert j.state=='paused';assert len(db.query(Evaluation).all())==1;assert j.items[0]['state']=='completed'
    await manager.control(jid,'resume');await manager.tasks[jid]
    with Session() as db:
        j=db.get(Job,jid);assert j.state=='completed';assert db.query(Evaluation).count()==3
        assert all(i['state']=='completed' for i in j.items)
        evaluations=db.query(Evaluation).all();assert all(e.profile_snapshot['profile_id']==project['profile_id'] and e.profile_version==1 for e in evaluations)
    # A completed candidate is never redundantly repeated after resumption.
    assert calls.count(calls[0])==1

@pytest.mark.asyncio
async def test_cancel_before_coroutine_starts(project):
    manager=JobManager();ollama.gate=asyncio.Lock()
    with Session() as db:
        p=db.get(Profile,project['profile_id']);j=Job(project_id=project['id'],profile_snapshot=p.config,profile_version=1,model='test',items=[{'candidate_id':'test','state':'pending'}]);db.add(j);db.commit();jid=j.id
    manager.launch(jid);await manager.control(jid,'stop')
    await asyncio.gather(manager.tasks[jid],return_exceptions=True);await asyncio.sleep(0)
    with Session() as db:assert db.get(Job,jid).state=='stopped'

@pytest.mark.asyncio
async def test_invalid_model_output_retries_twice_and_requires_human_review(project,monkeypatch):
    manager=JobManager();ollama.gate=asyncio.Lock();calls=[]
    with Session() as db:
        profile=db.get(Profile,project['profile_id']);c=Candidate(name='Synthetic invalid-output candidate',project_id=project['id']);db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='synthetic.pdf',display_name='synthetic.pdf',hash='synthetic',storage_name='synthetic.pdf',size=100,pages=[{'page':1,'text':'Built production services using Python.'}],warnings=[]))
        job=Job(project_id=project['id'],profile_snapshot={**profile.config,'profile_id':profile.id},profile_version=1,model='synthetic-invalid-response-only',items=[{'candidate_id':cid,'name':c.name,'state':'pending'}]);db.add(job);db.commit();jid=job.id
    async def invalid_chat(*args):calls.append(1);return '{invalid JSON'
    monkeypatch.setattr(ollama,'chat',invalid_chat)
    manager.launch(jid);await manager.tasks[jid]
    with Session() as db:
        assert len(calls)==2 and db.get(Job,jid).items[0]['state']=='failed'
        assert db.get(Candidate,cid).status=='Needs Review' and db.query(Evaluation).count()==0
