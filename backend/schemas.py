import re
from .hr import ASSESSMENT_INSTRUCTIONS
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

PROTECTED = re.compile(r'\b(gender\w*|nationalit\w*|citizenship|race|ethnic\w*|religio\w*|age|birth\w*|marital|pregnan\w*|maternit\w*|disabilit\w*|sexual\w*|sex|photo|appearance|male|female|women|men|nonbinary|young|youth)\b|\bnational\s+origin\b|\b(?:جنسیت|ملیت|تابعیت|نژاد|قومیت|مذهب|معلولیت|بارداری|سن)\b|وضعیت[‌ ]تأهل|گرایش[‌ ]جنسی', re.I)
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Criterion(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    weight: float = Field(ge=0, le=100)
    enabled: bool = True
    mandatory: bool = False
    instructions: str = Field(default='', max_length=1500)
class Requirement(Strict):
    description: str = Field(min_length=1, max_length=500)
    type: Literal['Skill','Certification','Qualification','Experience','Language','Work authorization','Other'] = 'Skill'
    classification: Literal['Required','Preferred'] = 'Required'
    expected_value: str = Field(default='', max_length=300)
    verification: str = Field(default='CV evidence and interview', max_length=300)
    notes: str = Field(default='', max_length=500)
class ProfileInput(Strict):
    name: str = Field(min_length=2, max_length=120)
    job_title: str = Field(min_length=2, max_length=120)
    department: str = Field(default='', max_length=120)
    description: str = Field(default='', max_length=20000)
    seniority: str = 'Mid-level'
    employment: str = 'Full-time'
    location: str = ''
    arrangement: str = 'Hybrid'
    salary: str = ''
    notes: str = ''
    criteria: list[Criterion] = Field(min_length=1, max_length=30)
    requirements: list[Requirement] = Field(default_factory=list, max_length=100)
    model: str = 'qwen3.5:4b-q4_K_M'
    depth: Literal['Balanced','Fast','Standard','Detailed'] = 'Balanced'
    instructions: str = Field(default=ASSESSMENT_INSTRUCTIONS, max_length=3000)
    shortlist_size: int = Field(default=10, ge=1, le=10000)
    language: str = 'English'
    missing_information: Literal['Not established'] = 'Not established'
    @model_validator(mode='after')
    def valid_rubric(self):
        if abs(sum(c.weight for c in self.criteria if c.enabled) - 100) > 0.00001:
            raise ValueError('Enabled criterion weights must total exactly 100%.')
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError('Criterion identifiers must be unique.')
        texts = [f'{c.name} {c.instructions}' for c in self.criteria] + [f'{r.description} {r.expected_value} {r.notes}' for r in self.requirements]
        if any(PROTECTED.search(t) for t in texts):
            raise ValueError('Scoring criteria and requirements must only describe job-relevant qualifications; protected traits are not allowed.')
        return self

class Evidence(Strict):
    document_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=10, max_length=1200)
class Assessment(Strict):
    criterion_id: str
    status: Literal['Supported','Not established','Contradictory information']
    score: float | None = Field(default=None, ge=0, le=100)
    explanation: str = Field(max_length=2000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)
class RequirementAssessment(Strict):
    requirement_index: int = Field(ge=0)
    status: Literal['Supported','Not established','Contradictory information']
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)
class Fact(Strict):
    kind: Literal['Skill','Employment','Education','Certification','Language','Achievement','Project','Summary','Name']
    value: str = Field(min_length=1, max_length=1000)
    evidence: Evidence
