import io
import json
import zipfile
import pytest
from pydantic import ValidationError
from backend.schemas import ProfileInput, AnalysisResponse, parse_analysis_response, analysis_schema
from backend.scoring import score_result, rank
from backend.documents import safe_zip, extract, job_text
from backend.ai import local_url, model_name
from backend.db import Session, Job, Profile, Candidate, Evaluation, migrate
from .helpers import pdf_bytes

def response(quote='Built production services using Python.',page=1,score=90):
    return AnalysisResponse.model_validate({'facts':[{'kind':'Skill','value':'Python','evidence':{'document_id':'doc1','page':page,'quote':quote}}],'assessments':[{'criterion_id':'skills','status':'Supported','score':score,'explanation':'Python production services documented.','evidence':[{'document_id':'doc1','page':page,'quote':quote}]}],'requirements':[],'warnings':[],'interview_questions':['Describe your Python service architecture.']})

def test_weighting_and_missing_evidence(profile_payload):
    p=ProfileInput.model_validate(profile_payload).model_dump()
    result=score_result(p,[response()],{('doc1',1):'Built production services using Python.'})
    assert result['score']==54 and result['coverage']==60
    assert result['assessments'][1]['score'] is None
    assert result['assessments'][1]['status']=='Not established'
    assert result['requirements'][0]['status']=='Not established'

def test_hallucinated_passage_and_wrong_page_never_award_points(profile_payload):
    p=ProfileInput.model_validate(profile_payload).model_dump()
    for r in [response(quote='Invented certification and Python expertise.'),response(page=2)]:
        result=score_result(p,[r],{('doc1',1):'Built production services using Python.'})
        assert result['score'] is None and result['coverage']==0 and not result['facts']

def test_documented_absence_of_information_is_not_positive_evidence(profile_payload):
    p=ProfileInput.model_validate(profile_payload).model_dump()
    text='Python service development is not documented in this resume.'
    result=score_result(p,[response(quote=text,score=0)],{('doc1',1):text})
    assert result['score'] is None and result['coverage']==0
    assert result['assessments'][0]['status']=='Not established'
    assert not result['facts']

def test_protected_traits_cannot_be_criteria_or_evidence(profile_payload):
    p=ProfileInput.model_validate(profile_payload).model_dump()
    r=response(quote='Nationality: invented. Built production services using Python.')
    result=score_result(p,[r],{('doc1',1):r.assessments[0].evidence[0].quote})
    assert result['score'] is None
    for name in ['Gender preference','Nationality','Candidate age','Religious alignment']:
        bad={**profile_payload,'criteria':[{**profile_payload['criteria'][0],'name':name,'weight':100}]}
        with pytest.raises(ValidationError): ProfileInput.model_validate(bad)
    assert 'Nationality:' not in job_text('Nationality: Example\nPython developer')

def test_model_schema_rejects_invalid_scores_and_keys():
    d=response().model_dump();d['assessments'][0]['score']=101
    with pytest.raises(ValidationError): AnalysisResponse.model_validate(d)

def test_compact_output_binds_source_and_preserves_evidence_validation(profile_payload):
    contract=analysis_schema(profile_payload)
    assert contract['properties']['a']['minItems']==2
    supported=contract['properties']['a']['items']['anyOf'][0]
    assert supported['properties']['i']['enum']==['skills','education']
    assert supported['properties']['q']['minItems']==1
    raw=json.dumps({'f':[{'k':'Skill','v':'Python','q':'Built production services using Python.'}],'a':[{'i':'skills','s':'yes','n':90,'x':'Python service work is documented.','q':['Built production services using Python.']}],'r':[],'w':[],'j':[]})
    source={'document_id':'actual-source','page':3}
    parsed=parse_analysis_response(raw,source)
    assert parsed.assessments[0].evidence[0].document_id=='actual-source'
    assert parsed.assessments[0].evidence[0].page==3
    profile=ProfileInput.model_validate(profile_payload).model_dump()
    result=score_result(profile,[parsed],{('actual-source',3):'Built production services using Python.'})
    assert result['score']==54 and result['coverage']==60
    assert score_result(profile,[parsed],{('actual-source',3):'Different source text.'})['score'] is None
    swapped=json.dumps({'a':[{'i':'skills','s':'yes','n':90,'x':'Built production services using Python.','q':['Rubric text that is not in the CV.']}],'r':[]})
    recovered=parse_analysis_response(swapped,{**source,'text':'Built production services using Python.'})
    assert recovered.assessments[0].evidence[0].quote=='Built production services using Python.'
    rejected=parse_analysis_response(swapped,{**source,'text':'A completely different source passage.'})
    assert not rejected.assessments[0].evidence
    d=response().model_dump();d['protected_trait']='invented'
    with pytest.raises(ValidationError): AnalysisResponse.model_validate(d)

