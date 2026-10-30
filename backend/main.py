import asyncio
import csv
import hashlib
import hmac
import io
import json
import math
import os
import secrets
import sqlite3
import time
import zipfile
import httpx
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, SecretStr
from typing import Literal
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from .db import *
from .schemas import ProfileInput, Strict, STAGES, PROTECTED
from .documents import extract, safe_name, safe_zip, MAX_FILE, chunks
from .ai import ollama, settings, local_url, model_name, active_model, active_embedding_model, context_budget, analysis_config, SYSTEM, DEFAULTS
from .jobs import jobs
from .scoring import rank
from .hr import ANSWER_INSTRUCTIONS, playbook
from .language import ui_language, request_language, response_instruction, TranslationInput, translate_texts

chat_tasks = set()
login_attempts = {}
@asynccontextmanager
async def lifespan(app):
    migrate()
    async def preload_installed_model():
        status=await ollama.status()
        if active_model() in status['models']:
            try: await ollama.warm()
            except Exception: pass  # Diagnostics expose the actionable error; the workspace still starts.
    warm_task=asyncio.create_task(preload_installed_model()) if os.environ.get('TALENTIQ_AUTO_WARM','1')=='1' and settings()['provider']=='local' else None
    yield
    if warm_task and not warm_task.done():
        warm_task.cancel()
        await asyncio.gather(warm_task,return_exceptions=True)
    await jobs.settle_all()
    for t in list(chat_tasks): t.cancel()
    if ollama.pull_task: ollama.pull_task.cancel()

