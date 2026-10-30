import io
import re
import zipfile
from pathlib import PurePosixPath
import fitz
from docx import Document as WordDocument

MAX_FILE = 25 * 1024 * 1024
MAX_EXPANDED = 200 * 1024 * 1024
MAX_ENTRIES = 2000
def safe_name(name):
    return name.replace('\\','/').split('/')[-1].strip()[:240] or 'resume'
def safe_zip(data):
    result, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        if len(infos) > MAX_ENTRIES: raise ValueError('Archive contains too many files (maximum 2,000).')
        for info in infos:
            path = PurePosixPath(info.filename.replace('\\','/'))
            if path.is_absolute() or '..' in path.parts or ':' in info.filename or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Archive contains unsafe paths or links.')
            total += info.file_size
            if total > MAX_EXPANDED or info.file_size > MAX_FILE or info.file_size / max(1, info.compress_size) > 150:
                raise ValueError('Archive exceeds safe expansion limits.')
            if not info.is_dir() and path.suffix.lower() in ('.pdf','.docx'):
                with z.open(info) as stream:
                    content = stream.read(MAX_FILE + 1)
                if len(content) > MAX_FILE: raise ValueError('Expanded file exceeds upload limit.')
                result.append((str(path), content))
    if not result: raise ValueError('No supported PDF or DOCX resumes found in this archive.')
    return result

def extract(filename, data):
    ext = PurePosixPath(filename).suffix.lower()
    warnings = []
    if ext == '.pdf':
        if not data.startswith(b'%PDF-'): raise ValueError('File does not have a valid PDF signature.')
        with fitz.open(stream=data, filetype='pdf') as pdf:
            if pdf.needs_pass: raise ValueError('Password-protected PDF. Upload an unlocked copy.')
            if len(pdf) > 200: raise ValueError('Resume exceeds the 200-page safety limit.')
            pages = []
            for i, page in enumerate(pdf):
                text = page.get_text(sort=True)
                if not text.strip(): warnings.append(f'Page {i+1}: no selectable text. OCR is required; upload a searchable PDF.')
                pages.append({'page':i+1,'text':text[:60000]})
    elif ext == '.docx':
        # Validate the ZIP container before handing it to the XML parser; never execute content.
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist()) > 2000 or sum(i.file_size for i in z.infolist()) > MAX_EXPANDED:
                raise ValueError('DOCX exceeds safe expansion limits.')
            if any(i.file_size / max(1,i.compress_size) > 150 for i in z.infolist()): raise ValueError('Unsafe DOCX compression ratio.')
        doc = WordDocument(io.BytesIO(data))
        text = '\n'.join([p.text for p in doc.paragraphs] + [' | '.join(c.text for c in row.cells) for t in doc.tables for row in t.rows])
        pages = [{'page':1,'text':text[:500000]}]
        warnings.append('DOCX references use text section 1; Word pagination is not preserved.')
    else: raise ValueError('Only PDF, DOCX, and ZIP imports are supported.')
    if not any(p['text'].strip() for p in pages): raise ValueError('No readable text. Make the document searchable with OCR before importing.')
    return pages, warnings

SENSITIVE_LINE = re.compile(r'(?im)^.*\b(gender|nationality|citizenship|date of birth|born|marital|religion|ethnicity|race|disability)\b[^\n]*$')
def job_text(text):
    return SENSITIVE_LINE.sub('[Administrative information excluded]', text)

def chunks(docs, size=9000):
    for doc in docs:
        for page in doc.pages:
            text = job_text(page['text'])
            for start in range(0, len(text), size):
                yield {'document_id':doc.id,'page':page['page'],'text':text[start:start+size]}
