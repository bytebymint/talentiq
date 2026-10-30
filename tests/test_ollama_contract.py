"""Provider contracts use an HTTP mock transport. This is not real-model validation."""
import json
import httpx
import pytest
from backend.ai import Ollama, settings

@pytest.mark.asyncio
async def test_warm_verifies_residency_shutdown_preserves_shared_models(monkeypatch):
    provider=Ollama();selected=settings()['model'];resident={'shared-model:latest'};unloads=[]
    def handle(request):
        route=request.url.path
        if route=='/api/tags':return httpx.Response(200,json={'models':[{'name':selected}]})
        if route=='/api/ps':return httpx.Response(200,json={'models':[{'name':n} for n in resident]})
        if route=='/api/version':return httpx.Response(200,json={'version':'synthetic-contract-only'})
        body=json.loads(request.content)
        if route=='/api/chat':
            assert body['messages']==[] and body['stream'] is False
            resident.add(selected);return httpx.Response(200,json={'done':True})
        if route=='/api/generate':
            assert body['keep_alive']==0;unloads.append(body['model']);resident.discard(body['model']);return httpx.Response(200,json={'done':True})
        raise AssertionError(route)
    monkeypatch.setattr(provider,'client',lambda timeout=None:httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handle)))
    await provider.warm();assert provider.state=='ready' and selected in provider.owned_models
    result=await provider.shutdown();assert result['state']=='stopped' and unloads==[selected] and resident=={'shared-model:latest'}

@pytest.mark.asyncio
async def test_structured_output_and_stream_contracts(monkeypatch):
    provider=Ollama();selected=settings()['model'];schema={'type':'object','properties':{'answer':{'type':'string'}}}
    def handle(request):
        if request.url.path=='/api/ps':return httpx.Response(200,json={'models':[]})
        body=json.loads(request.content);assert body['model']==selected
        if body['stream']:
            return httpx.Response(200,content='\n'.join(json.dumps(row) for row in [{'message':{'content':'Evidence '}},{'message':{'content':'only.'}},{'done':True}]),headers={'content-type':'application/x-ndjson'})
        assert body['format']==schema and body['options']['temperature']<=0.5
        return httpx.Response(200,json={'message':{'content':'{"answer":"evidence"}'}})
    monkeypatch.setattr(provider,'client',lambda timeout=None:httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handle)))
    assert json.loads(await provider.chat(selected,[{'role':'user','content':'Synthetic contract test'}],schema))['answer']=='evidence'
    assert ''.join([token async for token in provider.stream([{'role':'user','content':'Synthetic streaming test'}])])=='Evidence only.'

@pytest.mark.asyncio
async def test_offline_status_is_truthful(monkeypatch):
    provider=Ollama()
    def handle(request):raise httpx.ConnectError('Synthetic offline transport')
    monkeypatch.setattr(provider,'client',lambda timeout=None:httpx.AsyncClient(base_url='http://127.0.0.1:11434',transport=httpx.MockTransport(handle)))
    state=await provider.status();assert not state['online'] and state['state']=='offline' and state['models']==[]
