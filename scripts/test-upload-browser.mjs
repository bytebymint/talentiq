// All API requests are intercepted. Never writes to the live workspace.
import {chromium,expect} from '@playwright/test';
import {readFile,mkdir,writeFile,mkdtemp} from 'node:fs/promises';
import os from 'node:os';import path from 'node:path';
const url=process.env.TALENTIQ_UPLOAD_TEST_URL||'http://127.0.0.1:3001';
if(!new URL(url).hostname.match(/^(localhost|127\.0\.0\.1)$/))throw new Error('Upload tests require an isolated local frontend.');
const fixture=JSON.parse(await readFile('tests/fixtures/resume-files.json','utf8'));
const temp=await mkdtemp(path.join(os.tmpdir(),'talentiq-upload-regression-'));
const pdf=Buffer.from(fixture['Synthetic_Resume.pdf'],'base64');
await mkdir(path.join(temp,'رزومه‌ها'));await writeFile(path.join(temp,'First.pdf'),pdf);await writeFile(path.join(temp,'Second.pdf'),pdf);await writeFile(path.join(temp,'رزومه‌ها','Resume.pdf'),pdf);
const browser=await chromium.launch({channel:'chrome',headless:true});const checks=[];
const testDelete=process.env.TALENTIQ_TEST_RESUME_DELETE==='1';
try{
 for(const language of ['en','fa']){
  const context=await browser.newContext();await context.addCookies([{name:'talentiq-language',value:language,url}]);const page=await context.newPage();let attempts={},posts=[],deletes=0;
  await page.addInitScript(()=>{const read=File.prototype.arrayBuffer;File.prototype.arrayBuffer=function(){if(this.name==='Unreadable.pdf')return Promise.reject(new DOMException('Synthetic unreadable file','NotReadableError'));return read.call(this);};});
  const user={id:'existing-user',name:'Existing HR',username:'existing-hr',role:'admin'},project={id:'existing-project',name:'Existing recruitment project',profile_id:'existing-profile',archived:false};
  let documents=['a','b'].map(id=>({id:'existing-'+id,display_name:'Existing '+id.toUpperCase()+'.pdf',filename:'Existing '+id.toUpperCase()+'.pdf',candidate_name:'Synthetic candidate '+id,project_id:project.id,folder_id:null,size:1000,created_at:'2026-10-29T00:00:00Z',warnings:[]}));
  await page.route('**/api/**',async route=>{
   const request=route.request(),endpoint=new URL(request.url()).pathname.slice(4);if(request.method()==='DELETE')deletes++;
   const respond=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
   if(testDelete&&request.method()==='DELETE'){if(endpoint!=='/documents/existing-a')throw new Error('The wrong resume was selected for deletion.');documents=documents.filter(d=>d.id!=='existing-a');return respond({deleted:'existing-a'});}
   if(testDelete&&endpoint==='/documents')return respond(documents);
   if(endpoint==='/documents/import'){
    const bytes=request.postDataBuffer(),body=bytes.toString('latin1'),match=body.match(/filename="([^"]+)"/);const filename=Buffer.from(match?.[1]||'','latin1').toString('utf8');attempts[filename]=(attempts[filename]||0)+1;posts.push({filename,size:bytes.length,hasProject:body.includes('existing-project'),hasFolders:body.includes('preserve_folders')});
    if(filename==='Second.pdf'&&attempts[filename]===1)return route.abort('failed');
    if(filename==='Gateway.pdf'&&attempts[filename]===1)return route.fulfill({status:502,contentType:'text/html',body:'<html>Temporary gateway failure</html>'});
    if(filename==='Expired.pdf')return route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Sign in to your workspace.'})});
    return respond({results:[{filename,status:'imported',candidate_id:'synthetic-'+filename,document_id:'doc-'+filename,warnings:[]}]});
   }
   if(endpoint==='/health')return respond({ok:true,setup_required:false,local_only:true});
   if(endpoint==='/auth/me')return respond(user);
   if(endpoint==='/ai/status')return respond({state:'configured',provider:'qwencloud',key_configured:true,models:[],running:[]});
   if(endpoint==='/events')return route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({jobs:[],revision:1,engine_state:'configured'})+'\n\n'});
   if(endpoint==='/projects')return respond([project]);
   if(endpoint==='/profiles')return respond([{id:'existing-profile',name:'Existing role',version:1,config:{criteria:[],requirements:[]}}]);
   if(endpoint==='/analytics')return respond({candidates:0,evaluated:0,shortlisted:0,needs_review:0,projects:1,pipeline:{},gaps:{},skills:{},score_distribution:{}});
   return respond([]);
  });
  await page.goto(url+'/#folders');
  if(testDelete){
   const row=page.locator('.document-row').filter({hasText:'Existing A.pdf'});await row.locator('input[type=checkbox]').check();
   const remove=page.getByRole('button',{name:language==='en'?'Delete selected resumes':'حذف رزومه‌های انتخاب‌شده',exact:true});await remove.click();await expect(page.getByRole('dialog')).toContainText('Existing A.pdf');await page.getByRole('dialog').locator('footer button').first().click();if(deletes)throw new Error('Cancel sent a delete request.');
   await remove.click();await page.getByRole('dialog').locator('footer button.danger').click();await expect(row).toHaveCount(0);await expect(page.locator('.document-row').filter({hasText:'Existing B.pdf'})).toHaveCount(1);if(deletes!==1)throw new Error('Unexpected delete count.');
   checks.push({language,confirmation:true,cancelPreserves:true,onlySelectedDeleted:true,otherResumeKept:true});await context.close();continue;
  }
  await page.getByRole('button',{name:language==='en'?'Import resumes':'وارد کردن رزومه‌ها',exact:true}).first().click().catch(async()=>{await page.locator('main button').filter({has:page.locator('svg.lucide-upload')}).first().click();});
  const dialog=page.getByRole('dialog');await dialog.locator('input[type=file][accept=".pdf,.docx,.zip"]').setInputFiles([path.join(temp,'First.pdf'),path.join(temp,'Second.pdf')]);
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();
  await expect(dialog).toContainText(language==='en'?'The upload connection was interrupted.':'ارتباط هنگام بارگذاری قطع شد.');
  if(attempts['First.pdf']!==1||attempts['Second.pdf']!==1)throw new Error('Unexpected initial upload attempts.');
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();
  if(attempts['First.pdf']!==1||attempts['Second.pdf']!==2)throw new Error('Retry resubmitted an already completed file.');
  await dialog.locator('input[type=file][webkitdirectory]').setInputFiles(path.join(temp,'رزومه‌ها'));
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();
  if(!posts.some(p=>p.filename==='رزومه‌ها/Resume.pdf'))throw new Error('The browser folder path was lost.');
  await dialog.locator('input[type=file][accept=".pdf,.docx,.zip"]').setInputFiles({name:'Gateway.pdf',buffer:pdf,mimeType:'application/pdf'});
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();await expect(dialog).toContainText(language==='en'?'The upload service returned an incomplete response.':'پاسخ سرویس بارگذاری کامل نبود.');
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();if(attempts['Gateway.pdf']!==2)throw new Error('A gateway failure could not be retried.');
  await dialog.locator('input[type=file][accept=".pdf,.docx,.zip"]').setInputFiles({name:'Expired.pdf',buffer:pdf,mimeType:'application/pdf'});
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();await expect(dialog).toContainText(language==='en'?'Your session has expired.':'نشست کاربری شما منقضی شده است.');
  await dialog.locator('input[type=file][accept=".pdf,.docx,.zip"]').setInputFiles({name:'Unreadable.pdf',buffer:pdf,mimeType:'application/pdf'});
  await dialog.locator('footer button.primary').click();await expect(dialog.locator('footer button.primary')).toBeEnabled();await expect(dialog).toContainText(language==='en'?'This file could not be read.':'خواندن این فایل امکان‌پذیر نیست.');if(attempts['Unreadable.pdf'])throw new Error('An unreadable file was sent to the server.');
  if(deletes||posts.some(p=>!p.hasProject||!p.hasFolders||p.size<pdf.length))throw new Error('Upload changed existing records or lost document bytes.');
  checks.push({language,retryKeepsCompleted:true,folderPaths:true,realPdfBytes:true,gatewayFailure:true,sessionExpiry:true,unreadableFile:true,deleteRequests:deletes});await context.close();
 }
 await mkdir('test-results/uploads',{recursive:true});await writeFile('test-results/uploads/'+(testDelete?'delete-browser.json':'browser.json'),JSON.stringify({url,isolatedAPI:true,checks},null,2));console.log(JSON.stringify(checks));
}finally{await browser.close();}