app = FastAPI(title='TalentIQ Local API', version='1.0.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url='/api/openapi.json')

@app.get('/api/docs',response_class=HTMLResponse,include_in_schema=False)
def local_api_docs(request:Request):
    if request_language(request)=='fa':
        return """<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>راهنمای رابط برنامه‌نویسی تلنت‌آی‌کیو</title><style>body{font:16px/2 Tahoma,sans-serif;max-width:850px;margin:60px auto;padding:0 24px;color:#252838;background:#f7f8fa}h1{font-size:28px}code{direction:ltr;display:inline-block;background:#eeebfc;padding:2px 7px;border-radius:5px}a{color:#6254d9}li{margin:12px 0}</style><h1>راهنمای رابط برنامه‌نویسی تلنت‌آی‌کیو</h1><p>درخواست‌های برنامه با نشست کاربری احراز هویت می‌شوند. درخواست‌های تغییر اطلاعات به سرآیند <code>X-TalentIQ-Request: 1</code> و مبدأ مجاز نیاز دارند.</p><p><a href="/api/openapi.json">مشاهدهٔ ساختار کامل رابط برنامه‌نویسی</a></p><h2>منابع اصلی</h2><ul><li><code>/api/health</code> وضعیت سرویس و راه‌اندازی اولیه</li><li><code>/api/profiles</code> الگوهای ارزیابی و نسخه‌های آن‌ها</li><li><code>/api/projects</code> پروژه‌های مستقل استخدام</li><li><code>/api/documents/import</code> وارد کردن رزومه‌ها</li><li><code>/api/candidates</code> کارجویان، بررسی‌ها و ارزیابی‌ها</li><li><code>/api/jobs</code> جلسه‌های تحلیل و پیشرفت پردازش</li><li><code>/api/ai/status</code> وضعیت ارائه‌دهندهٔ هوش مصنوعی</li><li><code>/api/chat</code> گفت‌وگو با دستیار بر اساس شواهد رزومه</li><li><code>/api/translations</code> ترجمهٔ توضیحات هوشمند با حفظ ارجاع‌ها</li></ul><p>نام مسیرها و شناسه‌های فنی، بخشی از قرارداد رابط برنامه‌نویسی هستند.</p></html>"""
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>TalentIQ Local API</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:800px;margin:60px auto;padding:0 24px;color:#252838;background:#f7f8fa}h1{letter-spacing:-1px}a{color:#6254d9}code{background:#e9eaf0;padding:3px 6px;border-radius:4px}pre{padding:20px;background:#fff;border:1px solid #dddfe8;border-radius:10px;overflow:auto}small{color:#636a7b}</style><h1>TalentIQ Local API</h1><p>All application requests use authenticated local sessions. State changes require the <code>X-TalentIQ-Request: 1</code> header and a permitted localhost origin.</p><p><a href="/api/openapi.json">Open the complete OpenAPI schema →</a></p><h2>Core resources</h2><ul><li><code>/api/health</code> — backend status and first-run state</li><li><code>/api/profiles</code> — versioned recruitment rubrics</li><li><code>/api/projects</code> — independent hiring contexts</li><li><code>/api/documents/import</code> — authenticated multipart resume import</li><li><code>/api/candidates</code> — candidates, reviews, and evaluations</li><li><code>/api/jobs</code> — persistent analysis sessions</li><li><code>/api/events</code> — server-sent progress events</li><li><code>/api/ai/status</code> — verified local Ollama diagnostics</li><li><code>/api/chat</code> — project-grounded streaming chat</li></ul><h2>Example, in the authenticated application origin</h2><pre>await fetch('/api/jobs', {\n  method: 'POST',\n  headers: {\n    'Content-Type': 'application/json',\n    'X-TalentIQ-Request': '1'\n  },\n  body: JSON.stringify({ project_id: 'YOUR_PROJECT_ID' })\n});</pre><small>This documentation uses only local content. No third-party scripts, CDN assets, or remote fonts are requested.</small></html>'''

@app.middleware('http')
async def boundary(request:Request, call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('localhost','127.0.0.1','testserver'):
        return Response('Local access only',403)
    max_body=512*1024*1024 if request.url.path=='/api/restore' else 256*1024*1024
    try:
        if int(request.headers.get('content-length','0'))>max_body: return Response('Request exceeds the upload safety limit',413)
    except ValueError: return Response('Invalid content length',400)
    if request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('x-talentiq-request') != '1': return Response('Missing same-origin request header',403)
        origin=request.headers.get('origin')
        if origin and origin not in ('http://127.0.0.1:3000','http://localhost:3000','http://127.0.0.1:8000','http://localhost:8000'):
            return Response('Origin rejected',403)
    token=ui_language.set(request_language(request))
    try:response=await call_next(request)
    finally:ui_language.reset(token)
    if request_language(request):response.headers['Content-Language']=request_language(request)
    response.headers['Cache-Control']='no-store, no-transform' if request.url.path=='/api/events' else 'no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(ValueError)
async def value_error(_,e): return __import__('fastapi').responses.JSONResponse({'detail':str(e)[:500]},status_code=400)

@app.exception_handler(RequestValidationError)
async def request_validation_error(_,error):
    # Validation errors can otherwise echo the whole request body, including a
    # write-only API key when another required field is missing.
    detail=[{key:value for key,value in item.items() if key in ('loc','msg','type')} for item in error.errors()]
    return __import__('fastapi').responses.JSONResponse({'detail':detail},status_code=422)

@app.exception_handler(httpx.HTTPError)
async def inference_error(_,e):
    return __import__('fastapi').responses.JSONResponse({'detail':'The local Ollama request failed. Check AI Workspace, the installed model tag, and request timeout, then retry.'},status_code=503)

def db_session():
    with Session() as db: yield db
def user(request:Request,db=Depends(db_session)):
    token=request.cookies.get('talentiq_session','')
    session=db.query(Login).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
    if not session or session.expires < time.time(): raise HTTPException(401,'Sign in to your local workspace.')
    u=db.get(User,session.user_id)
    if not u: raise HTTPException(401,'Session expired.')
    return u
def writer(u=Depends(user)):
    if u.role not in ('admin','reviewer'): raise HTTPException(403,'A reviewer or administrator is required.')
    return u
def admin(u=Depends(user)):
    if u.role != 'admin': raise HTTPException(403,'Administrator access required.')
    return u
def require(db, cls, id):
    obj=db.get(cls,id)
    if not obj: raise HTTPException(404,f'{cls.__name__} not found.')
    return obj
def record(obj,exclude=()): return {c.name:getattr(obj,c.name) for c in obj.__table__.columns if c.name not in exclude}
def password_hash(password):
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
def password_valid(password,stored):
    salt,digest=stored.split(':')
    return hmac.compare_digest(digest,hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex())
def set_login(db,u,response):
    token=secrets.token_urlsafe(48)
    db.add(Login(user_id=u.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires=time.time()+43200))
    db.commit()
    response.set_cookie('talentiq_session',token,httponly=True,samesite='strict',max_age=43200,path='/')
def assert_idle():
    if jobs.active(): raise HTTPException(409,'Stop active analysis before changing or deleting its inputs.')

class Credentials(Strict):
    username:str=Field(min_length=3,max_length=80)
    password:str=Field(min_length=1,max_length=200)
class Setup(Credentials):
    name:str=Field(min_length=2,max_length=100)
class NewUser(Setup):
    role:str='reviewer'

@app.get('/api/health')
def health(db=Depends(db_session)):
    return {'ok':True,'setup_required':db.query(User).count()==0,'version':'1.0.0','database':'SQLite · WAL','local_only':True,'inference_local':settings()['provider']=='local','ai_provider':settings()['provider'],'ai_state':ollama.state}
@app.post('/api/auth/setup')
def setup(body:Setup,response:Response,db=Depends(db_session)):
    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    if db.query(User).count(): raise HTTPException(409,'Workspace is already configured. Sign in.')
    if len(body.password)<12: raise ValueError('Use a password of at least 12 characters.')
    u=User(name=body.name,username=body.username.casefold(),password=password_hash(body.password),role='admin'); db.add(u)
    try: db.flush()
    except Exception: db.rollback(); raise HTTPException(409,'Setup conflict; reload and sign in.')
    audit(db,u.name,'Workspace created'); set_login(db,u,response)
    return record(u,('password',))
@app.post('/api/auth/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(db_session)):
    key=(request.client.host,body.username.casefold()); attempts=login_attempts.get(key,[]); attempts=[t for t in attempts if t>time.time()-300]
    if len(attempts)>=8: raise HTTPException(429,'Too many sign-in attempts. Try again in five minutes.')
    u=db.query(User).filter_by(username=body.username.casefold()).first()
    if not u or not password_valid(body.password,u.password):
        login_attempts[key]=attempts+[time.time()]; raise HTTPException(401,'Username or password is incorrect.')
    login_attempts.pop(key,None); set_login(db,u,response)
    return record(u,('password',))
@app.get('/api/auth/me')
def me(u=Depends(user)): return record(u,('password',))

class AccountUpdate(Strict):
    username:str=Field(min_length=3,max_length=80)
    current_password:SecretStr=Field(min_length=1,max_length=200)
    new_password:SecretStr|None=Field(default=None,min_length=12,max_length=200)
    confirm_new_password:SecretStr|None=Field(default=None,max_length=200)

@app.patch('/api/auth/account')
def update_account(body:AccountUpdate,request:Request,response:Response,u=Depends(user),db=Depends(db_session)):
    attempt_key=('account',u.id,request.client.host)
    attempts=[t for t in login_attempts.get(attempt_key,[]) if t>time.time()-300]
    if len(attempts)>=8:raise HTTPException(429,'Too many account verification attempts. Try again in five minutes.')
    # Serialize changes so a second request must verify the current credential.
    db.connection().exec_driver_sql('BEGIN IMMEDIATE');db.refresh(u)
    token_hash=hashlib.sha256(request.cookies.get('talentiq_session','').encode()).hexdigest()
    if not db.query(Login).filter_by(user_id=u.id,token_hash=token_hash).first():raise HTTPException(401,'Session expired.')
    if not password_valid(body.current_password.get_secret_value(),u.password):
        login_attempts[attempt_key]=attempts+[time.time()]
        raise ValueError('Current password is incorrect.')
    username=body.username.strip().casefold()
    if not 3<=len(username)<=80 or any(c.isspace() or not c.isprintable() for c in username):raise ValueError('Use a username of 3–80 characters without spaces.')
    new_password=body.new_password.get_secret_value() if body.new_password else None
    confirmation=body.confirm_new_password.get_secret_value() if body.confirm_new_password else None
    if new_password!=confirmation:raise ValueError('The new passwords do not match.')
    if username==u.username and not new_password:raise ValueError('Choose a new username or password.')
    if db.query(User).filter(User.username==username,User.id!=u.id).first():raise HTTPException(409,'Username already exists.')
    changed_username=username!=u.username
    u.username=username
    if new_password:u.password=password_hash(new_password)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Username already exists.') from None
    db.query(Login).filter_by(user_id=u.id).delete(synchronize_session=False)
    audit(db,u.name,'Account sign-in updated',u.id,username_changed=changed_username,password_changed=bool(new_password))
    set_login(db,u,response)
    login_attempts.pop(attempt_key,None)
    return record(u,('password',))

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,u=Depends(user),db=Depends(db_session)):
    db.query(Login).filter_by(token_hash=hashlib.sha256(request.cookies.get('talentiq_session','').encode()).hexdigest()).delete(); db.commit(); response.delete_cookie('talentiq_session'); return {'ok':True}
@app.get('/api/users')
def users(u=Depends(admin),db=Depends(db_session)): return [record(x,('password',)) for x in db.query(User).all()]
@app.post('/api/users')
def create_user(body:NewUser,u=Depends(admin),db=Depends(db_session)):
    if body.role not in ('admin','reviewer','viewer') or len(body.password)<12: raise ValueError('Choose a valid role and a password of at least 12 characters.')
    if db.query(User).filter_by(username=body.username.casefold()).first(): raise ValueError('Username already exists.')
    row=User(name=body.name,username=body.username.casefold(),password=password_hash(body.password),role=body.role); db.add(row); audit(db,u.name,'Local user created',body.username,role=body.role); db.commit(); return record(row,('password',))

@app.get('/api/profiles')
def profiles(u=Depends(user),db=Depends(db_session)): return [record(p) for p in db.query(Profile).order_by(Profile.created_at.desc()).all()]
@app.post('/api/profiles')
def create_profile(body:ProfileInput,u=Depends(writer),db=Depends(db_session)):
    p=Profile(name=body.name,config=body.model_dump()); db.add(p); db.flush()
    db.add(ProfileVersion(profile_id=p.id,version=1,config=body.model_dump())); audit(db,u.name,'Profile created',p.name); db.commit(); return record(p)
@app.put('/api/profiles/{pid}')
def update_profile(pid:str,body:ProfileInput,u=Depends(writer),db=Depends(db_session)):
    assert_idle(); p=require(db,Profile,pid); p.version+=1; p.name=body.name; p.config=body.model_dump()
    db.add(ProfileVersion(profile_id=p.id,version=p.version,config=p.config)); audit(db,u.name,'Profile version saved',p.name,version=p.version); db.commit(); return record(p)
@app.get('/api/profiles/{pid}/versions')
def versions(pid:str,u=Depends(user),db=Depends(db_session)):
    require(db,Profile,pid); return [record(p) for p in db.query(ProfileVersion).filter_by(profile_id=pid).order_by(ProfileVersion.version.desc()).all()]
@app.post('/api/profiles/{pid}/duplicate')
def duplicate_profile(pid:str,u=Depends(writer),db=Depends(db_session)):
    p=require(db,Profile,pid); config={**p.config,'name':p.name+' (copy)'}
    return create_profile(ProfileInput.model_validate(config),u,db)
@app.post('/api/profiles/{pid}/archive')
def archive_profile(pid:str,u=Depends(writer),db=Depends(db_session)):
    p=require(db,Profile,pid); p.archived=not p.archived; audit(db,u.name,'Profile archive toggled',p.name); db.commit(); return record(p)
@app.delete('/api/profiles/{pid}')
def delete_profile(pid:str,u=Depends(writer),db=Depends(db_session)):
    p=require(db,Profile,pid)
    if db.query(Project).filter_by(profile_id=pid).count() or db.query(Evaluation).filter_by(profile_id=pid).count(): raise ValueError('This profile is referenced by a project or evaluation. Archive it to retain history.')
    audit(db,u.name,'Profile deleted',p.name); db.delete(p); db.commit(); return {'ok':True}
class Description(Strict): description:str=Field(min_length=20,max_length=12000)
@app.post('/api/profile-suggestions')
async def profile_suggestions(body:Description,u=Depends(writer)):
    if ollama.gate.locked(): raise HTTPException(409,'AI engine is busy.')
    async with ollama.gate:
        raw=await ollama.chat(active_model(),[{'role':'system','content':SYSTEM+response_instruction(ui_language.get())+' Propose a draft recruitment profile. The HR reviewer must approve it. Criteria weights must total 100.'},{'role':'user','content':body.description}],ProfileInput.model_json_schema())
        return ProfileInput.model_validate_json(raw).model_dump()

class ProjectInput(Strict):
    name:str=Field(min_length=2,max_length=160)
    profile_id:str
    department:str=Field(default='',max_length=100)
@app.get('/api/projects')
def projects(u=Depends(user),db=Depends(db_session)):
    results=[]
    for p in db.query(Project).order_by(Project.created_at.desc()).all():
        count=db.query(Candidate).filter_by(project_id=p.id).count()
        evaluated=db.query(Candidate).filter(Candidate.project_id==p.id,Candidate.id.in_(select(Evaluation.candidate_id))).count()
        job=db.query(Job).filter_by(project_id=p.id).order_by(Job.created_at.desc()).first()
        results.append({**record(p),'candidate_count':count,'evaluated':evaluated,'profile_name':db.get(Profile,p.profile_id).name,'job_state':job.state if job else None})
    return results
@app.post('/api/projects')
def create_project(body:ProjectInput,u=Depends(writer),db=Depends(db_session)):
    p=require(db,Profile,body.profile_id)
    if p.archived: raise ValueError('Choose an active profile.')
    project=Project(**body.model_dump()); db.add(project); db.flush(); audit(db,u.name,'Project created',project.name,project.id); db.commit(); return record(project)
@app.put('/api/projects/{pid}')
def edit_project(pid:str,body:ProjectInput,u=Depends(writer),db=Depends(db_session)):
    assert_idle(); p=require(db,Project,pid); require(db,Profile,body.profile_id)
    p.name=body.name; p.profile_id=body.profile_id; p.department=body.department; audit(db,u.name,'Project updated',p.name,pid); db.commit(); return record(p)
@app.post('/api/projects/{pid}/archive')
def archive_project(pid:str,u=Depends(writer),db=Depends(db_session)):
    assert_idle(); p=require(db,Project,pid); p.archived=not p.archived; audit(db,u.name,'Project archive toggled',p.name,pid); db.commit(); return record(p)

def candidate_record(db,c):
    e=db.query(Evaluation).filter_by(candidate_id=c.id).order_by(Evaluation.created_at.desc()).first()
    p=db.get(Project,c.project_id); profile=db.get(Profile,p.profile_id)
    docs=db.query(Document).filter_by(candidate_id=c.id).all()
    current_config=analysis_config(profile.config,profile.id)
    if e and e.profile_snapshot.get('_interface_language') in ('fa','en'):
        current_config.update(language=e.profile_snapshot['language'],_interface_language=e.profile_snapshot['_interface_language'])
    stale=bool(e and (e.profile_id!=profile.id or e.profile_version!=profile.version or e.model!=current_config['model'] or e.profile_snapshot.get('_provider','local')!=settings()['provider']))
    if e and current_config.get('depth') in ('Fast','Balanced'):
        if current_config.get('depth')=='Balanced':
            from .balanced import fingerprint
        else:
            from .fast import fingerprint
        stale=stale or e.result.get('input_hash')!=fingerprint(current_config,current_config['model'],docs)
    from .understanding import source_fingerprint,VERSION as BRIEF_VERSION
    brief=(c.details or {}).get('cv_brief') or {}
    if not (brief.get('checked') and brief.get('version')==BRIEF_VERSION and brief.get('source_fingerprint')==source_fingerprint(docs)):brief=None
    return {**record(c),'cv_brief':brief,'score':e.score if e else None,'coverage':e.coverage if e else 0,'evaluation':record(e) if e else None,'stale':stale,'documents':[record(d,('storage_name','pages')) for d in docs]}
@app.get('/api/candidates')
def candidates(project_id:str|None=None,q:str='',u=Depends(user),db=Depends(db_session)):
    query=db.query(Candidate)
    if project_id: require(db,Project,project_id); query=query.filter_by(project_id=project_id)
    if q: query=query.filter(Candidate.name.contains(q[:200],autoescape=True))
    return rank([candidate_record(db,c) for c in query.all()])
@app.get('/api/candidates/{cid}')
def candidate(cid:str,u=Depends(user),db=Depends(db_session)): return candidate_record(db,require(db,Candidate,cid))
class ReviewInput(Strict):
    name:str|None=Field(default=None,min_length=1,max_length=160)
    status:str|None=None
    shortlisted:bool|None=None
    reviewer:str|None=Field(default=None,max_length=100)
    interview_date:str|None=Field(default=None,max_length=40)
    note:str|None=Field(default=None,max_length=5000)
    confirm_decision:bool=False
@app.patch('/api/candidates/{cid}')
def review(cid:str,body:ReviewInput,u=Depends(writer),db=Depends(db_session)):
    c=require(db,Candidate,cid)
    if body.status and body.status not in STAGES: raise ValueError('Unknown pipeline status.')
    if body.status in ('Hired','Not Selected') and (not body.confirm_decision or not (body.note or '').strip()): raise ValueError('Final decisions require explicit confirmation and a reviewer note.')
    for field in ('name','status','reviewer','interview_date'):
        if getattr(body,field) is not None: setattr(c,field,getattr(body,field))
    if body.shortlisted is not None: c.shortlisted=int(body.shortlisted)
    if body.note: c.notes=[*c.notes,{'id':uid(),'author':u.name,'text':body.note,'created_at':now()}]
    audit(db,u.name,'Human review updated',c.name,c.project_id,changes={k:v for k,v in body.model_dump(exclude_none=True).items() if k not in ('note','confirm_decision')},note_added=bool(body.note)); db.commit(); return candidate_record(db,c)
def purge_candidate(db,c):
    paths=[d.storage_name for d in db.query(Document).filter_by(candidate_id=c.id).all()]
    db.delete(c); db.flush()
    for path in paths:
        if not db.query(Document).filter_by(storage_name=path).first(): (DATA/'documents'/path).unlink(missing_ok=True)
@app.delete('/api/candidates/{cid}')
def delete_candidate(cid:str,u=Depends(writer),db=Depends(db_session)):
    assert_idle(); c=require(db,Candidate,cid); audit(db,u.name,'Candidate and documents deleted',c.id,c.project_id); purge_candidate(db,c); db.commit(); return {'ok':True}
class Reuse(Strict): project_id:str
@app.post('/api/candidates/{cid}/reuse')
def reuse_candidate(cid:str,body:Reuse,u=Depends(writer),db=Depends(db_session)):
    source=require(db,Candidate,cid); target=require(db,Project,body.project_id)
    if source.project_id==target.id: raise ValueError('Select a different project.')
    c=Candidate(name=source.name,project_id=target.id); db.add(c); db.flush()
    for d in db.query(Document).filter_by(candidate_id=cid).all():
        db.add(Document(candidate_id=c.id,filename=d.filename,display_name=d.display_name,hash=d.hash,storage_name=d.storage_name,size=d.size,pages=d.pages,warnings=d.warnings))
    audit(db,u.name,'Candidate reused with human approval',c.name,target.id,source_project=source.project_id); db.commit(); return candidate_record(db,c)

class FolderInput(Strict):
    name:str=Field(min_length=1,max_length=100)
    parent_id:str|None=None
@app.get('/api/folders')
def folders(u=Depends(user),db=Depends(db_session)):
    return [{**record(f),'count':db.query(Document).filter_by(folder_id=f.id).count()} for f in db.query(Folder).all()]
@app.post('/api/folders')
def add_folder(body:FolderInput,u=Depends(writer),db=Depends(db_session)):
    if body.parent_id: require(db,Folder,body.parent_id)
    f=Folder(**body.model_dump()); db.add(f); audit(db,u.name,'Folder created',f.name); db.commit(); return record(f)
@app.put('/api/folders/{fid}')
def edit_folder(fid:str,body:FolderInput,u=Depends(writer),db=Depends(db_session)):
    f=require(db,Folder,fid); parent=body.parent_id
    seen={fid}
    while parent:
        if parent in seen: raise ValueError('Folders cannot contain themselves.')
        seen.add(parent); parent=require(db,Folder,parent).parent_id
    f.name=body.name; f.parent_id=body.parent_id; audit(db,u.name,'Folder updated',f.name); db.commit(); return record(f)
@app.delete('/api/folders/{fid}')
def remove_folder(fid:str,u=Depends(writer),db=Depends(db_session)):
    f=require(db,Folder,fid)
    if db.query(Folder).filter_by(parent_id=fid).count() or db.query(Document).filter_by(folder_id=fid).count(): raise ValueError('Move documents and child folders before deleting this folder.')
    db.delete(f); audit(db,u.name,'Empty folder deleted',f.name); db.commit(); return {'ok':True}

@app.post('/api/documents/import')
async def import_documents(project_id:str=Form(...),folder_id:str=Form(''),preserve_folders:bool=Form(False),files:list[UploadFile]=File(...),u=Depends(writer),db=Depends(db_session)):
    p=require(db,Project,project_id)
    if p.archived: raise ValueError('Unarchive the project before importing resumes.')
    if folder_id: require(db,Folder,folder_id)
    if len(files)>250: raise ValueError('Import up to 250 files per request; use additional batches for larger collections.')
    output=[]
    async def one(filename,content):
        name=safe_name(filename)
        if len(content)>MAX_FILE: return {'filename':name,'error':'File exceeds the 25 MB limit.'}
        digest=hashlib.sha256(content).hexdigest()
        existing=db.query(Document).join(Candidate).filter(Candidate.project_id==project_id,Document.hash==digest).first()
        if existing: return {'filename':name,'duplicate':True,'candidate_id':existing.candidate_id}
        try: pages,warnings=await asyncio.to_thread(extract,name,content)
        except Exception as e: return {'filename':name,'error':str(e)[:240] if isinstance(e,ValueError) else 'Document could not be parsed. Check that the original file opens correctly.'}
        # Extraction yields the event loop; another request may have committed the same file.
        existing=db.query(Document).join(Candidate).filter(Candidate.project_id==project_id,Document.hash==digest).first()
        if existing: return {'filename':name,'duplicate':True,'candidate_id':existing.candidate_id}
        target_folder=folder_id or None
        if preserve_folders:
            parts=filename.replace('\\','/').split('/')[:-1]
            if len(parts)>20 or any(part in ('','..','.') or ':' in part for part in parts): return {'filename':name,'error':'Unsafe directory path.'}
            for part in parts:
                f=db.query(Folder).filter_by(name=part[:100],parent_id=target_folder).first()
                if not f: f=Folder(name=part[:100],parent_id=target_folder); db.add(f); db.flush()
                target_folder=f.id
        storage=digest+Path(name).suffix.lower()
        (DATA/'documents'/storage).write_bytes(content)
        c=Candidate(project_id=project_id,name=Path(name).stem.replace('_',' ').replace('-',' '),status='Pending Analysis'); db.add(c); db.flush()
        d=Document(candidate_id=c.id,folder_id=target_folder,filename=name,display_name=name,hash=digest,storage_name=storage,size=len(content),pages=pages,warnings=warnings); db.add(d)
        audit(db,u.name,'Resume imported',name,project_id,bytes=len(content),warnings=warnings); db.commit()
        similar=db.query(Candidate).filter(Candidate.project_id==project_id,Candidate.name==c.name,Candidate.id!=c.id).count()
        return {'filename':name,'candidate_id':c.id,'warnings':warnings+(['A candidate has the same display name. Verify manually; records were not merged.'] if similar else []),'status':'Imported'}
    for upload in files:
        data=await upload.read(MAX_FILE+1); filename=upload.filename or 'resume'
        if filename.lower().endswith('.zip'):
            try:
                if len(data)>MAX_FILE: raise ValueError('ZIP exceeds the 25 MB upload limit.')
                entries=await asyncio.to_thread(safe_zip,data)
                for entry,content in entries: output.append(await one(entry,content))
            except (ValueError,zipfile.BadZipFile) as e: output.append({'filename':safe_name(filename),'error':str(e)[:240]})
        else: output.append(await one(filename,data))
    return {'results':output}

@app.get('/api/documents')
def documents(project_id:str|None=None,u=Depends(user),db=Depends(db_session)):
    query=db.query(Document).join(Candidate)
    if project_id: require(db,Project,project_id); query=query.filter(Candidate.project_id==project_id)
    return [{**record(d,('storage_name','pages')),'candidate_name':db.get(Candidate,d.candidate_id).name,'project_id':db.get(Candidate,d.candidate_id).project_id} for d in query.all()]
@app.get('/api/documents/{did}/text')
def document_text(did:str,u=Depends(user),db=Depends(db_session)):
    d=require(db,Document,did); return {'pages':d.pages,'warnings':d.warnings,'filename':d.filename}
@app.get('/api/documents/{did}/original')
def original(did:str,download:bool=False,u=Depends(user),db=Depends(db_session)):
    d=require(db,Document,did); path=(DATA/'documents'/d.storage_name).resolve()
    if path.parent != (DATA/'documents').resolve() or not path.is_file(): raise HTTPException(404,'Original file is unavailable.')
    audit(db,u.name,'Original resume accessed',d.id,db.get(Candidate,d.candidate_id).project_id); db.commit()
    mime='application/pdf' if d.filename.lower().endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return FileResponse(path,media_type=mime,filename=d.filename,content_disposition_type='attachment' if download or mime!='application/pdf' else 'inline')
@app.delete('/api/documents/{did}')
def delete_document(did:str,u=Depends(writer),db=Depends(db_session)):
    assert_idle(); d=require(db,Document,did); c=require(db,Candidate,d.candidate_id)
    storage=d.storage_name; filename=d.display_name or d.filename
    db.delete(d); db.query(Evaluation).filter_by(candidate_id=c.id).delete(synchronize_session=False)
    c.details={k:v for k,v in (c.details or {}).items() if k not in ('facts','cv_brief')}
    db.flush()
    if not db.query(Document).filter_by(storage_name=storage).first():
        path=(DATA/'documents'/storage).resolve()
        if path.parent==(DATA/'documents').resolve(): path.unlink(missing_ok=True)
    audit(db,u.name,'Resume deleted',filename,c.project_id,document_id=did,candidate_id=c.id);db.commit();return {'deleted':did}

class DocumentUpdate(Strict):
    ids:list[str]=Field(min_length=1,max_length=1000)
    folder_id:str|None=None
    display_name:str|None=Field(default=None,min_length=1,max_length=240)
@app.patch('/api/documents')
def move_documents(body:DocumentUpdate,u=Depends(writer),db=Depends(db_session)):
    if body.folder_id: require(db,Folder,body.folder_id)
    for id in body.ids:
        d=require(db,Document,id)
        if body.display_name is not None: d.display_name=body.display_name
        else: d.folder_id=body.folder_id
    audit(db,u.name,'Documents organized',str(len(body.ids))); db.commit(); return {'ok':True}

@app.get('/api/ai/status')
async def ai_status(u=Depends(user)): return await ollama.status()
@app.post('/api/ai/start')
async def ai_start(u=Depends(writer),db=Depends(db_session)):
    if ollama.gate.locked(): raise HTTPException(409,'AI engine is busy.')
    try: await ollama.warm()
    except Exception as e: raise HTTPException(503,str(e)[:300])
    audit(db,u.name,'QwenCloud connection checked' if settings()['provider']=='qwencloud' else 'AI model warmed',active_model()); db.commit(); return await ollama.status()
@app.post('/api/ai/shutdown')
async def ai_shutdown(u=Depends(writer),db=Depends(db_session)):
    await jobs.settle_all()
    for task in list(chat_tasks): task.cancel()
    if chat_tasks: await asyncio.gather(*list(chat_tasks),return_exceptions=True)
    if ollama.pull_task and not ollama.pull_task.done(): ollama.pull_task.cancel(); await asyncio.gather(ollama.pull_task,return_exceptions=True)
    try: result=await ollama.shutdown()
    except Exception as e: ollama.state='error'; raise HTTPException(503,'Shutdown could not be verified: '+str(e)[:200])
    audit(db,u.name,'AI shutdown requested',info=result); db.commit(); return result
class PullInput(Strict): model:str; confirm_download:bool=False
@app.post('/api/ai/pull')
async def pull_model(body:PullInput,u=Depends(admin)):
    if settings()['provider']!='local':raise ValueError('Choose Local AI before downloading local models.')
    if not body.confirm_download: raise ValueError('Explicitly confirm the model download; model files may require several gigabytes.')
    model_name(body.model)
    if ollama.gate.locked() or (ollama.pull_task and not ollama.pull_task.done()): raise HTTPException(409,'AI engine is busy.')
    ollama.pull_state={'model':body.model,'status':'starting'}; ollama.pull_task=asyncio.create_task(ollama.pull(body.model)); return ollama.pull_state

class JobInput(Strict):
    project_id:str
    candidate_ids:list[str]|None=None
    reevaluate:bool=False
@app.get('/api/jobs')
def list_jobs(project_id:str|None=None,u=Depends(user),db=Depends(db_session)):
    query=db.query(Job)
    if project_id: require(db,Project,project_id); query=query.filter_by(project_id=project_id)
    return [record(j) for j in query.order_by(Job.created_at.desc()).limit(100).all()]
@app.post('/api/jobs')
async def start_job(body:JobInput,u=Depends(writer),db=Depends(db_session)):
    if jobs.active() or ollama.gate.locked(): raise HTTPException(409,'One inference operation runs at a time. Pause or stop it first.')
    p=require(db,Project,body.project_id)
    if p.archived: raise ValueError('Unarchive this project before analysis.')
    profile=require(db,Profile,p.profile_id)
    snapshot=analysis_config(profile.config,profile.id,language=ui_language.get())
    state=await ollama.status()
    if snapshot['model'] not in state['models']: raise HTTPException(503,'The selected AI provider or analysis model is not configured. Open AI Workspace.')
    candidates=db.query(Candidate).filter_by(project_id=p.id).all()
    if body.candidate_ids is not None:
        allowed={c.id for c in candidates}
        if not set(body.candidate_ids)<=allowed: raise ValueError('Candidate selection does not belong to this project.')
        candidates=[c for c in candidates if c.id in body.candidate_ids]
    items=[]
    for c in candidates:
        previous=db.query(Evaluation).filter_by(candidate_id=c.id,profile_id=profile.id,profile_version=profile.version,model=snapshot['model']).order_by(Evaluation.created_at.desc()).first()
        if previous and snapshot.get('depth') in ('Fast','Balanced'):
            if snapshot.get('depth')=='Balanced':
                from .balanced import fingerprint
            else:
                from .fast import fingerprint
            docs=db.scalars(select(Document).where(Document.candidate_id==c.id)).all()
            if previous.result.get('input_hash')!=fingerprint(snapshot,snapshot['model'],docs):previous=None
        if body.reevaluate or not previous: items.append({'candidate_id':c.id,'name':c.name,'state':'pending','error':None})
    if not items: raise ValueError('No unevaluated candidates. Import resumes or explicitly re-evaluate a candidate.')
    j=Job(project_id=p.id,profile_snapshot=snapshot,profile_version=profile.version,model=snapshot['model'],items=items)
    db.add(j); db.flush(); audit(db,u.name,'Analysis started',p.name,p.id,count=len(items)); jobs.launch(j.id); db.commit(); return record(j)
@app.post('/api/jobs/{jid}/{action}')
async def control_job(jid:str,action:str,u=Depends(writer),db=Depends(db_session)):
    j=require(db,Job,jid); await jobs.control(jid,action); audit(db,u.name,'Analysis '+action,jid,j.project_id); db.commit()
    db.refresh(j); return record(j)
@app.get('/api/events')
async def events(request:Request,u=Depends(user)):
    async def stream():
        last=None
        while not await request.is_disconnected():
            with Session() as db:
                state={'jobs':[record(j) for j in db.query(Job).order_by(Job.created_at.desc()).limit(20).all()],'engine_state':ollama.state,'pull':ollama.pull_state,'revision':db.query(func.count(Audit.id)).scalar()}
            payload=json.dumps(state)
            if payload!=last: yield 'data: '+payload+'\n\n'; last=payload
            else: yield 'event: heartbeat\ndata: {}\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no','Cache-Control':'no-cache'})

