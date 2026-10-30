"""Synthetic source fixtures; model transport is stubbed only in unit tests."""
import asyncio
import json
from types import SimpleNamespace
import pytest
from backend.fast import prepare,decode,fingerprint,source_schema,retrieval_schema,_duration_match,screen_part
from backend.scoring import score_result
from backend.db import Session,Profile,Candidate,Document,Job,Evaluation,Embedding
from backend.jobs import JobManager
from backend.ai import ollama

def test_fast_cache_skips_current_results_and_invalidates_changed_sources(client,project,monkeypatch):
    from backend.jobs import jobs
    ollama.gate=asyncio.Lock();launched=[]
    with Session() as db:
        p=db.get(Profile,project['profile_id']);p.config={**p.config,'depth':'Fast'}
        snapshot={**p.config,'profile_id':p.id}
        c=Candidate(project_id=project['id'],name='Synthetic cached CV');db.add(c);db.flush();cid=c.id
        d=Document(candidate_id=cid,filename='cv.pdf',display_name='cv.pdf',storage_name='cv.pdf',hash='hash',size=100,pages=[{'page':1,'text':'Built production services using Python.'}]);db.add(d);db.flush();did=d.id
        e=Evaluation(candidate_id=cid,profile_id=p.id,profile_version=p.version,profile_snapshot=snapshot,model=p.config['model'],score=60,coverage=60,result={'input_hash':'obsolete-pipeline'},duration=1);db.add(e);db.commit();eid=e.id
    assert client.get('/api/candidates').json()[0]['stale']
    with Session() as db:
        d=db.get(Document,did);e=db.get(Evaluation,eid);e.result={'input_hash':fingerprint(snapshot,p.config['model'],[d])};db.commit()
    assert not client.get('/api/candidates').json()[0]['stale']
    async def status():return {'models':[p.config['model']]}
    monkeypatch.setattr(ollama,'status',status);monkeypatch.setattr(jobs,'launch',launched.append)
    assert client.post('/api/jobs',json={'project_id':project['id']}).status_code==400
    with Session() as db:
        d=db.get(Document,did);d.pages=[{'page':1,'text':'Built production services using Python. Added deployment evidence.'}];db.commit()
    assert client.get('/api/candidates').json()[0]['stale']
    response=client.post('/api/jobs',json={'project_id':project['id']})
    assert response.status_code==200 and len(response.json()['items'])==1 and len(launched)==1

def test_fast_whole_document_provenance_and_partial_row_recovery(profile_payload):
    doc=SimpleNamespace(id='doc',hash='hash',pages=[{'page':1,'text':'Built production services using Python.\nMaintained deployment automation and APIs.'},{'page':2,'text':'Bachelor of Computer Science degree from Example University, 2020.'}])
    prefix,parts,evidence,schema=prepare(profile_payload,[doc])
    assert len(parts)==1 and set(e['page'] for e in evidence.values())=={1,2}
    assert '"weight"' not in prefix
    raw=json.dumps({'C0: Technical skills':{'m':'full','q':'Built production services using Python'},'C1: Education':{'m':'full','q':'Invented masters qualification'},'R0: Documented Python experience':{'m':'full','q':'Built production services using Python'}})
    parsed=decode(raw,profile_payload,evidence,set(parts[0]['ids']))
    result=score_result(profile_payload,[parsed],{('doc',p['page']):p['text'] for p in doc.pages})
    assert result['score']==60 and result['coverage']==60
    assert result['assessments'][1]['status']=='Not established'
    assert result['assessments'][0]['evidence'][0]['page']==1
    assert any('invalid' in w for w in result['warnings'])
    with pytest.raises(ValueError):decode('not JSON',profile_payload,evidence,set(parts[0]['ids']))
    # An otherwise real ID outside this batch cannot establish a qualification.
    assert not decode(raw,profile_payload,evidence,{2}).assessments[0].evidence
    first=fingerprint(profile_payload,'model', [doc]);doc.pages[0]['text']+=' Added source.'
    assert fingerprint(profile_payload,'model',[doc])!=first

