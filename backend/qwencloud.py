"""QwenCloud's OpenAI-compatible protocol. Never contacts a local AI runtime."""
import json,math,re,time
import httpx
from .credentials import get_key

BASE_URL='https://ap-southeast-1.maas.qwencloudapi.com/compatible-mode/v1'

def cloud_url(value):
    if value.rstrip('/')!=BASE_URL:raise ValueError('Use the QwenCloud Singapore HTTPS endpoint configured for this integration.')
    return BASE_URL

def cloud_model(value):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}',value):raise ValueError('Enter a valid QwenCloud model ID.')
    return value

class QwenCloud:
    def __init__(self):self.last_generation=None;self.checked=False;self.last_error=None
    def configuration(self):
        from .ai import settings
        s=settings()
        if s['provider']!='qwencloud':raise ValueError('QwenCloud is not selected.')
        return s
    def client(self):
        s=self.configuration();key=get_key()
        if not key:raise ValueError('Configure a QwenCloud API key before connecting.')
        return httpx.AsyncClient(base_url=cloud_url(s['cloud_base_url'])+'/',headers={'Authorization':'Bearer '+key},timeout=httpx.Timeout(s['timeout'],connect=20),trust_env=False,follow_redirects=False)
    async def check_response(self,response):
        if response.is_success:return
        # Do not propagate request headers, provider bodies or CV-bearing errors.
        if response.status_code in (401,403):message='QwenCloud rejected the API key or its permissions. Check its Singapore region and model access.'
        elif response.status_code==429:message='QwenCloud rate or account quota limit reached. Retry after checking your account quota.'
        else:message=f'QwenCloud request failed (HTTP {response.status_code}). Check the model, endpoint and account access.'
        raise ValueError(message)
    async def stream(self,messages,schema=None,progress=None):
        s=self.configuration();began=time.monotonic();count=0;last=0;finished=False;usage={};reason=None;answered=False
        self.last_generation=None
        payload={'model':cloud_model(s['cloud_model']),'messages':list(messages),'stream':True,'stream_options':{'include_usage':True},'enable_thinking':s['cloud_thinking'],'max_completion_tokens':8192,'temperature':s['temperature']}
        if s['cloud_thinking']:payload['thinking_budget']=2048
        if schema:
            # JSON mode + an explicit contract works with thinking models and
            # the varied local grammars. Application validation still decides
            # which fields/source references can be accepted.
            payload['response_format']={'type':'json_object'}
            payload['messages']=[*messages,{'role':'user','content':'Return JSON only, conforming to this response schema:\n'+json.dumps(schema,ensure_ascii=False)}]
        from .ai import context_budget
        text=json.dumps(payload['messages'],ensure_ascii=False)
        factor=1.2 if sum(ord(c)>127 for c in text)/max(1,len(text))>.1 else 3
        if len(text)>(context_budget()-8192)*factor:raise ValueError('QwenCloud request exceeds the selected context budget. Narrow the selection or increase the cloud context limit.')
        try:
            async with self.client() as client:
                async with client.stream('POST','chat/completions',json=payload) as response:
                    await self.check_response(response)
                    async for line in response.aiter_lines():
                        if not line.startswith('data:'):continue
                        data=line[5:].strip()
                        if data=='[DONE]':finished=True;break
                        if not data:continue
                        item=json.loads(data)
                        if item.get('error'):raise ValueError('QwenCloud reported a generation error. Retry or inspect account diagnostics.')
                        if item.get('usage'):usage=item['usage']
                        for choice in item.get('choices',[]):
                            delta=choice.get('delta',{})
                            # Raw reasoning is deliberately not displayed/stored.
                            if delta.get('reasoning_content') or delta.get('content'):
                                count+=1
                                if progress and time.monotonic()-last>=2:progress(count);last=time.monotonic()
                            token=delta.get('content')
                            if token:answered=True;yield token
                            if choice.get('finish_reason'):reason=choice['finish_reason']
            if not finished or not reason:raise ValueError('QwenCloud stream ended before confirming completion. No complete response was confirmed.')
            if reason not in ('stop','length'):raise ValueError('QwenCloud did not return a complete answer. Check the request and retry.')
            if not answered:raise ValueError('QwenCloud returned no answer. Retry the request.')
            self.checked=True;self.last_error=None
            self.last_generation={'provider':'qwencloud','model':s['cloud_model'],'done_reason':reason,'seconds':round(time.monotonic()-began,3),'eval_count':usage.get('completion_tokens',0),'prompt_eval_count':usage.get('prompt_tokens',0),'usage':usage}
        except ValueError as error:
            self.checked=False;self.last_error=str(error);raise
        except httpx.TimeoutException:raise ValueError('QwenCloud timed out. Retry the request; no local fallback was started.') from None
        except httpx.HTTPError:raise ValueError('Could not connect to QwenCloud. Check this server’s internet connection; no local fallback was started.') from None
    async def chat(self,messages,schema=None,progress=None):
        output=''.join([token async for token in self.stream(messages,schema,progress)])
        if self.last_generation['done_reason']!='stop':raise ValueError('QwenCloud did not finish the structured response. Retry with a smaller request.')
        if not output.strip():raise ValueError('QwenCloud returned no answer.')
        return output
    async def embed(self,passages):
        s=self.configuration()
        try:
            async with self.client() as client:
                response=await client.post('embeddings',json={'model':cloud_model(s['cloud_embedding_model']),'input':passages,'encoding_format':'float','dimensions':1024})
                await self.check_response(response)
                data=sorted(response.json().get('data',[]),key=lambda item:item['index'])
        except httpx.HTTPError:raise ValueError('QwenCloud embedding request could not connect. No local model was started.') from None
        vectors=[item['embedding'] for item in data]
        if len(vectors)!=len(passages) or any(not v or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in v) for v in vectors):raise ValueError('QwenCloud returned invalid embeddings.')
        return vectors

cloud=QwenCloud()