def cosine(a,b):
    if len(a)!=len(b): return 0
    denom=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denom if denom else 0
async def retrieve(db,pid,query,candidate_id=None):
    require(db,Project,pid)
    candidates=db.query(Candidate).filter_by(project_id=pid).all()
    if candidate_id:
        c=require(db,Candidate,candidate_id)
        if c.project_id!=pid: raise ValueError('Candidate is outside the selected project.')
        candidates=[c]
    ids=[c.id for c in candidates]; names={c.id:c.name for c in candidates}
    embs=db.query(Embedding).filter(Embedding.candidate_id.in_(ids),Embedding.model==active_embedding_model()).all()
    results=[]; mode='keyword'
    if embs:
        try:
            vector=(await ollama.embed([query]))[0]
            results=[{'candidate_id':e.candidate_id,'candidate':names[e.candidate_id],'document_id':e.document_id,'page':e.page,'text':e.passage[:2500],'relevance':cosine(vector,e.vector)} for e in embs]; mode='semantic'
        except Exception: pass
    if not results:
        terms=set(query.casefold().split())
        for doc in db.query(Document).filter(Document.candidate_id.in_(ids)).all():
            for part in chunks([doc],2500):
                relevance=sum(part['text'].casefold().count(t) for t in terms if len(t)>2)
                results.append({'candidate_id':doc.candidate_id,'candidate':names[doc.candidate_id],'document_id':doc.id,'page':part['page'],'text':part['text'],'relevance':relevance})
    return sorted(results,key=lambda x:(-x['relevance'],x['candidate_id']))[:8],mode
