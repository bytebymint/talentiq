"""Source review contracts. All CVs and model responses are fictional."""
import asyncio,json
from types import SimpleNamespace as NS
import pytest
from backend.understanding import parse_brief,merge_briefs,source_fingerprint,checked_answer,VERSION
from backend.balanced import prepare,screen_part
from backend.memory import candidate_memory,assemble,select_scope
from backend.ai import ollama
from backend.db import Session,Candidate,Document,Message

TEXT='Ada Example\nSoftware Engineer | Bridgepoint Services LLC | Jan 2021 - Dec 2024\nBuilt Python APIs using Microsoft Dynamics.\nHigh School Diploma, 2019.\nCredential TEST-742.'

def brief():
    return {'summary':{'text':'Built Python APIs.','evidence':[{'source':1,'quote':'Built Python APIs using Microsoft Dynamics.'}]},'work_history':[{'employer':'Bridgepoint Services LLC','title':'Software Engineer','dates':'Jan 2021 - Dec 2024','kind':'employment','evidence':[{'source':1,'quote':'Software Engineer | Bridgepoint Services LLC | Jan 2021 - Dec 2024'}]}],'qualifications':[{'kind':'Education','text':'High School Diploma, 2019.','support':'listed','evidence':[{'source':1,'quote':'High School Diploma, 2019.'}]}],'clarifications':['Clarify production ownership.'],'interview_questions':['Describe the API integration.']}

def doc():return NS(id='doc',hash='hash',filename='Ada.pdf',pages=[{'page':1,'text':TEXT}])

def test_brief_quotes_are_original_and_bound_to_the_current_source():
    evidence={'passages':{1:{'document_id':'doc','page':1,'quote':TEXT},2:{'document_id':'other','page':1,'quote':TEXT}}}
    b=brief();b['qualifications'] += [
        {'kind':'Education','text':'Bachelor degree','evidence':[{'source':1,'quote':'Bachelor degree in computing.'}]},
        {'kind':'Certification','text':'Foreign candidate credential','evidence':[{'source':2,'quote':'Credential TEST-742.'}]}]
    b['work_history'].append({**b['work_history'][0],'employer':'Microsoft'})
    parsed,facts=parse_brief(b,{'ids':[1]},evidence)
    assert len(parsed['work_history'])==1 and parsed['work_history'][0]['employer']=='Bridgepoint Services LLC'
    assert len(parsed['qualifications'])==1 and parsed['omitted_items']==3
    assert all(f['evidence']['quote'] in TEXT for f in facts)
    assert all(f['evidence']['document_id']=='doc' for f in facts)

@pytest.mark.asyncio
async def test_second_pass_corrects_the_proposal_and_uses_original_cv(profile_payload):
    prefix,parts,evidence,schema=prepare(profile_payload,[doc()]);calls=[];checkpoints=[]
    class Engine:
        async def fast_chat(self,model,messages,schema,progress):
            calls.append(messages)
            value={'B':brief(),'C0':{'score':80,'sources':[1],'reason':'Python APIs are documented.'},'C1':{'score':None,'sources':[],'reason':'A computer science degree is not established.'},'R0':{'status':'supported','sources':[1]}}
            if len(calls)==1:value['B']['work_history'][0]['employer']='Microsoft';value['C1']={'score':100,'sources':[1],'reason':'Degree is established.'}
            return json.dumps(value),{'seconds':1,'eval_count':100}
    parsed,metrics,_=await screen_part(Engine(),'fixture',profile_payload,prefix,parts[0],evidence,schema,checkpoint=checkpoints.append)
    assert len(calls)==2 and TEXT in calls[1][1]['content'] and 'PROPOSED JSON' in calls[1][1]['content']
    assert metrics['passes']==2 and metrics['seconds']==2 and metrics['evidence_checked']
    assert metrics['cv_brief']['work_history'][0]['employer']=='Bridgepoint Services LLC'
    assert parsed.assessments[1].score is None
    assert [s['checked'] for s in checkpoints]==[False,True]

@pytest.mark.asyncio
async def test_resume_after_first_pass_only_runs_the_pending_review(profile_payload):
    prefix,parts,evidence,schema=prepare(profile_payload,[doc()]);saved={};calls=[]
    class Engine:
        async def fast_chat(self,*args):
            calls.append(args)
            if len(calls)==2:raise asyncio.CancelledError()
            return json.dumps({'B':brief()}),{'seconds':1}
    def checkpoint(value):saved.update(json.loads(json.dumps(value)))
    with pytest.raises(asyncio.CancelledError):await screen_part(Engine(),'fixture',profile_payload,prefix,parts[0],evidence,schema,checkpoint=checkpoint)
    assert saved['checked'] is False
    _,metrics,_=await screen_part(Engine(),'fixture',profile_payload,prefix,parts[0],evidence,schema,cached=saved,checkpoint=checkpoint)
    assert len(calls)==3 and 'second evidence reviewer' in calls[2][1][0]['content']
    assert saved['checked'] and metrics['evidence_checked']

@pytest.mark.asyncio
@pytest.mark.parametrize('answer',[None,[],42,'No citation','Foreign company. [S2]'])
async def test_chat_rejects_malformed_or_unknown_source_answers(answer):
    class Engine:
        async def chat(self,*args):return json.dumps({'answer':answer})
    with pytest.raises(ValueError,match='source check'):
        await checked_answer(Engine(),'fixture',[{'role':'system','content':'Rules'},{'role':'user','content':TEXT},{'role':'user','content':'Employer?'}],'Microsoft [S1]',[{'source_id':'S1'}])