class AnalysisResponse(Strict):
    facts: list[Fact] = Field(default_factory=list, max_length=100)
    assessments: list[Assessment]
    requirements: list[RequirementAssessment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    interview_questions: list[str] = Field(default_factory=list, max_length=10)

# Compact inference wire format avoids asking a CPU model to repeat long document
# identifiers and verbose field names for every quote. Provenance is assigned by
# application code from the single source chunk, then validated by the same rubric.
class CompactFact(Strict):
    k: Literal['Skill','Employment','Education','Certification','Language','Achievement','Project','Summary','Name']
    v: str = Field(min_length=1,max_length=300)
    q: str = Field(min_length=10,max_length=280)
class CompactAssessment(Strict):
    i: str = Field(description='Exact criterion ID from the recruitment rubric, never its display name.')
    s: Literal['yes','unknown','conflict'] = Field(description='yes for source-supported qualifications, unknown for absent evidence, conflict for contradictory evidence.')
    n: float | None = Field(default=None,ge=0,le=100,description='Criterion match points from 0 to 100 when s=yes; otherwise null.')
    x: str = Field(min_length=10,max_length=180)
    q: list[str] = Field(default_factory=list,max_length=2)
class CompactRequirement(Strict):
    i: int = Field(ge=0)
    s: Literal['yes','unknown','conflict']
    x: str = Field(min_length=10,max_length=180)
    q: list[str] = Field(default_factory=list,max_length=2)
class CompactAnalysisResponse(Strict):
    f: list[CompactFact] = Field(default_factory=list,max_length=12)
    a: list[CompactAssessment]
    r: list[CompactRequirement] = Field(default_factory=list)
    w: list[str] = Field(default_factory=list,max_length=3)
    j: list[str] = Field(default_factory=list,max_length=3)

def analysis_schema(profile):
    from copy import deepcopy
    schema=CompactAnalysisResponse.model_json_schema()
    criteria=[c['id'] for c in profile['criteria'] if c['enabled']]
    count=len(profile['requirements'])
    schema['required']=['f','a','r','w','j']
    schema['properties']['a'].update(minItems=len(criteria),maxItems=len(criteria))
    schema['properties']['r'].update(minItems=count,maxItems=count)
    schema['$defs']['CompactAssessment']['properties']['i']['enum']=criteria
    schema['$defs']['CompactAssessment']['required']=['i','s','n','x','q']
    schema['$defs']['CompactRequirement']['required']=['i','s','x','q']
    if count:schema['$defs']['CompactRequirement']['properties']['i']['enum']=list(range(count))
    # A supported assessment cannot omit its quote or numeric match score.
    for field,definition in [('a','CompactAssessment'),('r','CompactRequirement')]:
        supported=deepcopy(schema['$defs'][definition]);unknown=deepcopy(supported)
        supported['properties']['s']={'type':'string','enum':['yes']}
        supported['properties']['q'].update(minItems=1)
        supported['properties']['q']['items'].update(minLength=10,maxLength=280)
        unknown['properties']['s']={'type':'string','enum':['unknown','conflict']}
        if field=='a':
            supported['properties']['n']={'type':'number','minimum':0,'maximum':100}
            unknown['properties']['n']={'type':'null'}
        schema['properties'][field]['items']={'anyOf':[supported,unknown]}
        del schema['$defs'][definition]
    if profile.get('depth')=='Detailed':schema['title']='CompactAnalysisResponseDetailed'
    return schema

def parse_analysis_response(raw,source):
    import json
    value=json.loads(raw)
    if 'assessments' in value: return AnalysisResponse.model_validate(value)
    compact=CompactAnalysisResponse.model_validate(value)
    statuses={'yes':'Supported','unknown':'Not established','conflict':'Contradictory information'}
    def ev(quote): return {'document_id':source['document_id'],'page':source['page'],'quote':quote}
    def source_quotes(quotes,explanation):
        # Small models sometimes swap quote and explanation slots. Recover only
        # text that is itself an exact source substring; never invent evidence.
        if not source.get('text'):return quotes
        normalize=lambda text:re.sub(r'\s+',' ',text).strip().casefold()
        passage=normalize(source['text'])
        verified=[quote for quote in quotes if len(quote)>=10 and normalize(quote) in passage]
        if not verified and len(explanation)>=10 and normalize(explanation) in passage:verified=[explanation]
        return verified
    return AnalysisResponse.model_validate({
        'facts':[{'kind':f.k,'value':f.v,'evidence':ev(f.q)} for f in compact.f],
        'assessments':[{'criterion_id':a.i,'status':statuses[a.s],'score':a.n if a.s=='yes' else None,'explanation':a.x,'evidence':[ev(q) for q in source_quotes(a.q,a.x)]} for a in compact.a],
        'requirements':[{'requirement_index':r.i,'status':statuses[r.s],'explanation':r.x,'evidence':[ev(q) for q in source_quotes(r.q,r.x)]} for r in compact.r],
        'warnings':compact.w,'interview_questions':compact.j})

STAGES = ['Imported','Pending Analysis','Analyzed','Needs Review','Under HR Review','Shortlisted','Interview Scheduled','Interview Completed','On Hold','Hired','Not Selected']