class SearchInput(Strict):
    project_id:str
    query:str=Field(min_length=1,max_length=2000)
    candidate_id:str|None=None
@app.post('/api/search')
async def talent_search(body:SearchInput,u=Depends(user),db=Depends(db_session)):
    if PROTECTED.search(body.query): raise ValueError('Search by job-related skills, qualifications, or experience.')
    if ollama.gate.locked(): raise HTTPException(409,'AI engine is busy; wait for the current operation.')
    async with ollama.gate: sources,mode=await retrieve(db,body.project_id,body.query,body.candidate_id)
    return {'results':sources,'mode':mode}
class ChatInput(SearchInput):
    candidate_ids:list[str]|None=Field(default=None,max_length=6)
    language:Literal['en','fa']|None=None
    instructions:str=Field(default=ANSWER_INSTRUCTIONS,max_length=2000)

@app.get('/api/chat/playbook')
def hr_playbook(u=Depends(user)):
    return playbook()

@app.post('/api/translations')
async def translated_research(body:TranslationInput,u=Depends(user)):
    return {'translations':await translate_texts(body)}

@app.get('/api/chat')
def chat_history(project_id:str,candidate_id:str|None=None,candidate_ids:str='',u=Depends(user),db=Depends(db_session)):
    require(db,Project,project_id)
    requested=set(filter(None,candidate_ids.split(',')))|({candidate_id} if candidate_id else set())
    for cid in requested:
        if require(db,Candidate,cid).project_id!=project_id:raise ValueError('Candidate is outside the selected project.')
    result=[]
    from .memory import VERSION
    for m in db.query(Message).filter_by(project_id=project_id,user_id=u.id).order_by(Message.created_at).all():
        scope=set(m.sources[0].get('scope_candidate_ids',[])) if m.sources else set()
        if scope!=requested:continue
        result.append({**record(m),'legacy':m.role=='assistant' and not any(x.get('context_version')==VERSION for x in m.sources)})
    return result

