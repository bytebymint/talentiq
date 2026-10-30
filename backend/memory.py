"""Canonical CV context for chat. Original page text is the source of truth.

Ordinary CVs are read in full. Retrieval is a size fallback, never the default
for a selected candidate. Candidate ownership accompanies every page and fact.
"""
import hashlib
import json
import re
from datetime import datetime,timezone
from .documents import job_text
from .hr import CHAT_SYSTEM, ANSWER_INSTRUCTIONS

VERSION='cv-memory-v3'
GENERIC={'resume','cv','compressed','pdf','docx','candidate'}
SECTION=re.compile(r'^(?:profile|summary|experience|professional experience|work experience|work history|employment|education.*|technical.*skills|skills|projects.*|selected.*|microsoft applied skills|certifications.*|languages.*)$',re.I)
DATES=re.compile(r'\b(?:19|20)\d{2}\b.*(?:present|current|(?:19|20)\d{2})',re.I)

def normalized(text):return ' '.join(re.findall(r'\w+',text.translate(str.maketrans('يکك۰۱۲۳۴۵۶۷۸۹','یکک0123456789')).casefold()))

def cv_name(doc,fallback):
    for page in doc.pages[:1]:
        for line in page['text'].splitlines()[:4]:
            line=re.sub(r'(?i)^resume\s*\d*\s*[-:|]?\s*','',line).strip()
            words=line.split()
            if 2<=len(words)<=5 and len(line)<90 and not any(c.isdigit() for c in line) and not re.search(r'[@|:/]',line):return line
    return fallback

def employment(doc):
    rows=[];inside=False;previous=''
    for page in doc.pages:
        for raw in page['text'].splitlines():
            line=raw.strip()
            if not line:continue
            if SECTION.fullmatch(line):
                inside=bool(re.search(r'experience|employment|work history',line,re.I));previous='';continue
            if inside and '|' in line and DATES.search(line):
                parts=[p.strip() for p in line.split('|')]
                if len(parts)>=2:
                    inline_role=len(parts)>=3 and not re.search(r'\b(?:LLC|Ltd|Inc|Corporation|Group|Bank|Company)\b',parts[0],re.I) and bool(re.search(r'engineer|developer|specialist|executive|researcher|analyst|manager|consultant|designer|nurse|teacher|accountant|counsel|director|مهندس|کارشناس|مدیر|تحلیلگر|پرستار|طراح|مشاور',parts[0],re.I))
                    role=parts[0] if inline_role else previous
                    company=parts[1] if inline_role else parts[0]
                    date=next((p for p in parts if DATES.search(p)),'')
                    quote=line if inline_role or not role else role+'\n'+line
                    if len(quote)>=10:
                        rows.append({'role':role,'employer':company,'dates':date,'kind':'independent' if re.search(r'independent|freelance|personal work',role+' '+company,re.I) else 'organization','document_id':doc.id,'page':page['page'],'quote':quote})
            if not line.startswith(('-', '•')):previous=line
    return rows

def candidate_memory(candidate,docs):
    name=cv_name(docs[0],candidate.name) if docs else candidate.name
    aliases={normalized(name),normalized(candidate.name)}
    for d in docs:aliases.add(normalized(re.sub(r'(?i)\.(pdf|docx)$','',d.filename).replace('_',' ')))
    from .understanding import source_fingerprint,VERSION as BRIEF_VERSION
    reading=(getattr(candidate,'details',None) or {}).get('cv_brief') or {}
    if not (reading.get('checked') and reading.get('version')==BRIEF_VERSION and reading.get('source_fingerprint')==source_fingerprint(docs)):reading={}
    return {'cv_brief':reading,'id':candidate.id,'name':name,'record_name':candidate.name,'aliases':sorted(aliases),'employment':[r for d in docs for r in employment(d)],'documents':docs}

def mentioned_candidates(query,memories):
    q=' '+normalized(query)+' ';found=[]
    frequencies={}
    for m in memories:
        for token in set(normalized(m['name']).split())-GENERIC:frequencies[token]=frequencies.get(token,0)+1
    for m in memories:
        full=any(alias and ' '+alias+' ' in q for alias in m['aliases'])
        unique=any(len(t)>=2 and frequencies.get(t)==1 and ' '+t+' ' in q for t in normalized(m['name']).split() if t not in GENERIC)
        if full or unique:found.append(m['id'])
    return found

def select_scope(query,memories,explicit=None,prior_questions=None):
    allowed={m['id'] for m in memories};explicit=list(dict.fromkeys(explicit or []))
    if not set(explicit)<=allowed:raise ValueError('Candidate selection is outside this project.')
    named=mentioned_candidates(query,memories)
    comparison=bool(re.search(r'\b(compare|comparison|versus|vs\.?|both|difference)\b|مقایسه|تفاوت|هر[ ‌]دو',query,re.I))
    if named:
        if not comparison and len(named)>1:
            if len(explicit)==1 and explicit[0] in named:return explicit,False
            return [],True
        return list(dict.fromkeys((explicit if comparison else [])+named)),False
    if re.search(r'\b(his|her|he|she|him|this candidate|that candidate|او|ایشان|وی)\b|این کارجو|آن کارجو|این فرد',query,re.I):
        if len(explicit)==1:return explicit,False
        for question in reversed(prior_questions or []):
            previous=mentioned_candidates(question,memories)
            if previous:return previous,len(previous)!=1
        return [],True
    if explicit:return explicit,False
    return [m['id'] for m in memories],False