def test_quote_grammar_field_isolation_and_explicit_duration(profile_payload):
    doc=SimpleNamespace(id='doc',hash='hash',pages=[{'page':1,'text':'Built production services using Python and automated deployments.'}])
    _,parts,evidence,schema=prepare(profile_payload,[doc])
    wire=source_schema(schema,evidence,parts[0]['ids'])
    assert 'Invented qualification' not in wire['$defs']['SourceQuote']['enum']
    assert wire['properties']['C0: Technical skills']['properties']['q']=={'$ref':'#/$defs/SourceQuote'}
    response=decode(json.dumps({'C0: Technical skills':{'m':'full','q':'Built production services using Python'},'C1: Education':{'m':'unknown','q':''},'R0: Documented Python experience':{'m':'full','q':'Built production services using Python'}}),profile_payload,evidence,set(parts[0]['ids']))
    wire,empty=retrieval_schema(schema,evidence,parts[0]['ids'],profile_payload)
    assert 'C1: Education' in empty
    assert wire['properties']['C0: Technical skills'] is not wire['properties']['R0: Documented Python experience']
    assert _duration_match({'kind':'requirement','name':'Professional software engineering experience','definition':'Minimum 4 years'},'Eight years of professional software engineering experience.')=='full'
    assert _duration_match({'kind':'requirement','name':'Professional software engineering experience','definition':'Minimum 4 years'},'Two years of professional software engineering experience.')=='unknown'
    assert _duration_match({'kind':'requirement','name':'Professional software engineering experience','definition':'Minimum 4 years'},'Eight years of retail marketing experience.') is None

def test_each_field_has_its_own_source_pool(profile_payload):
    doc=SimpleNamespace(id='doc',hash='hash',pages=[{'page':1,'text':'Built production Python services and automated deployment pipelines.'},{'page':2,'text':'Bachelor of Computer Science degree from Example University.'}])
    _,parts,evidence,schema=prepare(profile_payload,[doc]);wire,empty=retrieval_schema(schema,evidence,parts[0]['ids'],profile_payload)
    def pool(key):return wire['$defs'][wire['properties'][key]['properties']['q']['$ref'].split('/')[-1]]['enum']
    assert not empty
    assert any('Python' in q for q in pool('C0: Technical skills'))
    assert any('Computer Science' in q for q in pool('C1: Education'))
    assert not any('Python' in q for q in pool('C1: Education'))

@pytest.mark.asyncio
async def test_short_check_resume_reuses_primary_response(profile_payload):
    profile_payload['criteria'][0]['instructions']='Python production services'
    doc=SimpleNamespace(id='doc',hash='hash',pages=[{'page':1,'text':'Built production Python services and automated deployment pipelines.'}])
    prefix,parts,evidence,schema=prepare(profile_payload,[doc]);entered=asyncio.Event();release=asyncio.Event();saved={};primary=[]
    class Engine:
        async def fast_chat(self,model,messages,schema,progress=None):
            if 'match' in schema['properties']:
                entered.set();await release.wait();return '{"match":"partial"}',{'seconds':.01}
            primary.append(1);return json.dumps({key:'unknown' if key=='C0' else 'full' for key in schema['properties']}),{'seconds':.01}
    def checkpoint(state):saved.update(json.loads(json.dumps(state)))
    task=asyncio.create_task(screen_part(Engine(),'synthetic',profile_payload,prefix,parts[0],evidence,schema,checkpoint=checkpoint))
    await asyncio.wait_for(entered.wait(),5);task.cancel();await asyncio.gather(task,return_exceptions=True)
    assert saved['value']['C0: Technical skills']['m']=='unknown'
    release.set();parsed,_,_=await screen_part(Engine(),'synthetic',profile_payload,prefix,parts[0],evidence,schema,cached=saved,checkpoint=checkpoint)
    assert len(primary)==1 and parsed.assessments[0].score==50