@app.delete('/api/chat')
def clear_chat(project_id:str,u=Depends(writer),db=Depends(db_session)):
    require(db,Project,project_id); db.query(Message).filter_by(project_id=project_id,user_id=u.id).delete(); db.commit(); return {'ok':True}

@app.post('/api/chat')
async def chat(body:ChatInput,request:Request,u=Depends(writer),db=Depends(db_session)):
    from .memory import candidate_memory,select_scope,assemble,chat_messages,VERSION,CHAT_SYSTEM
    project=require(db,Project,body.project_id)
    if PROTECTED.search(body.query):raise ValueError('Ask about documented job qualifications; protected attributes cannot be used for assessment.')
    if ollama.gate.locked():raise HTTPException(409,'AI engine is busy. Pause analysis or wait for it to finish.')
    rows=db.query(Candidate).filter_by(project_id=body.project_id).all()
    memories=[candidate_memory(c,db.query(Document).filter_by(candidate_id=c.id).order_by(Document.created_at).all()) for c in rows]
    explicit=list(dict.fromkeys(([body.candidate_id] if body.candidate_id else [])+(body.candidate_ids or [])))
    if len(explicit)>6:raise ValueError('Select up to six candidates for one conversation.')
    for cid in explicit:
        if require(db,Candidate,cid).project_id!=body.project_id:raise ValueError('Candidate is outside the selected project.')
    prior_rows=db.query(Message).filter_by(project_id=body.project_id,user_id=u.id).order_by(Message.created_at.desc()).limit(30).all()[::-1]
    prior_rows=[m for m in prior_rows if (set(m.sources[0].get('scope_candidate_ids',[])) if m.sources else set())==set(explicit)][-10:]
    selected,ambiguous=select_scope(body.query,memories,explicit,[m.content for m in prior_rows if m.role=='user'])
    profile=require(db,Profile,project.profile_id)
    role_context={k:profile.config.get(k,'') for k in ('job_title','description','seniority','instructions','language','employment','arrangement','location')}
    language=body.language or ui_language.get()
    if language:role_context['language']='Persian' if language=='fa' else 'English'
    role_context['criteria']=[{k:c.get(k,'') for k in ('name','instructions')} for c in profile.config['criteria'] if c['enabled']]
    role_context['requirements']=[{k:r.get(k,'') for k in ('description','expected_value','classification')} for r in profile.config['requirements']]
    config={**settings(),'model':active_model(),'context_length':context_budget()}
    text=body.query+''.join(p['text'] for m in memories if m['id'] in selected for d in m['documents'] for p in d.pages)
    factor=1.2 if sum(ord(c)>127 for c in text)/max(1,len(text))>.1 else 2.7
    reserve=8192 if config['provider']=='qwencloud' else 4096
    max_chars=int((config['context_length']-reserve)*factor)-len(body.query)-len(body.instructions)-len(CHAT_SYSTEM)-len(json.dumps(role_context,ensure_ascii=False))-6500
    sources,facts,coverage=assemble(memories,selected,body.query,max_chars) if selected and not ambiguous else ([],[],{'mode':'clarification','complete':False,'candidate_ids':selected})
    sources=[{**source,'scope_candidate_ids':explicit,'evidence_candidate_ids':selected,'chat_model':config['model'],'ai_provider':config['provider'],'answer_language':language or profile.config.get('language','English'),'coverage_complete':coverage.get('complete',False),'profile_id':profile.id,'profile_version':profile.version} for source in sources]
    history=[]
    current_hashes={d.id:d.hash for m in memories for d in m['documents']}
    for m in prior_rows:
        scope=set(m.sources[0].get('scope_candidate_ids',[])) if m.sources else set()
        if scope!=set(explicit):continue
        if m.role=='assistant' and m.sources and set(m.sources[0].get('evidence_candidate_ids',[]))!=set(selected):continue
        if m.role=='assistant' and m.sources and m.sources[0].get('ai_provider','local')!=config['provider']:continue
        if m.role=='assistant' and m.sources and (m.sources[0].get('profile_id')!=profile.id or m.sources[0].get('profile_version')!=profile.version):continue
        if m.role=='assistant' and not (m.sources and all(x.get('context_version')==VERSION and current_hashes.get(x.get('document_id'))==x.get('content_hash') for x in m.sources)):continue
        history.append({'role':m.role,'content':m.content[:2000]})
    messages=chat_messages(sources,facts,coverage,body.query,history[-4:],role_context,body.instructions,language)
    budget=(config['context_length']-reserve)*factor
    while len(json.dumps(messages,ensure_ascii=False))>budget:
        if history:history.pop(0)
        else:raise ValueError('Selected CV evidence exceeds the context budget. Select fewer candidates or narrow the question.')
        messages=chat_messages(sources,facts,coverage,body.query,history[-4:],role_context,body.instructions,language)
    user_id=u.id
    db.add(Message(project_id=body.project_id,user_id=user_id,role='user',content=body.query,sources=[{'scope_candidate_ids':explicit,'evidence_candidate_ids':selected,'context_version':VERSION}]))
    db.commit()
    async def generate():
        task=asyncio.current_task();chat_tasks.add(task);output='';completed=False;started=time.monotonic()
        try:
            async with ollama.gate:
                if settings()['provider']!=config['provider'] or active_model()!=config['model']:raise ValueError('The AI provider changed before this request began. Retry with the selected provider.')
                ollama.state='processing'
                yield json.dumps({'sources':sources,'retrieval':coverage['mode'],'coverage':coverage,'model':config['model'],'provider':config['provider'],'status':'Reading complete selected CVs' if coverage.get('complete') else 'Reading focused CV excerpts'})+'\n'
                if ambiguous or not selected:
                    output='Which candidate do you mean? Please name the candidate or select the CVs to compare.'
                    yield json.dumps({'token':output})+'\n'
                elif not sources:
                    output='No readable CV text is available for that selection. Import a searchable resume first.'
                    yield json.dumps({'token':output})+'\n'
                else:
                    from .understanding import checked_answer
                    draft=''
                    async for token in ollama.stream(messages):
                        if await request.is_disconnected():break
                        draft+=token
                    if await request.is_disconnected():return
                    if ollama.last_generation and ollama.last_generation.get('done_reason')=='length':raise ValueError('The draft reached its response limit. Narrow the question and retry.')
                    yield json.dumps({'status':'Checking the answer against the CV sources','checking':True})+'\n'
                    checked=await checked_answer(ollama,config['model'],messages,draft,sources)
                    if await request.is_disconnected():return
                    output=checked['answer']
                    sources[:]=[{**source,'answer_checked':True,'answer_check_version':checked['version']} for source in sources]
                    yield json.dumps({'sources':sources,'token':output,'checked':True})+'\n'
                completed=not await request.is_disconnected()
        except asyncio.CancelledError:pass
        except Exception as e:
            yield json.dumps({'error':str(e)[:250] if isinstance(e,ValueError) else 'AI generation failed. Verify the selected provider and model, then retry.'})+'\n'
        finally:
            if output:
                with Session() as db2:
                    if db2.get(Project,body.project_id):
                        saved_sources=[{**source,'answer_seconds':round(time.monotonic()-started,3)} for source in sources]
                        db2.add(Message(project_id=body.project_id,user_id=user_id,role='assistant',content=output+('' if completed else '\n[Generation interrupted; verify incomplete answer.]'),sources=saved_sources));db2.commit()
            ollama.state='stopped';chat_tasks.discard(task)
        if completed:yield json.dumps({'done':True,'seconds':round(time.monotonic()-started,3),'generation':ollama.last_generation})+'\n'
    return StreamingResponse(generate(),media_type='application/x-ndjson',headers={'X-Accel-Buffering':'no','Cache-Control':'no-store, no-transform'})

