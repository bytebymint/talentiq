"""Synthetic provider contracts. These tests never use a real API key/network."""
import asyncio,io,json,time,zipfile
import httpx,pytest
from fastapi.testclient import TestClient
from backend.ai import ollama,settings
from backend.db import Session,Setting,Candidate,Document,Evaluation,Job
from backend.qwencloud import cloud,BASE_URL
from backend import credentials
from backend.main import app

KEY='synthetic-cloud-contract-key'

@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch,tmp_path):
    monkeypatch.delenv('DASHSCOPE_API_KEY',raising=False);monkeypatch.delenv('QWENCLOUD_API_KEY',raising=False)
    monkeypatch.setattr(credentials,'_path',lambda:tmp_path/'qwencloud.key')
    ollama.gate=asyncio.Lock();ollama.owned_models.clear();ollama.external_models.clear();ollama.error=None;ollama.state='stopped';cloud.checked=False;cloud.last_error=None

def select_cloud(db):
    credentials.save_key(KEY)
    db.add(Setting(id='app',value={**settings(),'provider':'qwencloud'}));db.commit()

def no_local(*args,**kwargs):raise AssertionError('Cloud mode attempted a local-runtime request')

def transport(monkeypatch,answer='OK',finish='stop',complete=True):
    requests=[]
    def handle(request):
        assert str(request.url).startswith(BASE_URL+'/')
        assert request.headers['Authorization']=='Bearer '+KEY
        body=json.loads(request.content);requests.append((request.url.path,body))
        if request.url.path.endswith('/embeddings'):
            return httpx.Response(200,json={'data':[{'index':i,'embedding':[.1,.2,.3]} for i in range(len(body['input']))]})
        assert body['model']=='qwen3.8-flash' and body['enable_thinking'] is True
        rows=[{'choices':[{'delta':{'reasoning_content':'PRIVATE REASONING MUST NOT LEAK'},'finish_reason':None}]},{'choices':[{'delta':{'content':answer},'finish_reason':None}]},{'choices':[{'delta':{},'finish_reason':finish}]},{'choices':[],'usage':{'prompt_tokens':20,'completion_tokens':10}}]
        data='\n\n'.join('data: '+json.dumps(row) for row in rows)
        if complete:data+='\n\ndata: [DONE]\n\n'
        return httpx.Response(200,content=data,headers={'Content-Type':'text/event-stream'})
    monkeypatch.setattr(cloud,'client',lambda:httpx.AsyncClient(base_url=BASE_URL+'/',headers={'Authorization':'Bearer '+KEY},transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(ollama,'client',no_local)
    return requests

def test_write_only_key_and_provider_settings_backup(client,monkeypatch):
    monkeypatch.setattr(ollama,'client',no_local)
    response=client.put('/api/ai/provider',json={'provider':'qwencloud','api_key':KEY})
    assert response.status_code==200 and response.json()['local_ai_enabled'] is False
    assert KEY not in response.text
    configured=client.get('/api/settings');assert configured.json()['key_configured'] and KEY not in configured.text
    with Session() as db:assert KEY not in json.dumps(db.get(Setting,'app').value)
    backup=client.get('/api/backup')
    with zipfile.ZipFile(io.BytesIO(backup.content)) as archive:
        assert not any('.credentials' in path for path in archive.namelist())
        assert KEY.encode() not in archive.read('talentiq.db')
    assert credentials.get_key()==KEY
    invalid=client.put('/api/ai/provider',json={'api_key':KEY})
    assert invalid.status_code==422 and KEY not in invalid.text

def test_cloud_startup_and_status_never_probe_ollama(client,monkeypatch):
    with Session() as db:select_cloud(db)
    monkeypatch.setattr(ollama,'client',no_local);monkeypatch.setenv('TALENTIQ_AUTO_WARM','1')
    with TestClient(app) as fresh:
        assert fresh.get('/api/health').json()['ai_provider']=='qwencloud'
    status=client.get('/api/ai/status').json()
    assert status['provider']=='qwencloud' and status['models']==['qwen3.8-flash'] and not status['local_ai_enabled']
    assert client.post('/api/ai/pull',json={'model':'qwen3:0.6b','confirm_download':True}).status_code==400

@pytest.mark.asyncio
async def test_streaming_thinking_and_embeddings_use_cloud_only(monkeypatch):
    with Session() as db:select_cloud(db)
    requests=transport(monkeypatch,answer='Synthetic answer.')
    output=''.join([token async for token in ollama.stream([{'role':'user','content':'Synthetic question'}])])
    assert output=='Synthetic answer.' and 'REASONING' not in output
    assert ollama.last_generation['provider']=='qwencloud'
    assert await ollama.embed(['Synthetic Python developer'])==[[.1,.2,.3]]
    assert len(requests)==2

@pytest.mark.asyncio
async def test_stream_interruptions_and_output_limits_are_not_accepted(monkeypatch):
    with Session() as db:select_cloud(db)
    transport(monkeypatch,complete=False)
    with pytest.raises(ValueError,match='before confirming completion'):await cloud.chat([{'role':'user','content':'Synthetic'}])
    transport(monkeypatch,finish='length')
    with pytest.raises(ValueError,match='did not finish'):await cloud.chat([{'role':'user','content':'Synthetic'}],{'type':'object'})
    transport(monkeypatch,answer='')
    with pytest.raises(ValueError,match='no answer'):await cloud.chat([{'role':'user','content':'Synthetic'}])

def test_cloud_job_overrides_local_profile_model_and_records_provider(client,project,monkeypatch):
    with Session() as db:
        select_cloud(db)
        c=Candidate(project_id=project['id'],name='Synthetic Candidate',status='On Hold');db.add(c);db.flush();cid=c.id
        db.add(Document(candidate_id=cid,filename='synthetic.pdf',display_name='synthetic.pdf',hash='hash',storage_name='synthetic.pdf',size=100,pages=[{'page':1,'text':'Synthetic Candidate\nBuilt production services using Python.'}]))
        db.commit()
    answer=json.dumps({'B':{'summary':{'text':'Python services are documented.','evidence':[{'source':1,'quote':'Built production services using Python.'}]},'work_history':[],'qualifications':[],'clarifications':[],'interview_questions':[]},'C0':{'score':80,'sources':[1],'reason':'Production Python is documented.'},'C1':{'score':None,'sources':[],'reason':'Education is not established.'},'R0':{'status':'supported','sources':[1]}})
    requests=transport(monkeypatch,answer)
    response=client.post('/api/jobs',json={'project_id':project['id']})
    assert response.status_code==200,response.text
    job=response.json();assert job['model']=='qwen3.8-flash' and job['profile_snapshot']['_provider']=='qwencloud' and job['profile_snapshot']['depth']=='Balanced'
    for _ in range(50):
        job=client.get('/api/jobs').json()[0]
        if job['state'] in ('completed','error'):break
        time.sleep(.05)
    assert job['state']=='completed' and job['items'][0]['state']=='completed' and job['items'][0]['index_state']=='completed'
    candidate=client.get('/api/candidates/'+cid).json()
    assert candidate['evaluation']['model']=='qwen3.8-flash' and not candidate['stale']
    assert candidate['status']=='On Hold'
    assert candidate['cv_brief']['checked'] and candidate['cv_brief']['summary']['text']=='Python services are documented.'
    assert len([path for path,_ in requests if path.endswith('/chat/completions')])==2
    assert any(path.endswith('/embeddings') for path,_ in requests)
    with Session() as db:
        row=db.get(Setting,'app');row.value={**row.value,'provider':'local'};db.commit()
    assert client.get('/api/candidates/'+cid).json()['stale']

def test_missing_choice_and_invalid_cloud_destination_do_not_start_local(client,monkeypatch):
    with Session() as db:db.add(Setting(id='app',value={'provider':'unconfigured'}));db.commit()
    monkeypatch.setattr(ollama,'client',no_local)
    assert client.get('/api/ai/status').json()['state']=='unconfigured'
    assert client.post('/api/ai/start').status_code==503
    config=client.get('/api/settings').json()
    response=client.put('/api/settings',json={**config,'provider':'qwencloud','cloud_base_url':'https://example.invalid/v1','api_key':KEY})
    assert response.status_code==400 and not credentials._path().exists()

@pytest.mark.asyncio
async def test_provider_auth_errors_are_sanitized_without_fallback(monkeypatch):
    with Session() as db:select_cloud(db)
    monkeypatch.setattr(ollama,'client',no_local)
    monkeypatch.setattr(cloud,'client',lambda:httpx.AsyncClient(base_url=BASE_URL+'/',transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'error':KEY+' PRIVATE CV DATA'}))))
    with pytest.raises(ValueError) as error:await cloud.chat([{'role':'user','content':'Synthetic'}])
    assert KEY not in str(error.value) and 'PRIVATE CV' not in str(error.value) and 'permissions' in str(error.value)

