"""Write-only provider credentials, separate from database exports/backups."""
import base64,ctypes,os
from pathlib import Path
from .db import DATA

def _path():return DATA/'.credentials'/'qwencloud.key'

def _protect(data,decrypt=False):
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    crypt=ctypes.windll.crypt32
    ok=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)) if decrypt else crypt.CryptProtectData(ctypes.byref(source),'TalentIQ QwenCloud',None,None,None,1,ctypes.byref(target))
    if not ok:raise ValueError('The saved API key could not be accessed by this server account. Configure its environment variable or save it again.')
    try:return ctypes.string_at(target.data,target.size)
    finally:ctypes.windll.kernel32.LocalFree(target.data)

def key_source():
    if os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWENCLOUD_API_KEY'):return 'environment'
    return 'server credential store' if _path().is_file() else 'not configured'

def get_key():
    value=os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWENCLOUD_API_KEY')
    if value:return value.strip()
    path=_path()
    if not path.is_file():return ''
    data=path.read_bytes()
    if data.startswith(b'dpapi:'):
        if os.name!='nt':raise ValueError('Set DASHSCOPE_API_KEY on this host; the saved Windows credential belongs to the original server account.')
        return _protect(base64.b64decode(data[6:]),True).decode()
    return data.removeprefix(b'plain:').decode()

def save_key(value):
    value=value.strip()
    if not value or len(value)>4096 or any(c.isspace() for c in value):raise ValueError('Enter a valid API key without whitespace.')
    if key_source()=='environment':raise ValueError('This server uses an environment API key. Update DASHSCOPE_API_KEY on the server to change it.')
    path=_path();path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    data=b'dpapi:'+base64.b64encode(_protect(value.encode())) if os.name=='nt' else b'plain:'+value.encode()
    temporary=path.with_suffix('.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'wb') as out:out.write(data)
    temporary.replace(path)
