import asyncio
import hashlib
import json
import time
from sqlalchemy import select
from .db import Session, Job, Candidate, Document, Evaluation, Embedding, audit, now
from .schemas import AnalysisResponse, analysis_schema, parse_analysis_response
from .scoring import score_result
from .documents import chunks
from .hr import mark_review_ready
from .ai import ollama, settings, active_model, active_embedding_model, context_budget, analysis_config, SYSTEM

class JobManager:
    def __init__(self): self.tasks = {}; self.operations = {}
    def active(self): return any(not t.done() for t in self.tasks.values())
    def launch(self, job_id):
        if job_id in self.tasks and not self.tasks[job_id].done(): raise ValueError('This job is already running.')
        if self.active() or ollama.gate.locked(): raise ValueError('The AI engine is busy. Wait for the current operation.')
        self.tasks[job_id] = asyncio.create_task(self.run(job_id))
        self.tasks[job_id].add_done_callback(lambda task: self.reconcile(job_id))
    def reconcile(self, job_id):
        # Also settles a task cancelled before its coroutine first ran.
        with Session() as db:
            j=db.get(Job,job_id)
            if j and j.state in ('pausing','stopping'):
                j.state='paused' if self.operations.pop(job_id,'stop')=='pause' else 'stopped'
                j.current=None
                j.items=[{**i,'state':'pending'} if i['state']=='processing' else i for i in j.items]
                j.stage='TalentIQ request closed. Internal Ollama execution is not independently observable.'
                j.updated_at=now(); db.commit()
    async def control(self, job_id, action):
        with Session() as db:
            j = db.get(Job,job_id)
            if not j: raise ValueError('Job not found.')
            if action == 'resume':
                if j.profile_snapshot.get('_provider','local')!=settings()['provider'] or (settings()['provider']=='qwencloud' and j.model!=active_model()):raise ValueError('This checkpoint belongs to another AI provider or model. Switch back to resume it, or start a new analysis.')
                if settings()['provider']=='qwencloud' and j.profile_snapshot.get('_provider_options')!=analysis_config(j.profile_snapshot).get('_provider_options'):raise ValueError('Cloud thinking or context settings changed. Restore the checkpoint settings or start a new analysis.')
                if j.state not in ('paused','stopped','completed','error'): raise ValueError('Job cannot be resumed in its current state.')
                if self.active() or ollama.gate.locked(): raise ValueError('The AI engine is busy.')
                j.items = [{**i,'state':'pending','error':None} if i['state'] in ('failed','processing') else i for i in j.items]
                if not any(i['state'] == 'pending' or i.get('index_state') in ('pending','failed') for i in j.items): raise ValueError('No candidates or evidence indexes need retrying.')
                j.state = 'queued'; j.error = None; db.commit(); self.launch(job_id); return
            if action not in ('pause','stop'): raise ValueError('Unknown job action.')
            task = self.tasks.get(job_id)
            if j.state in ('completed','error') and (not task or task.done()): raise ValueError('This job is no longer running.')
            j.state = 'pausing' if action == 'pause' else 'stopping'
            j.stage = 'Closing application-owned request; completed evaluations are preserved.'
            j.updated_at = now(); db.commit()
            self.operations[job_id] = action
            if task and not task.done(): task.cancel()
            else:
                j.state = 'paused' if action == 'pause' else 'stopped'; j.current = None; db.commit()
    async def settle_all(self):
        for jid, task in list(self.tasks.items()):
            if not task.done(): await self.control(jid,'stop')
        await asyncio.gather(*self.tasks.values(),return_exceptions=True)
    def update_item(self,jid,cid,state,**extra):
        with Session() as db:
            j=db.get(Job,jid)
            j.items=[{**i,'state':state,**extra} if i['candidate_id']==cid else i for i in j.items]
            j.updated_at=now(); db.commit()
    def stage(self,jid,message):
        with Session() as db:
            j=db.get(Job,jid); j.stage=message; j.updated_at=now(); db.commit()
    async def run_fast(self,jid,snapshot,model,version,items):
        if snapshot.get('depth')=='Balanced':
            from .balanced import prepare, fingerprint, screen_part, PIPELINE
        else:
            from .fast import prepare, fingerprint, screen_part, PIPELINE
        mode='Balanced' if snapshot.get('depth')=='Balanced' else 'Fast'
        for item in items:
            if item['state']=='completed': continue
            cid=item['candidate_id']; started=time.monotonic()
            self.update_item(jid,cid,'processing')
            with Session() as db:
                j=db.get(Job,jid);j.current=cid;db.commit()
                docs=db.scalars(select(Document).where(Document.candidate_id==cid)).all()
                pages={(d.id,p['page']):p['text'] for d in docs for p in d.pages}
            try:
                prefix,parts,evidence,schema=prepare(snapshot,docs,context_budget())
                if not parts:raise ValueError('No readable source passages are available.')
                digest=fingerprint(snapshot,model,docs)
                cache=item.get('fast_cache') or {}
                saved=cache.get('parts',[]) if cache.get('fingerprint')==digest else []
                active=cache.get('active') if cache.get('fingerprint')==digest else None
                responses=[]
                for n,part in enumerate(parts):
                    label=f'{mode} CV assessment {n+1}/{len(parts)}'
                    if n<len(saved):
                        parsed=AnalysisResponse.model_validate(saved[n]['response'])
                    else:
                        self.stage(jid,label+' · reading resume evidence')
                        def checkpoint(state):self.update_item(jid,cid,'processing',fast_cache={'fingerprint':digest,'parts':saved,'active':{'part':n,**state}})
                        parsed,metrics,_=await screen_part(ollama,model,snapshot,prefix,part,evidence,schema,lambda count:self.stage(jid,label+f' · {count} output fragments received'),checkpoint=checkpoint,cached=active if active and active.get('part')==n else None,status=lambda message:self.stage(jid,message))
                        saved.append({'response':parsed.model_dump(),'metrics':metrics})
                        # Save each long-document part before scheduling another call.
                        self.update_item(jid,cid,'processing',fast_cache={'fingerprint':digest,'parts':saved})
                    responses.append(parsed)
                result=score_result(snapshot,responses,pages)
                if mode=='Balanced':
                    from .understanding import merge_briefs
                    result['cv_brief']=merge_briefs([p['metrics']['cv_brief'] for p in saved if p['metrics'].get('cv_brief')],docs,model)
                result.update(pipeline=PIPELINE,input_hash=digest,inference_metrics=[{'assessment':p['metrics'],'verification':p.get('verification_metrics')} for p in saved])
                with Session() as db:
                    candidate=db.get(Candidate,cid)
                    if not candidate:continue
                    db.add(Evaluation(candidate_id=cid,profile_id=snapshot['profile_id'],profile_version=version,profile_snapshot=snapshot,model=model,scoring_version='documented-balanced-v1' if mode=='Balanced' else 'documented-fast-v1',score=result['score'],coverage=result['coverage'],result=result,duration=time.monotonic()-started))
                    mark_review_ready(candidate);candidate.details={**(candidate.details or {}),'facts':result['facts'],**({'cv_brief':result['cv_brief']} if result.get('cv_brief') else {})}
                    j=db.get(Job,jid);j.items=[{**i,'state':'completed','error':None,'index_state':'pending','fast_cache':None} if i['candidate_id']==cid else i for i in j.items]
                    audit(db,'AI',mode+' evaluation saved',candidate.name,j.project_id,profile_version=version,model=model,pipeline=PIPELINE)
                    db.commit()
            except asyncio.CancelledError:raise
            except Exception as e:
                self.update_item(jid,cid,'failed',error=str(e)[:350])
                with Session() as db:
                    c=db.get(Candidate,cid)
                    if c:mark_review_ready(c)
                    audit(db,'Application',mode+' evaluation requires manual review',cid,db.get(Job,jid).project_id);db.commit()
        # All assessments are saved before loading the embedding model once.
        with Session() as db: index_items=[i.copy() for i in db.get(Job,jid).items if i['state']=='completed' and i.get('index_state') in ('pending','failed')]
        for n,item in enumerate(index_items):
            cid=item['candidate_id']
            with Session() as db:
                j=db.get(Job,jid);j.current=cid;db.commit()
                docs=db.scalars(select(Document).where(Document.candidate_id==cid)).all()
            try:
                parts=list(chunks(docs,size=6000));embed_model=active_embedding_model()
                missing=[]
                for part in parts:
                    digest=hashlib.sha256(part['text'].encode()).hexdigest()
                    with Session() as db:exists=db.query(Embedding).filter_by(candidate_id=cid,model=embed_model,content_hash=digest).first()
                    if not exists:missing.append((part,digest))
                for offset in range(0,len(missing),4):
                    self.stage(jid,f'Evaluations saved · indexing resume {n+1}/{len(index_items)}, passages {offset+1}–{min(offset+4,len(missing))}/{len(missing)}')
                    batch=missing[offset:offset+4];vectors=await ollama.embed([p['text'] for p,_ in batch])
                    with Session() as db:
                        if db.get(Candidate,cid):
                            for (part,digest),vector in zip(batch,vectors):db.add(Embedding(candidate_id=cid,document_id=part['document_id'],model=embed_model,content_hash=digest,page=part['page'],passage=part['text'],vector=vector))
                            db.commit()
                self.update_item(jid,cid,'completed',index_state='completed',index_error=None)
            except asyncio.CancelledError:raise
            except Exception as e:self.update_item(jid,cid,'completed',index_state='failed',index_error=str(e)[:200])
        with Session() as db:
            j=db.get(Job,jid);j.state='completed';j.current=None;j.updated_at=now()
            failures=sum(i['state']=='failed' for i in j.items);index_failures=sum(i.get('index_state')=='failed' for i in j.items)
            j.stage=f'{mode} pass finished · {failures} assessment failures · {index_failures} indexing failures. Review source evidence manually.';db.commit()
    async def run(self,jid):
        try:
            async with ollama.gate:
                ollama.state='processing'
                with Session() as db:
                    j=db.get(Job,jid); j.state='processing'; db.commit()
                    snapshot=j.profile_snapshot; model=j.model; version=j.profile_version
                    if snapshot.get('_provider','local')!=settings()['provider']:raise ValueError('Analysis provider changed. Start a new analysis with the selected provider.')
                    items=[i.copy() for i in j.items]
                if snapshot.get('depth') in ('Fast','Balanced'):
                    await self.run_fast(jid,snapshot,model,version,items)
                    return
                output_schema=analysis_schema(snapshot)
                for item in items:
                    if item['state'] == 'completed': continue
                    cid=item['candidate_id']; start=time.monotonic()
                    self.update_item(jid,cid,'processing')
                    with Session() as db:
                        j=db.get(Job,jid); j.current=cid; db.commit()
                        candidate=db.get(Candidate,cid)
                        if not candidate:
                            self.update_item(jid,cid,'failed',error='Candidate was deleted.'); continue
                        docs=db.scalars(select(Document).where(Document.candidate_id==cid)).all()
                        # Reserve room for instructions, the JSON schema, and generation.
                        # Only application code sees weights: otherwise small local models
                        # can confuse a criterion's weight with its unweighted 0–100 score.
                        rubric={key:snapshot.get(key,'') for key in ('job_title','seniority','instructions','language')}
                        rubric['description']=snapshot.get('description','')[:4000]
                        rubric['criteria']=[{key:c.get(key,'') for key in ('id','name','instructions','mandatory')} for c in snapshot['criteria'] if c['enabled']]
                        rubric['requirements']=snapshot['requirements']
                        reserve=2048 if snapshot.get('depth')=='Detailed' else 1024
                        budget=(context_budget()-reserve)*3-len(json.dumps(rubric))-2*len(json.dumps(output_schema))-len(SYSTEM)-1800
                        if budget<1000: raise ValueError('The profile exceeds the context budget. Simplify it or increase AI context length.')
                        parts=list(chunks(docs,size=min(9000,budget)))
                        pages={(d.id,p['page']):p['text'] for d in docs for p in d.pages}
                    try:
                        if not parts: raise ValueError('No extracted document passages available.')
                        responses=[]
                        for n,part in enumerate(parts):
                            self.stage(jid,f'Assessing document passage {n+1} of {len(parts)}')
                            payload={'rubric':rubric,'response_schema':output_schema,'instructions':f"Evaluate every enabled criterion in a using its exact ID. Matching documented qualifications to a rubric is advisory assessment, not a hiring decision. Score anchors: 100=fully documented fit, 50=partial documented fit; use s=unknown,n=null,q=[] when evidence is absent. For s=yes, n must be numeric and q must contain a short exact source quote. f: at most 4 key facts (k=kind,v=value,q=quote). r: assess every requirement by zero-based index. w: important warnings only. j: at most 2 interview questions. Quotes should be 6-18 words. Application code attaches the source document/page. If the source is a labeled synthetic fixture, assess its supplied hypothetical qualifications and retain a fixture warning; do not withhold the rubric analysis solely because it is fictional. No reasoning preamble or repeated summaries. Depth: {snapshot.get('depth','Standard')}. Language: {snapshot.get('language','English')}."}
                            payload['source']={'text':part['text']}
                            last_error=None
                            for attempt in range(2):
                                try:
                                    extraction_system=SYSTEM.replace('Cite exact source quotations with document_id and page.','Return exact short source quotes; the application attaches the current document ID and page.')
                                    raw=await ollama.chat(model,[{'role':'system','content':extraction_system},{'role':'user','content':json.dumps(payload)}],output_schema)
                                    parsed=parse_analysis_response(raw,part)
                                    required_ids={c['id'] for c in snapshot['criteria'] if c['enabled']}
                                    if {a.criterion_id for a in parsed.assessments} != required_ids:
                                        raise ValueError('The model must assess every rubric criterion using its exact ID.')
                                    if any(a.status=='Supported' and (a.score is None or not a.evidence) for a in parsed.assessments):
                                        raise ValueError('Supported criteria require a numeric unweighted score and exact source evidence.')
                                    responses.append(parsed); last_error=None; break
                                except (ValueError,KeyError) as e: last_error=e
                            if last_error: raise ValueError('The model returned invalid structured output twice. Retry or review manually.')
                        result=score_result(snapshot,responses,pages)
                        self.stage(jid,'Saving verified evaluation checkpoint')
                        with Session() as db:
                            candidate=db.get(Candidate,cid)
                            if not candidate: continue
                            db.add(Evaluation(candidate_id=cid,profile_id=snapshot['profile_id'],profile_version=version,profile_snapshot=snapshot,model=model,score=result['score'],coverage=result['coverage'],result=result,duration=time.monotonic()-start))
                            mark_review_ready(candidate)
                            candidate.details={'facts':result['facts']}
                            names=[f['value'] for f in result['facts'] if f['kind']=='Name']
                            if names: candidate.name=names[0][:160]
                            # The evaluation and its completed checkpoint commit in the same transaction.
                            j=db.get(Job,jid); j.items=[{**i,'state':'completed','error':None} if i['candidate_id']==cid else i for i in j.items]
                            audit(db,'AI','Evaluation saved',candidate.name,j.project_id,profile_version=version,model=model)
                            db.commit()
                        # Retrieval indexing failure never discards a completed evaluation.
                        self.stage(jid,'Indexing local evidence for semantic search')
                        try:
                            embed_model=active_embedding_model()
                            for part in parts:
                                digest=hashlib.sha256(part['text'].encode()).hexdigest()
                                with Session() as db:
                                    exists=db.query(Embedding).filter_by(candidate_id=cid,model=embed_model,content_hash=digest).first()
                                if exists: continue
                                vector=(await ollama.embed([part['text']]))[0]
                                with Session() as db:
                                    if db.get(Candidate,cid):
                                        db.add(Embedding(candidate_id=cid,document_id=part['document_id'],model=embed_model,content_hash=digest,page=part['page'],passage=part['text'],vector=vector)); db.commit()
                        except Exception:
                            with Session() as db:
                                audit(db,'Application','Semantic indexing unavailable',cid,db.get(Job,jid).project_id,remedy='Install the selected embedding model and reindex. Keyword retrieval remains available.'); db.commit()
                    except asyncio.CancelledError: raise
                    except Exception as e:
                        self.update_item(jid,cid,'failed',error=('Inference failed. '+str(e))[:350])
                        with Session() as db:
                            failed_candidate=db.get(Candidate,cid)
                            if failed_candidate: mark_review_ready(failed_candidate)
                            audit(db,'Application','Evaluation requires manual review',cid,db.get(Job,jid).project_id)
                            db.commit()
                with Session() as db:
                    j=db.get(Job,jid); j.state='completed'; j.current=None; j.stage='Finished. Review evidence and approve decisions manually.'; j.updated_at=now(); db.commit()
        except asyncio.CancelledError:
            with Session() as db:
                j=db.get(Job,jid)
                if j:
                    j.items=[{**i,'state':'pending'} if i['state']=='processing' else i for i in j.items]
                    j.state='paused' if self.operations.pop(jid,'stop')=='pause' else 'stopped'
                    j.current=None; j.stage='TalentIQ request closed. Ollama internal execution cannot be independently confirmed.'; j.updated_at=now(); db.commit()
        except Exception as e:
            with Session() as db:
                j=db.get(Job,jid)
                if j: j.state='error'; j.error=str(e)[:300]; j.current=None; db.commit()
        finally:
            ollama.state='stopped'

jobs=JobManager()