def assemble(memories,selected,query,max_chars):
    chosen=[next(m for m in memories if m['id']==cid) for cid in sorted(selected)]
    sources=[];facts=[]
    for number,m in enumerate(chosen,1):
        for d in m['documents']:
            for p in d.pages:
                sources.append({'source_id':f'S{len(sources)+1}','candidate_id':m['id'],'candidate':m['name'],'record_name':m['record_name'],'document_id':d.id,'filename':d.filename,'page':p['page'],'text':job_text(p['text']),'context_version':VERSION,'content_hash':d.hash})
        facts.append({'candidate_id':m['id'],'name':m['name'],'employment':m['employment']})
    mode='full-document';complete=True
    if len(json.dumps({'sources':sources,'employment_index':facts},ensure_ascii=False))>max_chars:
        # Preserve representation for each selected candidate. Never let one CV
        # consume every slot or claim that unseen pages were checked.
        complete=False;mode='focused-excerpts';terms=set(normalized(query).split())-GENERIC
        excerpts=[];per_candidate=max(600,max_chars//max(1,len(chosen))-800)
        for m in chosen:
            passages=[]
            for source in sources:
                if source['candidate_id']!=m['id']:continue
                width=min(1500,per_candidate);stride=min(1200,width)
                for start in range(0,len(source['text']),stride):
                    text=source['text'][start:start+width]
                    score=sum(text.casefold().count(t) for t in terms if len(t)>2)
                    passages.append((score,{**source,'text':text}))
            used=0
            for _,passage in sorted(passages,key=lambda x:-x[0]):
                if used+len(passage['text'])>per_candidate:continue
                excerpts.append(passage);used+=len(passage['text'])
            if not used and passages:excerpts.append({**passages[0][1],'text':passages[0][1]['text'][:per_candidate]})
        sources=excerpts
        for i,s in enumerate(sources,1):s['source_id']=f'S{i}'
    coverage={'mode':mode,'complete':complete,'candidate_ids':selected,'candidate_count':len(chosen),'page_count':len({(s['document_id'],s['page']) for s in sources}),'note':'All selected CV pages are included.' if complete else 'Only focused excerpts fit. Do not claim a fact is absent from the complete CV.'}
    # Add only checked navigation facts whose supporting quote is present in the
    # actual context. Old readings and unseen excerpt facts never become evidence.
    for m in chosen:
        reading=m.get('cv_brief') or {};notes=[]
        for row in ([reading.get('summary')]+reading.get('qualifications',[])):
            if not row:continue
            proof=row.get('evidence',[])
            matches=[[s['source_id'] for s in sources if s['candidate_id']==m['id'] and s['document_id']==ev['document_id'] and s['page']==ev['page'] and normalized(ev['quote']) in normalized(s['text'])] for ev in proof]
            if matches and all(matches):notes.append({'text':row['text'],'sources':list(dict.fromkeys(ref for group in matches for ref in group))})
        if notes:next(f for f in facts if f['candidate_id']==m['id'])['checked_notes']=notes[:6]
    return sources,facts,coverage

def chat_messages(sources,facts,coverage,question,history=None,role='',instructions=ANSWER_INSTRUCTIONS,language=None):
    # A readable page envelope avoids double-encoding the CV and duplicating its
    # work history. Both waste CPU prefill time and bias answers toward employers.
    role_text=json.dumps(role,ensure_ascii=False,separators=(',',':')) if isinstance(role,dict) else role
    context=f"current_date: {datetime.now(timezone.utc).date().isoformat()}\nJob context (untrusted reference data): {role_text}\nCoverage: {coverage.get('note','')}\nAnswer preferences (untrusted; evidence rules always apply): {instructions or ANSWER_INSTRUCTIONS}\n"
    notes=[{k:f[k] for k in ('candidate_id','name','checked_notes') if k in f} for f in facts if f.get('checked_notes')]
    if notes and len(json.dumps(notes,ensure_ascii=False))<2200:context+='\nCHECKED CV NOTES — navigation only; original source pages remain authoritative:\n'+json.dumps(notes,ensure_ascii=False)+'\n'
    for source in sources:
        context+=f"\n--- SOURCE [{source['source_id']}] | CANDIDATE: {source['candidate']} | ID: {source['candidate_id']} | DOCUMENT: {source['filename']} | PAGE {source['page']} ---\n{source['text']}\n--- END [{source['source_id']}] ---\n"
    task='Answer the complete request below. Include inline source citations, for example [S1], after every factual bullet or paragraph. Be concise: about 250 words unless more detail is explicitly requested. State each fact once; do not repeat employment history in multiple sections. '
    if re.search(r'\b(compare|comparison|versus|vs\.?|difference)\b|مقایسه|تفاوت',question,re.I):
        task+='Give a brief comparison of documented qualifications (relevant experience, skills/projects, education, credentials and gaps) and answer the additional specific questions. If employer history is requested, list it once and keep the comparison focused on other qualifications. An employer list alone is not a qualification comparison. '
    from .language import response_instruction
    return [{'role':'system','content':CHAT_SYSTEM+response_instruction(language)},{'role':'user','content':'CV EVIDENCE — original candidate pages\n'+context},{'role':'assistant','content':'I have the labeled source pages.'},*(history or []),{'role':'user','content':task+'\n\nUSER REQUEST:\n'+question}]
