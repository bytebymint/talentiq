"""Synthetic progress fixture, restricted to the disposable browser-test DB."""
import os,sys,tempfile
from pathlib import Path
folder=Path(os.environ.get('TALENTIQ_DATA_DIR','')).resolve()
if os.environ.get('TALENTIQ_TEST_FIXTURE')!='1' or 'talentiq-ui-' not in str(folder) or not folder.is_relative_to(Path(tempfile.gettempdir()).resolve()):
    raise RuntimeError('Synthetic job writes require an isolated temporary browser-test directory.')
state=sys.argv[1]
if state not in ('processing','completed'):raise ValueError('Unknown fixture state.')
from backend.db import Session,Job,Candidate,Profile,Project,now
with Session() as db:
    candidates=db.query(Candidate).order_by(Candidate.name).all();project=db.get(Project,candidates[0].project_id);profile=db.get(Profile,project.profile_id)
    job=db.query(Job).filter_by(model='synthetic-progress-test-only').first()
    if not job:
        job=Job(project_id=project.id,profile_snapshot={**profile.config,'profile_id':profile.id},profile_version=profile.version,model='synthetic-progress-test-only',items=[]);db.add(job)
    job.state=state;job.stage='SYNTHETIC STATUS CHECK '+state.upper();job.updated_at=now()
    job.current=candidates[0].id if state=='processing' else None
    job.items=[{'candidate_id':c.id,'name':c.name,'state':'completed' if state=='completed' else 'processing' if i==0 else 'pending','index_state':'completed' if state=='completed' else None} for i,c in enumerate(candidates)]
    db.commit()