@pytest.mark.asyncio
async def test_fast_pause_keeps_part_checkpoints_and_defers_indexing(project,monkeypatch):
    manager=JobManager();ollama.gate=asyncio.Lock();entered=asyncio.Event();release=asyncio.Event();calls=[];indexed=[]
    with Session() as db:
        p=db.get(Profile,project['profile_id']);snapshot={**p.config,'profile_id':p.id,'depth':'Fast'}
        c=Candidate(project_id=project['id'],name='Synthetic long CV');db.add(c);db.flush();cid=c.id
        # Enough distinct passages for multiple bounded source batches.
        text='\n'.join(f'Project {i}: Built production services using Python and maintained enterprise deployment automation.' for i in range(200))
        db.add(Document(candidate_id=cid,filename='long.pdf',display_name='long.pdf',hash='long',storage_name='long.pdf',size=100,pages=[{'page':1,'text':text}]))
        j=Job(project_id=project['id'],profile_snapshot=snapshot,profile_version=1,model='synthetic-only',items=[{'candidate_id':cid,'state':'pending','name':c.name}]);db.add(j);db.commit();jid=j.id
    async def fake_chat(model,messages,schema,progress):
        calls.append(messages[-1]['content'])
        assert not indexed
        if len(calls)==2:entered.set();await release.wait()
        return json.dumps({key:'full' for key in schema['properties']}),{'eval_count':20,'seconds':.01}
    async def fake_embed(passages):
        with Session() as db:assert db.query(Evaluation).count()==1
        indexed.extend(passages);return [[.1,.2] for _ in passages]
    monkeypatch.setattr(ollama,'fast_chat',fake_chat);monkeypatch.setattr(ollama,'embed',fake_embed)
    manager.launch(jid);await asyncio.wait_for(entered.wait(),5)
    await manager.control(jid,'pause');await manager.tasks[jid]
    with Session() as db:
        j=db.get(Job,jid);assert j.state=='paused' and len(j.items[0]['fast_cache']['parts'])==1
        assert db.query(Evaluation).count()==0
    await manager.control(jid,'resume');release.set();await manager.tasks[jid]
    with Session() as db:
        j=db.get(Job,jid);assert j.state=='completed' and j.items[0]['state']=='completed'
        assert j.items[0]['index_state']=='completed' and db.query(Embedding).count()>0
        assert db.query(Evaluation).count()==1
    assert calls.count(calls[0])==1

@pytest.mark.asyncio
async def test_fast_index_retry_does_not_repeat_assessment(project,monkeypatch):
    manager=JobManager();ollama.gate=asyncio.Lock();calls=[]
    with Session() as db:
        p=db.get(Profile,project['profile_id']);snapshot={**p.config,'profile_id':p.id,'depth':'Fast'}
        c=Candidate(project_id=project['id'],name='Synthetic indexed CV');db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='cv.pdf',display_name='cv.pdf',hash='cv',storage_name='cv.pdf',size=100,pages=[{'page':1,'text':'Built production services using Python and automated deployment pipelines.'}]))
        j=Job(project_id=project['id'],profile_snapshot=snapshot,profile_version=1,model='synthetic-only',items=[{'candidate_id':cid,'state':'pending','name':c.name}]);db.add(j);db.commit();jid=j.id
    async def chat(model,messages,schema,progress):
        calls.append(1)
        return json.dumps({key:'full' for key in schema['properties']}),{}
    async def offline(*args):raise ValueError('Synthetic indexing unavailable')
    monkeypatch.setattr(ollama,'fast_chat',chat);monkeypatch.setattr(ollama,'embed',offline)
    manager.launch(jid);await manager.tasks[jid]
    with Session() as db:assert db.get(Job,jid).items[0]['index_state']=='failed' and db.query(Evaluation).count()==1
    async def embed(passages):return [[.1,.2] for _ in passages]
    monkeypatch.setattr(ollama,'embed',embed)
    await manager.control(jid,'resume');await manager.tasks[jid]
    with Session() as db:assert db.get(Job,jid).items[0]['index_state']=='completed' and db.query(Evaluation).count()==1
    assert len(calls)==1