def test_switching_to_local_explicitly_activates_local_runtime(client,monkeypatch):
    with Session() as db:select_cloud(db)
    activated=[]
    async def warm():activated.append('local')
    async def status():return {'provider':'local','local_ai_enabled':True}
    monkeypatch.setattr(ollama,'warm',warm);monkeypatch.setattr(ollama,'status',status)
    response=client.put('/api/ai/provider',json={'provider':'local'})
    assert response.status_code==200 and activated==['local']

@pytest.mark.asyncio
async def test_paused_cloud_job_cannot_resume_with_changed_thinking(project):
    from backend.ai import analysis_config
    from backend.db import Profile
    from backend.jobs import JobManager
    with Session() as db:
        select_cloud(db)
        profile=db.get(Profile,project['profile_id'])
        snapshot=analysis_config(profile.config,profile.id)
        job=Job(project_id=project['id'],state='paused',profile_snapshot=snapshot,profile_version=1,model='qwen3.8-flash',items=[{'candidate_id':'synthetic','state':'pending'}]);db.add(job);db.commit();jid=job.id
        row=db.get(Setting,'app');row.value={**row.value,'cloud_thinking':False};db.commit()
    with pytest.raises(ValueError,match='thinking or context'):await JobManager().control(jid,'resume')

@pytest.mark.asyncio
async def test_local_status_retains_saved_cloud_configuration(monkeypatch):
    credentials.save_key(KEY)
    with Session() as db:
        db.add(Setting(id='app',value={**settings(),'provider':'local','cloud_model':'qwen3.8-flash','cloud_thinking':False}));db.commit()
    def handle(request):
        return httpx.Response(200,json={'models':[],'version':'synthetic'})
    monkeypatch.setattr(ollama,'client',lambda timeout=None:httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handle)))
    status=await ollama.status()
    assert status['key_configured'] and status['cloud_model']=='qwen3.8-flash' and status['cloud_thinking'] is False
    assert KEY not in json.dumps(status)
