import re
from .schemas import AnalysisResponse, PROTECTED

MISSING_PROOF = re.compile(r'\b(?:not (?:documented|stated|mentioned|provided|established|specified|listed)|no (?:documented )?evidence (?:of|for|that)|no (?:[a-z0-9+/&-]+\s+){0,5}(?:experience|certifications?|degrees?|qualifications?|leadership|skills?|training))\b|ذکر نشده|ارائه نشده|مشخص نیست|احراز نشده|شواهدی.{0,40}وجود ندارد', re.I)

def normalize(s): return re.sub(r'\s+', ' ', s).strip().casefold()
def valid_evidence(e, pages):
    text = pages.get((e.document_id, e.page), '')
    return bool(text and normalize(e.quote) in normalize(text) and not PROTECTED.search(e.quote) and not MISSING_PROOF.search(e.quote))

def score_result(profile, responses: list[AnalysisResponse], pages):
    """Only verified passages can contribute points. Unknowns never become negative facts.
    Points are documented rubric coverage, not a hiring decision or confidence estimate.
    """
    facts, warnings = [], []
    for response in responses:
        warnings.extend(response.warnings)
        for fact in response.facts:
            if valid_evidence(fact.evidence, pages) and not PROTECTED.search(fact.value):
                if not any(f['kind'] == fact.kind and f['value'] == fact.value for f in facts):
                    facts.append(fact.model_dump())
    assessments, requirements = [], []
    for criterion in profile['criteria']:
        if not criterion['enabled']: continue
        options = []
        for response in responses:
            for a in response.assessments:
                if a.criterion_id != criterion['id']: continue
                ev = [e.model_dump() for e in a.evidence if valid_evidence(e, pages)]
                if ev and a.status == 'Supported' and a.score is not None and not PROTECTED.search(a.explanation):
                    options.append({**a.model_dump(), 'evidence': ev})
        # Each chunk uses the same rubric. Contradictions require human review, never automated failure.
        contradictory = any(a.criterion_id == criterion['id'] and a.status == 'Contradictory information' for r in responses for a in r.assessments)
        if contradictory:
            choice = {'criterion_id': criterion['id'], 'status':'Contradictory information','score':None,'explanation':'Source assessments conflict. Verify the original CV before awarding points.','evidence':[]}
        elif options:
            choice = max(options, key=lambda a: a['score'])
        else:
            choice = {'criterion_id': criterion['id'], 'status':'Not established','score':None,'explanation':'No verified supporting passage was established. Ask the candidate to clarify.','evidence':[]}
        assessments.append({**choice, 'name':criterion['name'], 'weight':criterion['weight']})
    for index, requirement in enumerate(profile['requirements']):
        options = [a for r in responses for a in r.requirements if a.requirement_index == index]
        supported = next((a for a in options if a.status == 'Supported' and any(valid_evidence(e, pages) for e in a.evidence) and not PROTECTED.search(a.explanation)), None)
        requirements.append({'requirement_index':index, 'description':requirement['description'], 'status': 'Supported' if supported else 'Not established', 'explanation':supported.explanation if supported else 'Verify with the candidate; absence from a CV is not proof of absence.', 'evidence':[e.model_dump() for e in supported.evidence if valid_evidence(e, pages)] if supported else []})
    known = [a for a in assessments if a['score'] is not None]
    coverage = round(sum(a['weight'] for a in known), 2)
    score = round(sum(a['score'] * a['weight'] / 100 for a in known), 2) if known else None
    return {'facts':facts,'assessments':assessments,'requirements':requirements,'warnings':list(dict.fromkeys(warnings)), 'interview_questions':list(dict.fromkeys(q for r in responses for q in r.interview_questions if not PROTECTED.search(q)))[:10], 'score':score,'coverage':coverage, 'scoring_note':'Documented points out of the full rubric. Unestablished criteria earn no documented points and remain unknown, not failed. Coverage is evidence availability, not statistical confidence.'}

def rank(candidates):
    return sorted(candidates, key=lambda c: (c.get('score') is None, -(c.get('score') or 0), -(c.get('coverage') or 0), c['created_at'], c['id']))
