"""Explicit download of official LiquidAI GGUF through Ollama, copied to a local tag."""
import argparse,asyncio,json
from pathlib import Path
import httpx

SOURCE='hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M'
LOCAL='lfm2.5-local:1.2b'

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--confirm-download',action='store_true',required=True);parser.parse_args()
    async with httpx.AsyncClient(base_url='http://127.0.0.1:11434',timeout=1800,trust_env=False) as client:
        last=None
        async with client.stream('POST','/api/pull',json={'model':SOURCE,'stream':True}) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:continue
                item=json.loads(line)
                if item.get('error'):raise ValueError(item['error'])
                status=item.get('status','')
                percent=int(item.get('completed',0)/item['total']*10)*10 if item.get('total') else None
                key=(status,percent)
                if key!=last:print(status+(f' {percent}%' if percent is not None else ''),flush=True);last=key
        copy=await client.post('/api/copy',json={'source':SOURCE,'destination':LOCAL});copy.raise_for_status()
        tags=(await client.get('/api/tags')).json()['models'];local=next(m for m in tags if m['name']==LOCAL)
        provenance={'local_tag':LOCAL,'source':SOURCE,'publisher':'LiquidAI','digest':local['digest'],'size':local['size'],'details':local.get('details')}
        Path('data/fast-model-provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
        print(json.dumps(provenance),flush=True)
if __name__=='__main__':asyncio.run(main())
