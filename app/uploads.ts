import {currentLocale,localize} from './i18n';

export async function uploadResume(file:File,projectId:string,folderId:string,signal:AbortSignal,onReady:()=>void){
 if(file.size>25*1024*1024)throw new Error(localize('File exceeds the 25 MB upload limit.'));
 let bytes:ArrayBuffer;
 try{bytes=await file.arrayBuffer();if(bytes.byteLength!==file.size)throw new Error('Incomplete file read');}
 catch{throw new Error(localize('This file could not be read. Save a copy on this computer, choose it again, and retry.'));}
 // Send immutable bytes rather than holding a native file handle across a
 // network request. Keep the selected file and its folder path for retries.
 const body=new FormData();body.set('project_id',projectId);body.set('folder_id',folderId);body.set('preserve_folders','true');
 body.append('files',new Blob([bytes],{type:file.type||'application/octet-stream'}),file.webkitRelativePath||file.name);
 onReady();
 const controller=new AbortController();let timedOut=false;const cancel=()=>controller.abort();if(signal.aborted)cancel();else signal.addEventListener('abort',cancel,{once:true});
 const timer=setTimeout(()=>{timedOut=true;controller.abort();},180000);let response:Response;
 try{response=await fetch('/api/documents/import',{method:'POST',credentials:'same-origin',headers:{'X-TalentIQ-Request':'1','X-TalentIQ-Language':currentLocale()},body,signal:controller.signal});}
 catch{throw new Error(localize(signal.aborted?'Upload cancelled.':timedOut?'The upload took too long. Retry this file; completed imports are kept.':'The upload connection was interrupted. Retry this file; completed imports are kept.'));}
 finally{clearTimeout(timer);signal.removeEventListener('abort',cancel);}
 let result:any;
 try{result=await response.json();}
 catch{throw new Error(localize(response.status===413?'File exceeds the 25 MB upload limit.':'The upload service returned an incomplete response. Retry this file; completed imports are kept.'));}
 if(!response.ok)throw new Error(localize(response.status===401?'Your session has expired. Sign in again; your saved work is kept.':typeof result.detail==='string'?result.detail:'Import rejected. Check the file and try again.'));
 if(!Array.isArray(result.results))throw new Error(localize('The upload service returned an incomplete response. Retry this file; completed imports are kept.'));
 return result;
}