def test_saved_brief_expires_when_the_original_document_changes():
    d=doc();b,_=parse_brief(brief(),{'ids':[1]},{'passages':{1:{'document_id':d.id,'page':1,'quote':TEXT}}})
    stored=merge_briefs([b],[d],'fixture');c=NS(id='a',name='Ada Example',details={'cv_brief':stored})
    assert candidate_memory(c,[d])['cv_brief']['checked']
    d.pages=[{'page':1,'text':TEXT+'\nChanged source'}]
    assert not candidate_memory(c,[d])['cv_brief']
    assert stored['source_fingerprint']!=source_fingerprint([d])

@pytest.mark.asyncio
async def test_local_review_reserves_output_space_instead_of_dropping_cv_pages(monkeypatch):
    monkeypatch.setattr(ollama,'client',lambda *args:pytest.fail('An oversized review must be rejected before contacting Ollama'))
    schema={'title':'BalancedCV','properties':{'B':{'type':'object'}}}
    with pytest.raises(ValueError,match='local context budget'):
        await ollama.fast_chat('synthetic',[{'role':'user','content':'a'*27000}],schema)

def test_excerpt_context_does_not_import_a_note_with_unseen_supporting_quotes():
    d=doc();d.pages=[{'page':1,'text':'Built Python APIs using Microsoft Dynamics.\n'+'service implementation details '*300},{'page':2,'text':'High School Diploma, 2019. Credential TEST-742.'}]
    reading=merge_briefs([{'summary':{'text':'Python developer with High School Diploma.','evidence':[{'document_id':d.id,'page':1,'quote':'Built Python APIs using Microsoft Dynamics.'},{'document_id':d.id,'page':2,'quote':'High School Diploma, 2019.'}]}}],[d],'fixture')
    m=candidate_memory(NS(id='a',name='Ada Example',details={'cv_brief':reading}),[d])
    sources,facts,coverage=assemble([m],['a'],'Python',1200)
    assert not coverage['complete'] and all(s['page']==1 for s in sources)
    assert not facts[0].get('checked_notes')
    _,facts,coverage=assemble([m],['a'],'Python',30000)
    assert coverage['complete'] and facts[0]['checked_notes']

def test_persian_followup_stays_with_the_selected_candidate():
    a=candidate_memory(NS(id='a',name='Ada Example'),[doc()]);b=candidate_memory(NS(id='b',name='Bea Sample'),[NS(id='bdoc',hash='bhash',filename='Bea.pdf',pages=[{'page':1,'text':'Bea Sample\nAnalyst at Cedarline Retail.'}])])
    assert select_scope('او در کدام شرکت کار کرده است؟',[a,b],['a'])==(['a'],False)
    assert select_scope('هر دو را مقایسه کن',[a,b],['a','b'])==(['a','b'],False)

def test_same_name_requires_selection_before_attributing_experience():
    a=candidate_memory(NS(id='a',name='Ada Example'),[doc()]);b={**a,'id':'b'}
    assert select_scope('Where did Ada Example work?',[a,b])==([],True)
    assert select_scope('Where did Ada Example work?',[a,b],['a'])==(['a'],False)
    assert select_scope('Compare Ada Example CVs',[a,b],['a','b'])==(['a','b'],False)

def test_chat_never_publishes_or_saves_a_draft_that_failed_review(client,project,monkeypatch):
    with Session() as db:
        c=Candidate(project_id=project['id'],name='Ada Example');db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='Ada.pdf',display_name='Ada.pdf',storage_name='fixture.pdf',size=100,hash='hash',pages=doc().pages));db.commit()
    ollama.gate=asyncio.Lock()
    async def stream(messages):yield 'UNCHECKED DRAFT: Microsoft [S1]'
    async def failed(*args):raise ValueError('Synthetic reviewer failure')
    monkeypatch.setattr(ollama,'stream',stream);monkeypatch.setattr(ollama,'chat',failed)
    response=client.post('/api/chat',json={'project_id':project['id'],'candidate_id':cid,'query':'Employer?'})
    assert 'UNCHECKED DRAFT' not in response.text and 'Synthetic reviewer failure' in response.text
    with Session() as db:assert db.query(Message).filter_by(role='assistant').count()==0

def test_checked_answer_is_published_with_source_check_metadata(client,project,monkeypatch):
    with Session() as db:
        c=Candidate(project_id=project['id'],name='Ada Example');db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='Ada.pdf',display_name='Ada.pdf',storage_name='fixture.pdf',size=100,hash='hash',pages=doc().pages));db.commit()
    ollama.gate=asyncio.Lock();ollama.last_generation=None
    async def stream(messages):yield 'Microsoft [S1]'
    async def reviewed(model,messages,schema):
        assert TEXT in messages[1]['content']
        return json.dumps({'answer':'Bridgepoint Services LLC; Microsoft Dynamics is a product. [S1]'})
    monkeypatch.setattr(ollama,'stream',stream);monkeypatch.setattr(ollama,'chat',reviewed)
    packets=[json.loads(line) for line in client.post('/api/chat',json={'project_id':project['id'],'candidate_id':cid,'query':'Employer?'}).text.splitlines()]
    assert any(p.get('checking') for p in packets) and any(p.get('checked') for p in packets)
    with Session() as db:
        m=db.query(Message).filter_by(role='assistant').one()
        assert m.content.startswith('Bridgepoint') and m.sources[0]['answer_check_version']==VERSION
