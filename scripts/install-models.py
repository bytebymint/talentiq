"""Explicit local model setup; never run automatically during ordinary startup."""
import argparse
import asyncio
import json
import time
from pathlib import Path
import httpx

MODELS=['qwen3.5:4b-q4_K_M','qwen3:0.6b','qwen3:4b-instruct','qwen3-embedding:0.6b']
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'data'/'model-install-status.json'
progress={}

def persist():
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(progress,indent=2),encoding='utf-8')

async def main():
    parser=argparse.ArgumentParser(description='Download real local Ollama models (several GB).')
    parser.add_argument('--confirm-download',action='store_true',required=True)
    parser.add_argument('--models',nargs='+',choices=MODELS+['qwen3.5:2b-q4_K_M','qwen3:1.7b','qwen2.5:1.5b'],default=MODELS)
    selected=parser.parse_args().models
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=httpx.Timeout(1800,connect=15),trust_env=False) as client:
        version=await client.get('/api/version');version.raise_for_status();print('Ollama '+version.json()['version'],flush=True)
        tags=await client.get('/api/tags');tags.raise_for_status();installed={m['name'] for m in tags.json().get('models',[])}
        async def pull(model):
            if model in installed:
                progress[model]={'status':'success','already_installed':True};persist();print(model+': already installed',flush=True);return
            last=None;last_save=0
            async with client.stream('POST','/api/pull',json={'model':model,'stream':True}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:continue
                    event=json.loads(line)
                    if event.get('error'):raise RuntimeError(model+': '+event['error'])
                    progress[model]=event
                    percentage=int(event.get('completed',0)/max(event.get('total',1),1)*100)
                    signature=(event.get('status'),percentage//10)
                    if signature!=last:
                        detail=f" {percentage}% ({event.get('completed',0)/1024**2:.0f}/{event.get('total',0)/1024**2:.0f} MiB)" if event.get('total') else ''
                        print(model+': '+event.get('status','')+detail,flush=True);last=signature
                    if time.monotonic()-last_save>2 or event.get('status')=='success':persist();last_save=time.monotonic()
        outcomes=await asyncio.gather(*(pull(model) for model in selected),return_exceptions=True)
        for outcome in outcomes:
            if isinstance(outcome,BaseException):raise outcome
        tags=await client.get('/api/tags');tags.raise_for_status();installed={m['name'] for m in tags.json()['models']}
        if not all(model in installed for model in selected):raise RuntimeError('Ollama did not list every requested model after download.')
        print('REQUESTED LOCAL MODELS VERIFIED INSTALLED',flush=True)

if __name__=='__main__':asyncio.run(main())
