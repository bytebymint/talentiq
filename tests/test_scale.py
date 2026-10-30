"""Large intake is tested locally; no provider calls or real CVs are used."""
import io
import zipfile
from .helpers import pdf_bytes
from backend.ai import ollama
from backend.jobs import jobs

def test_import_and_queue_501_resumes(client,project,monkeypatch):
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zipped:
        for index in range(501):
            zipped.writestr(f'Synthetic intake/Candidate-{index:04d}.pdf',pdf_bytes(f'Synthetic Candidate {index:04d}\nBuilt production services using Python.\nFictional document for a scale regression test.'))
    response=client.post('/api/documents/import',data={'project_id':project['id'],'preserve_folders':'true'},files={'files':('synthetic-501.zip',archive.getvalue(),'application/zip')})
    assert response.status_code==200
    imported=response.json()['results']
    assert len(imported)==501 and all(row.get('status')=='Imported' for row in imported)
    assert len(client.get('/api/candidates?project_id='+project['id']).json())==501
    assert len(client.get('/api/documents?project_id='+project['id']).json())==501
    async def configured_provider():return {'models':['qwen3:4b-instruct']}
    launched=[]
    monkeypatch.setattr(ollama,'status',configured_provider)
    monkeypatch.setattr(jobs,'launch',lambda job_id:launched.append(job_id))
    queued=client.post('/api/jobs',json={'project_id':project['id']})
    assert queued.status_code==200
    job=queued.json()
    assert len(job['items'])==501 and all(item['state']=='pending' for item in job['items'])
    assert launched==[job['id']]