class ComparisonInput(Strict):
    project_id:str
    name:str=Field(min_length=1,max_length=120)
    candidate_ids:list[str]=Field(min_length=2,max_length=6)
@app.get('/api/comparisons')
def comparisons(project_id:str,u=Depends(user),db=Depends(db_session)):
    require(db,Project,project_id); return [record(c) for c in db.query(Comparison).filter_by(project_id=project_id).all()]
@app.post('/api/comparisons')
def save_comparison(body:ComparisonInput,u=Depends(writer),db=Depends(db_session)):
    require(db,Project,body.project_id)
    if len(set(body.candidate_ids))!=len(body.candidate_ids): raise ValueError('Choose different candidates.')
    for cid in body.candidate_ids:
        if require(db,Candidate,cid).project_id!=body.project_id: raise ValueError('All candidates must belong to the selected project.')
    c=Comparison(**body.model_dump()); db.add(c); audit(db,u.name,'Comparison saved',c.name,body.project_id); db.commit(); return record(c)
@app.get('/api/audit')
def history(project_id:str|None=None,u=Depends(user),db=Depends(db_session)):
    query=db.query(Audit)
    if project_id: require(db,Project,project_id); query=query.filter_by(project_id=project_id)
    return [record(a) for a in query.order_by(Audit.created_at.desc()).limit(500).all()]
