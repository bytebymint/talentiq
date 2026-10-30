from .helpers import pdf_bytes

def test_delete_selected_resume_keeps_other_resume_and_human_notes(client,project):
    def upload(name,text):
        result=client.post('/api/documents/import',data={'project_id':project['id']},files={'files':(name,pdf_bytes(text),'application/pdf')}).json()['results'][0]
        result['document_id']=client.get('/api/candidates/'+result['candidate_id']).json()['documents'][0]['id']
        return result
    first=upload('First.pdf','Synthetic first resume. Python engineer.')
    second=upload('Second.pdf','Synthetic second resume. Different qualifications.')
    client.patch('/api/candidates/'+first['candidate_id'],json={'status':'On Hold','note':'Keep this human review.'})
    result=client.delete('/api/documents/'+first['document_id'])
    assert result.status_code==200
    assert client.get('/api/documents/'+first['document_id']+'/original').status_code==404
    assert client.get('/api/documents/'+second['document_id']+'/original').status_code==200
    candidate=client.get('/api/candidates/'+first['candidate_id']).json()
    assert candidate['notes'][0]['text']=='Keep this human review.'
    assert candidate['status']=='On Hold' and candidate['documents']==[]