def test_weights_and_stable_ranking(profile_payload):
    # Job-related words must not be accidentally treated as demographic prefixes.
    legitimate={**profile_payload,'criteria':[{**profile_payload['criteria'][0],'name':'Agency experience and mentoring','weight':100}]}
    ProfileInput.model_validate(legitimate)
    bad={**profile_payload,'criteria':[{**profile_payload['criteria'][0],'weight':25}]}
    with pytest.raises(ValidationError): ProfileInput.model_validate(bad)
    rows=[{'id':'b','created_at':'2026-01-01','score':50,'coverage':60,'gender':'irrelevant'},{'id':'a','created_at':'2026-01-01','score':50,'coverage':60,'nationality':'irrelevant'},{'id':'c','created_at':'2026-01-01','score':None,'coverage':0}]
    assert [r['id'] for r in rank(rows)]==['a','b','c']
    assert [r['id'] for r in rank(rows[::-1])]==['a','b','c']

def test_auth_roles_origin_and_document_boundary(client,project):
    r=client.post('/api/documents/import',data={'project_id':project['id']},files=[('files',('test.pdf',pdf_bytes('Synthetic Python Engineer\nBuilt production services using Python.'),'application/pdf'))]);assert r.status_code==200
    cid=r.json()['results'][0]['candidate_id'];did=client.get('/api/candidates/'+cid).json()['documents'][0]['id']
    assert client.get('/api/documents/'+did+'/original').status_code==200
    assert client.post('/api/projects',json={'name':'attack','profile_id':project['profile_id']},headers={'origin':'https://untrusted.example'}).status_code==403
    assert client.get('/api/documents/../../.env/original').status_code==404
    client.post('/api/users',json={'name':'Synthetic Viewer','username':'viewer','password':'viewer-password-123','role':'viewer'})
    client.post('/api/auth/logout');assert client.get('/api/documents/'+did+'/original').status_code==401
    client.post('/api/auth/login',json={'username':'viewer','password':'viewer-password-123'})
    assert client.post('/api/profiles',json={}).status_code==403
    assert client.get('/api/backup').status_code==403
    assert client.get('/api/documents/'+did+'/original').status_code==200

def test_bulk_50_pdfs_duplicates_and_persistence(client,project):
    files=[('files',(f'synthetic-{i}.pdf',pdf_bytes(f'Synthetic Candidate {i}\nBuilt production services using Python.'),'application/pdf')) for i in range(50)]
    r=client.post('/api/documents/import',data={'project_id':project['id']},files=files)
    assert r.status_code==200 and len(r.json()['results'])==50 and all('candidate_id' in x for x in r.json()['results'])
    assert len(client.get('/api/candidates?project_id='+project['id']).json())==50
    duplicate=client.post('/api/documents/import',data={'project_id':project['id']},files=[files[0]])
    assert duplicate.json()['results'][0]['duplicate']
    migrate()
    with Session() as db: assert db.query(Candidate).filter_by(project_id=project['id']).count()==50

def test_profile_versions_and_project_isolation(client,project,profile_payload):
    p2=client.post('/api/projects',json={'name':'Other synthetic project','profile_id':project['profile_id']}).json()
    r=client.post('/api/documents/import',data={'project_id':project['id']},files={'files':('example.pdf',pdf_bytes('Synthetic candidate with Python work.'),'application/pdf')})
    cid=r.json()['results'][0]['candidate_id']
    assert client.get('/api/candidates?project_id='+p2['id']).json()==[]
    assert client.post('/api/search',json={'project_id':p2['id'],'candidate_id':cid,'query':'Python'}).status_code==400
    assert client.post('/api/comparisons',json={'project_id':p2['id'],'name':'Invalid mix','candidate_ids':[cid,'missing']}).status_code==400
    updated=client.put('/api/profiles/'+project['profile_id'],json={**profile_payload,'name':'Updated synthetic profile'}).json()
    assert updated['version']==2
    versions=client.get('/api/profiles/'+project['profile_id']+'/versions').json();assert len(versions)==2 and versions[1]['config']['name']==profile_payload['name']
    assert client.post('/api/profiles/'+project['profile_id']+'/duplicate').status_code==200