@app.get('/api/analytics')
def analytics(project_id:str|None=None,u=Depends(user),db=Depends(db_session)):
    query=db.query(Candidate)
    if project_id: require(db,Project,project_id); query=query.filter_by(project_id=project_id)
    cs=query.all(); ids=[c.id for c in cs]
    evaluations=[db.query(Evaluation).filter_by(candidate_id=c.id).order_by(Evaluation.created_at.desc()).first() for c in cs]; es=[e for e in evaluations if e]
    gaps={}; skills={}
    for e in es:
        for a in e.result['assessments']:
            if a['status']!='Supported': gaps[a['name']]=gaps.get(a['name'],0)+1
        for f in e.result['facts']:
            if f['kind']=='Skill': skills[f['value']]=skills.get(f['value'],0)+1
    js=db.query(Job).filter(Job.project_id==project_id).all() if project_id else db.query(Job).all()
    return {'candidates':len(cs),'evaluated':len(es),'shortlisted':sum(c.shortlisted for c in cs),'needs_review':sum(c.status in ('Needs Review','Under HR Review') for c in cs),'projects':db.query(Project).filter_by(archived=0).count(),'pipeline':{s:sum(c.status==s for c in cs) for s in STAGES},'gaps':gaps,'skills':dict(sorted(skills.items(),key=lambda x:-x[1])[:15]),'average_seconds':round(sum(e.duration for e in es)/len(es),1) if es else None,'failures':sum(i['state']=='failed' for j in js for i in j.items),'score_distribution':{label:sum(e.score is not None and lo<=e.score<=hi for e in es) for label,lo,hi in [('0–24',0,24.99),('25–49',25,49.99),('50–74',50,74.99),('75–100',75,100)]}}

def safe_settings():
    from .credentials import key_source
    return {**settings(),'key_configured':key_source()!='not configured','key_source':key_source()}

@app.get('/api/settings')
def get_settings(u=Depends(admin)):return safe_settings()

class SettingsInput(Strict):
    provider:Literal['unconfigured','local','qwencloud']='local'
    ollama_url:str
    model:str
    embedding_model:str
    context_length:int=Field(ge=4096,le=32768)
    timeout:int=Field(ge=30,le=3600)
    temperature:float=Field(ge=0,le=0.5)
    keep_alive:str
    retention_days:int=Field(ge=1,le=3650)
    cloud_base_url:str=DEFAULTS['cloud_base_url']
    cloud_model:str=DEFAULTS['cloud_model']
    cloud_embedding_model:str=DEFAULTS['cloud_embedding_model']
    cloud_thinking:bool=True
    cloud_context_length:int=Field(default=32768,ge=16384,le=131072)
    api_key:SecretStr|None=Field(default=None,exclude=True)
    key_configured:bool=Field(default=False,exclude=True)
    key_source:str=Field(default='',exclude=True)

async def apply_settings(body,db,u):
    from .credentials import key_source,save_key
    from .qwencloud import cloud_url,cloud_model,cloud
    assert_idle()
    if ollama.gate.locked() or (ollama.pull_task and not ollama.pull_task.done()):raise HTTPException(409,'Wait for AI operations to finish before changing providers.')
    local_url(body.ollama_url);model_name(body.model);model_name(body.embedding_model)
    cloud_url(body.cloud_base_url);cloud_model(body.cloud_model);cloud_model(body.cloud_embedding_model)
    if body.keep_alive not in ('0','5m','10m','30m'):raise ValueError('Choose a supported memory duration.')
    key=body.api_key.get_secret_value() if body.api_key else ''
    if body.provider=='qwencloud' and not key and key_source()=='not configured':raise ValueError('Enter the QwenCloud API key or set DASHSCOPE_API_KEY on the server.')
    previous=settings()['provider']
    if previous=='local' and body.provider!='local':
        # Unload only models owned by this TalentIQ process. Never start Ollama
        # in order to switch away from it, or terminate unrelated applications.
        if ollama.owned_models:await ollama.shutdown()
    if key:save_key(key)
    value=body.model_dump()
    row=db.get(Setting,'app')
    if row:row.value=value
    else:db.add(Setting(id='app',value=value))
    audit(db,u.name,'AI provider settings updated',body.provider,model=body.cloud_model if body.provider=='qwencloud' else body.model)
    db.commit();cloud.checked=False;cloud.last_error=None;ollama.error=None;ollama.state='stopped' if body.provider=='local' else 'configured' if body.provider=='qwencloud' else 'unconfigured'
    if body.provider=='local' and previous!='local':
        try:await ollama.warm()
        except Exception as e:ollama.state='error';ollama.error=str(e)[:250]

@app.put('/api/settings')
async def update_settings(body:SettingsInput,u=Depends(admin),db=Depends(db_session)):
    await apply_settings(body,db,u);return safe_settings()

class ProviderInput(Strict):
    provider:Literal['local','qwencloud']
    api_key:SecretStr|None=None
    cloud_model:str|None=None
    cloud_thinking:bool|None=None

@app.put('/api/ai/provider')
async def choose_provider(body:ProviderInput,u=Depends(admin),db=Depends(db_session)):
    value={**settings(),**body.model_dump(exclude_none=True)}
    await apply_settings(SettingsInput.model_validate(value),db,u)
    return await ollama.status()

@app.get('/api/system')
def system(u=Depends(admin),db=Depends(db_session)):
    with engine.connect() as c:
        integrity=c.exec_driver_sql('PRAGMA quick_check').scalar(); migration=c.exec_driver_sql('SELECT MAX(version) FROM schema_migrations').scalar()
    return {'data_directory':str(DATA),'storage_bytes':sum(p.stat().st_size for p in DATA.rglob('*') if p.is_file()),'database':integrity,'migration':migration,'active_jobs':jobs.active(),'concurrency':1,'ocr':'External OCR preprocessing required; automatic OCR is not enabled.','formats':['PDF','DOCX','ZIP'],'file_limit_mb':25,'retention':'Manual administrator approval required before deleting expired candidates.'}
@app.get('/api/retention')
def retention(u=Depends(admin),db=Depends(db_session)):
    cutoff=(datetime.now(timezone.utc)-timedelta(days=settings()['retention_days'])).isoformat()
    return [{'id':c.id,'name':c.name,'created_at':c.created_at,'project_id':c.project_id} for c in db.query(Candidate).filter(Candidate.created_at<cutoff).all()]
class RetentionInput(Strict): ids:list[str]; confirm:bool=False
@app.post('/api/retention')
def purge_retention(body:RetentionInput,u=Depends(admin),db=Depends(db_session)):
    assert_idle()
    if not body.confirm: raise ValueError('Confirm permanent deletion.')
    eligible={c['id'] for c in retention(u,db)}
    if not set(body.ids)<=eligible: raise ValueError('Selection contains records that have not reached the retention limit.')
    for cid in body.ids: purge_candidate(db,require(db,Candidate,cid))
    audit(db,u.name,'Retention deletion approved',str(len(body.ids))); db.commit(); return {'deleted':len(body.ids)}

