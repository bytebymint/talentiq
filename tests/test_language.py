"""Language selection must not change source evidence or machine-readable values."""
import asyncio,json
from types import SimpleNamespace as NS
import pytest
from backend.ai import analysis_config,ollama
from backend.db import Session,Candidate,Document,Message
from backend.language import ui_language,cache
from backend.memory import chat_messages,assemble,candidate_memory

def test_language_snapshot_is_scoped_and_preserves_profile(profile_payload):
    original=json.dumps(profile_payload,sort_keys=True)
    token=ui_language.set('fa')
    try:
        assert analysis_config(profile_payload,language=ui_language.get())['language']=='Persian'
        assert analysis_config(profile_payload).get('language','English')=='English'
    finally:ui_language.reset(token)
    assert analysis_config(profile_payload).get('language','English')=='English'
    assert json.dumps(profile_payload,sort_keys=True)==original

def test_farsi_chat_uses_persian_instruction_but_original_sources(client,project,monkeypatch):
    with Session() as db:
        c=Candidate(name='Synthetic Ada',project_id=project['id']);db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='original.docx',display_name='original.docx',storage_name='original.docx',hash='fa-source',size=100,pages=[{'page':1,'text':'Synthetic Ada\nEngineer at Alpha Systems, 2024. Credential TEST-742.'}]));db.commit()
    captured=[];ollama.gate=asyncio.Lock()
    async def stream(messages):
        captured.extend(messages);yield 'نام کارفرما Alpha Systems است. [S1]'
    async def check(model,messages,schema):
        return json.dumps({'answer': ''.join([piece async for piece in stream(messages)])})
    monkeypatch.setattr(ollama,'chat',check)
    monkeypatch.setattr(ollama,'stream',stream)
    response=client.post('/api/chat',headers={'X-TalentIQ-Language':'fa'},json={'project_id':project['id'],'candidate_id':cid,'query':'نام کارفرما چیست؟','language':'fa'})
    assert response.status_code==200 and response.headers['content-language']=='fa'
    assert 'natural Persian' in captured[0]['content']
    assert 'Credential TEST-742.' in captured[1]['content']
    packets=[json.loads(line) for line in response.text.splitlines()]
    assert packets[0]['sources'][0]['answer_language']=='fa'
    with Session() as db:
        assert db.query(Document).first().pages[0]['text'].endswith('Credential TEST-742.')
        assert db.query(Message).filter_by(role='assistant').first().content.startswith('نام کارفرما')

def test_translation_cache_and_source_references(client,monkeypatch):
    cache.clear();calls=[];ollama.gate=asyncio.Lock()
    async def chat(model,messages,schema):
        calls.append(messages);return json.dumps({'translations':['کارجو 6 ساعت صرفه‌جویی کرده است. [S1]']})
    monkeypatch.setattr(ollama,'chat',chat)
    body={'texts':['Candidate saved 6 hours. [S1]'],'language':'fa'}
    first=client.post('/api/translations',json=body);second=client.post('/api/translations',json=body)
    assert first.status_code==200 and first.json()==second.json() and len(calls)==1
    assert 'untrusted' in calls[0][0]['content']
    assert client.post('/api/translations',json={'texts':['a'*20001],'language':'fa'}).status_code==422
    cache.clear()

@pytest.mark.parametrize('answer',['بهبود 6 ساعته. [S2]','بهبود 60 ساعته. [S1]'])
def test_translation_rejects_changed_references_or_numbers(client,monkeypatch,answer):
    cache.clear();ollama.gate=asyncio.Lock()
    async def chat(*args):return json.dumps({'translations':[answer]})
    monkeypatch.setattr(ollama,'chat',chat)
    response=client.post('/api/translations',json={'texts':['Improvement of 6 hours. [S1]'],'language':'fa'})
    assert response.status_code==400 and not cache

def test_catalog_covers_every_original_interface_string():
    from pathlib import Path
    catalog=json.loads(Path('app/fa.json').read_text(encoding='utf-8'))
    visible=set(json.loads(Path('tests/fixtures/interface-strings.json').read_text(encoding='utf-8')))
    assert visible<=catalog.keys()
    assert all(sorted(__import__('re').findall(r'\{\d+\}',key))==sorted(__import__('re').findall(r'\{\d+\}',value)) for key,value in catalog.items())
    for key in ['Overview','Candidate Library','Recruitment Profiles','Close dialog','Not established','Review CV','Match to role','Interview questions','Username','Password']:
        assert __import__('re').search(r'[\u0600-\u06ff]',catalog[key])


def test_persian_criteria_and_digits_preserve_evidence_checks():
    from backend.balanced import screen_part
    profile={'criteria':[{'id':'impact','name':'دستاوردهای مرتبط','enabled':True,'weight':100}],'requirements':[{'expected_value':'حداقل ۳ سال'}]}
    passages={1:{'document_id':'doc','page':1,'quote':'Saved 14 hours monthly. Stated 2 years of experience.'}}
    evidence={'facts':[],'passages':passages,'pages':{('doc',1):passages[1]['quote']}}
    cached={'value':{'C0':{'score':80,'sources':[1],'reason':'صرفه‌جویی ۱۴ ساعته در ماه.'},'R0':{'status':'supported','sources':[1]}},'metrics':{}}
    parsed,_,_=asyncio.run(screen_part(None,'model',profile,'',{'ids':[1]},evidence,{},cached=cached,quality_review=False))
    assert parsed.assessments[0].score==80
    assert parsed.assessments[0].evidence[0].quote==passages[1]['quote']
    assert parsed.requirements[0].status=='Not established'


def test_persian_protected_trait_guard_and_negative_evidence(client,project,profile_payload):
    from backend.schemas import Evidence
    from backend.scoring import valid_evidence
    profile_payload['criteria'][0]['name']='سن کارجو'
    assert client.post('/api/profiles',json=profile_payload).status_code==422
    assert client.post('/api/chat',json={'project_id':project['id'],'query':'سن کارجو چقدر است؟','language':'fa'}).status_code==400
    quote='این مهارت در رزومه ذکر نشده است.'
    assert not valid_evidence(Evidence(document_id='doc',page=1,quote=quote),{('doc',1):quote})


def test_translation_protects_names_and_ids_without_freezing_role_terms():
    from backend.language import protect_names
    text='Casey Example is a Software Engineer at Alpha Systems. Credential TEST-FA-742.'
    masked,mapping=protect_names(text,['Casey Example'])
    assert 'Casey Example' not in masked and 'Alpha Systems' not in masked and 'TEST-FA-742' not in masked
    assert 'Software Engineer' in masked
    for token,original in mapping.items():masked=masked.replace(token,original)
    assert masked==text