def test_document_failure_zip_security_and_folder_tree(client,project):
    r=client.post('/api/documents/import',data={'project_id':project['id']},files={'files':('broken.pdf',b'not a real PDF','application/pdf')})
    assert r.json()['results'][0]['error']
    for filename in ['../outside.pdf','/absolute.pdf','C:/outside.pdf']:
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr(filename,b'abc')
        with pytest.raises(ValueError):safe_zip(b.getvalue())
    f=client.post('/api/folders',json={'name':'Engineering'}).json();child=client.post('/api/folders',json={'name':'Python','parent_id':f['id']}).json()
    assert client.put('/api/folders/'+f['id'],json={'name':'Bad cycle','parent_id':child['id']}).status_code==400
    assert client.delete('/api/folders/'+f['id']).status_code==400

def test_directory_import_preserves_nested_structure_and_docx(client,project):
    from docx import Document as WordDocument
    doc=WordDocument();doc.add_paragraph('Synthetic DOCX candidate. Python production services.');out=io.BytesIO();doc.save(out)
    result=client.post('/api/documents/import',data={'project_id':project['id'],'preserve_folders':'true'},files=[('files',('Recruitment/Engineering/Synthetic.docx',out.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))])
    assert result.status_code==200,result.text
    cid=result.json()['results'][0]['candidate_id'];c=client.get('/api/candidates/'+cid).json()
    folders=client.get('/api/folders').json();root=next(f for f in folders if f['name']=='Recruitment');child=next(f for f in folders if f['name']=='Engineering')
    assert child['parent_id']==root['id'] and c['documents'][0]['folder_id']==child['id']
    text=client.get('/api/documents/'+c['documents'][0]['id']+'/text').json()
    assert 'Python production services' in text['pages'][0]['text'] and text['warnings']

def test_csv_excel_pdf_backup_restore_and_human_decisions(client,project):
    r=client.post('/api/documents/import',data={'project_id':project['id']},files={'files':('test.pdf',pdf_bytes('Synthetic candidate Python experience.'),'application/pdf')})
    cid=r.json()['results'][0]['candidate_id']
    assert client.patch('/api/candidates/'+cid,json={'status':'Not Selected'}).status_code==400
    assert client.patch('/api/candidates/'+cid,json={'status':'Not Selected','confirm_decision':True,'note':'Synthetic explicit human decision for test.'}).status_code==200
    assert client.patch('/api/candidates/'+cid,json={'shortlisted':True}).json()['shortlisted']==1
    for ext,signature in [('csv',b'\xef\xbb\xbf'),('xlsx',b'PK'),('pdf',b'%PDF-')]:
        r=client.get(f'/api/reports/{project["id"]}?format={ext}');assert r.status_code==200 and r.content.startswith(signature)
    backup=client.get('/api/backup');assert backup.content.startswith(b'PK')
    client.delete('/api/candidates/'+cid);assert not client.get('/api/candidates').json()
    result=client.post('/api/restore',data={'confirm':'true'},files={'file':('backup.zip',backup.content,'application/zip')});assert result.status_code==200,result.text
    assert client.get('/api/auth/me').status_code==401
    client.post('/api/auth/login',json={'username':'testadmin','password':'test-password-12345'})
    assert len(client.get('/api/candidates').json())==1

def test_restart_recovers_interrupted_checkpoints(project):
    with Session() as db:
        p=db.get(Profile,project['profile_id'])
        j=Job(project_id=project['id'],state='processing',profile_snapshot=p.config,profile_version=1,model='test',items=[{'candidate_id':'finished','state':'completed'},{'candidate_id':'interrupted','state':'processing'}]);db.add(j);db.commit();jid=j.id
    migrate()
    with Session() as db:
        j=db.get(Job,jid);assert j.state=='paused' and [i['state'] for i in j.items]==['completed','pending']

def test_ollama_endpoint_and_model_boundaries():
    for url in ['https://cloud.example','http://169.254.169.254','http://localhost:11434/private','http://user:password@localhost:11434']:
        with pytest.raises(ValueError):local_url(url)
    for name in ['qwen3:cloud','other/model','bad name']:
        with pytest.raises(ValueError):model_name(name)
    assert local_url('http://127.0.0.1:11434')=='http://127.0.0.1:11434'