@app.get('/api/backup')
def backup(u=Depends(admin),db=Depends(db_session)):
    buffer=io.BytesIO(); snap=DATA/('backup-'+uid()+'.db')
    try:
        with closing(sqlite3.connect(str(DATA/'talentiq.db'))) as source, closing(sqlite3.connect(str(snap))) as target: source.backup(target)
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(snap,'talentiq.db'); z.writestr('manifest.json',json.dumps({'app':'TalentIQ','schema':1,'created_at':now()}))
            for path in (DATA/'documents').iterdir():
                if path.is_file(): z.write(path,'documents/'+path.name)
    finally: snap.unlink(missing_ok=True)
    audit(db,u.name,'Workspace backup downloaded'); db.commit(); buffer.seek(0)
    return StreamingResponse(buffer,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="talentiq-backup.zip"'})

@app.post('/api/restore')
async def restore(file:UploadFile=File(...),confirm:bool=Form(False),u=Depends(admin)):
    assert_idle()
    if ollama.gate.locked(): raise HTTPException(409,'Stop AI operations before restoring.')
    if not confirm: raise ValueError('Confirm replacement of this workspace with the backup.')
    data=await file.read(512*1024*1024+1)
    if len(data)>512*1024*1024: raise ValueError('Backup exceeds the 512 MB browser restore limit.')
    import re
    temp=DATA/('restore-'+uid()+'.db')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>2*1024**3: raise ValueError('Backup expansion exceeds safety limits.')
            if len(set(z.namelist()))!=len(z.namelist()): raise ValueError('Duplicate backup entries are not allowed.')
            if any(n not in ('manifest.json','talentiq.db') and not re.fullmatch(r'documents/[a-f0-9]{64}\.(pdf|docx)',n) for n in z.namelist()): raise ValueError('Backup contains unexpected paths.')
            manifest=json.loads(z.read('manifest.json'))
            if manifest.get('app')!='TalentIQ' or manifest.get('schema')!=1: raise ValueError('Backup schema is not supported.')
            temp.write_bytes(z.read('talentiq.db'))
            with closing(sqlite3.connect(str(temp))) as source:
                source.execute('PRAGMA trusted_schema=OFF')
                if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Backup database failed its integrity check.')
                if source.execute('PRAGMA foreign_key_check').fetchone(): raise ValueError('Backup has invalid record references.')
                if source.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]: raise ValueError('Unexpected executable database objects.')
                for table in Base.metadata.tables:
                    if not source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone(): raise ValueError('Backup is missing required tables.')
                for storage,digest in source.execute('SELECT storage_name, hash FROM documents'):
                    if not re.fullmatch(r'[a-f0-9]{64}\.(pdf|docx)',storage): raise ValueError('Invalid document storage path.')
                    content=z.read('documents/'+storage)
                    if hashlib.sha256(content).hexdigest()!=digest: raise ValueError('Backup document hash does not match.')
                # Validate all database-controlled paths before replacing live metadata.
                for storage,digest in source.execute('SELECT storage_name, hash FROM documents'):
                    (DATA/'documents'/storage).write_bytes(z.read('documents/'+storage))
                engine.dispose()
                with closing(sqlite3.connect(str(DATA/'talentiq.db'))) as target: source.backup(target)
        with Session() as db:
            db.query(Login).delete(); audit(db,'Administrator','Workspace restored from backup'); db.commit()
        migrate()
    except (zipfile.BadZipFile,KeyError,sqlite3.DatabaseError,json.JSONDecodeError): raise ValueError('Backup is invalid or incomplete.')
    finally: temp.unlink(missing_ok=True)
    return {'ok':True,'message':'Workspace restored. Sign in with an account from the backup.'}

def safe_cell(value):
    text=str(value if value is not None else '')
    return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
@app.get('/api/reports/{pid}')
def report(pid:str,format:str='csv',kind:str='rankings',candidate_ids:str='',u=Depends(user),db=Depends(db_session)):
    from xml.sax.saxutils import escape
    p=require(db,Project,pid); profile=db.get(Profile,p.profile_id)
    cs=rank([candidate_record(db,c) for c in db.query(Candidate).filter_by(project_id=pid).all()])
    if kind=='shortlist': cs=[c for c in cs if c['shortlisted']]
    if candidate_ids:
        ids=set(candidate_ids.split(',')); allowed={c['id'] for c in cs}
        if not ids<=allowed: raise ValueError('Report selection is outside this project.')
        cs=[c for c in cs if c['id'] in ids]
    audit(db,u.name,'Report exported',kind,pid,format=format); db.commit()
    title=f'TalentIQ · {p.name}'
    headers=['Candidate','Documented points','Evidence coverage %','Human review','Human shortlist','Model','Profile version','Evaluated at','Scoring version']
    rows=[]
    for c in cs:
        e=c['evaluation'] or {}
        rows.append([c['name'],c['score'],c['coverage'],c['status'],'Yes' if c['shortlisted'] else 'No',e.get('model',''),e.get('profile_version',''),e.get('created_at',''),e.get('scoring_version','')])
    if kind=='activity':
        headers=['Time','Actor','Action','Target']; rows=[[a.created_at,a.actor,a.action,a.target] for a in db.query(Audit).filter_by(project_id=pid).order_by(Audit.created_at).all()]
    if format=='csv':
        output=io.StringIO(); w=csv.writer(output); w.writerow([title]); w.writerow(['Recruitment profile',profile.name]); w.writerow(headers); w.writerows([[safe_cell(v) for v in r] for r in rows]); raw=output.getvalue().encode('utf-8-sig'); mime='text/csv'
    elif format=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb=Workbook(); ws=wb.active; ws.title='TalentIQ'; ws.append([title]); ws.append(['Recruitment profile',profile.name]); ws.append(headers)
        for row in rows: ws.append([safe_cell(v) for v in row])
        for cell in ws[3]: cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='303C6C')
        ws.freeze_panes='B4'
        for col in ws.columns: ws.column_dimensions[col[0].column_letter].width=min(55,max(18,max(len(str(c.value or '')) for c in col)+2))
        buffer=io.BytesIO(); wb.save(buffer); raw=buffer.getvalue(); mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format=='pdf':
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4, landscape
        buffer=io.BytesIO(); styles=getSampleStyleSheet(); doc=SimpleDocTemplate(buffer,pagesize=landscape(A4),rightMargin=35,leftMargin=35,topMargin=35,bottomMargin=35)
        story=[Paragraph(escape(title),styles['Title']),Paragraph(escape(f'{kind.title()} | {profile.name} | Generated {now()[:10]}'),styles['Normal']),Spacer(1,14),Paragraph('Human review required. Points reflect documented rubric coverage. Missing evidence is not a failed qualification. Scores are not final hiring decisions.',styles['Normal']),Spacer(1,14)]
        pdf_headers=headers if kind=='activity' else ['Candidate','Points','Coverage','Review','Shortlist','Model / profile version']
        pdf_rows=rows if kind=='activity' else [[r[0],r[1] if r[1] is not None else 'Unknown',r[2],r[3],r[4],f'{r[5]} / v{r[6]}'] for r in rows]
        table=Table([[Paragraph(escape(str(v or '')),styles['Normal']) for v in row] for row in [pdf_headers,*pdf_rows]],repeatRows=1,colWidths=[(landscape(A4)[0]-70)/len(pdf_headers)]*len(pdf_headers))
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E9EDF8')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),0.4,colors.HexColor('#DDE1EB')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)])); story.append(table)
        if kind in ('candidate','comparison','summary'):
            for c in cs:
                e=c['evaluation']
                story.extend([PageBreak(),Paragraph(escape(c['name']),styles['Heading1']),Paragraph(escape(c['status']),styles['Normal'])])
                if not e: story.append(Paragraph('No completed evaluation.',styles['Normal'])); continue
                story.append(Paragraph(escape(f"Model: {e['model']} | Profile v{e['profile_version']} | {e['created_at']} | {e['scoring_version']}"),styles['Normal']))
                for a in e['result']['assessments']:
                    story.extend([Spacer(1,12),Paragraph(escape(f"{a['name']} ({a['weight']}%) · {a['status']} · {a['score'] if a['score'] is not None else 'Unknown'}"),styles['Heading3']),Paragraph(escape(a['explanation']),styles['Normal'])])
                    for ev in a['evidence']: story.append(Paragraph(escape(f"Document {ev['document_id']} · page/section {ev['page']}: {ev['quote']}"),styles['Normal']))
        doc.build(story); raw=buffer.getvalue(); mime='application/pdf'
    else: raise ValueError('Choose PDF, Excel, or CSV.')
    return Response(raw,media_type=mime,headers={'Content-Disposition':f'attachment; filename="talentiq-{kind}.{format}"'})
