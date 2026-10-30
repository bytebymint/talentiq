import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';

export async function checkFarsi({page,context,browser,output,checks}){
 const fa=JSON.parse(await readFile('app/fa.json','utf8'));
 const englishText=new Set();
 await page.route('**/api/translations',async route=>{
  const body=route.request().postDataJSON();
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({translations:body.texts.map(text=>`توضیح آزمایشی بر اساس شواهد رزومه. ${(text.match(/\[S\d+\]/g)||[]).join(' ')}`)})});
 });
 await page.getByRole('button',{name:'Switch to Persian',exact:true}).click();
 await page.locator('html[lang=fa][dir=rtl]').waitFor();
 assert((await page.title()).includes('تلنت'));
 const font=await page.locator('body').evaluate(el=>getComputedStyle(el).fontFamily);
 assert(font.includes('Vazirmatn'));
 const nav=['Overview','Recruitment Projects','Candidate Library','Resume Folders','Talent Search','AI Workspace','Candidate Rankings','Comparisons','Recruitment Analytics','Recruitment Profiles','Activity & Audit','Settings'];
 for(const theme of ['light','dark']){
  const toggle=page.getByRole('button',{name:fa[theme==='light'?'Switch to light theme':'Switch to dark theme'],exact:true});
  if(await toggle.count())await toggle.click();
  for(const size of [{width:1440,height:1000},{width:390,height:844}]){
   await page.setViewportSize(size);
   for(const name of nav){
    await page.getByRole('button',{name:fa[name],exact:true}).first().click();
    const dims=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth,dir:document.documentElement.dir}));
    for(const text of await page.evaluate(()=>{const found=[];const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode()){const p=node.parentElement,text=node.textContent.trim();if(!p||!/[A-Za-z]{2}/.test(text)||['SCRIPT','STYLE'].includes(p.tagName)||!p.getClientRects().length)continue;found.push(text);}return found;}))englishText.add(text);
    assert.equal(dims.dir,'rtl');assert(dims.scroll<=dims.width+1,`${name}: Persian overflow at ${size.width}`);
   }
   checks.push(`12 Persian ${theme} screens fit at ${size.width}×${size.height}`);
  }
 }
 await writeFile(path.join(output,'fa-visible-text-audit.json'),JSON.stringify([...englishText].sort(),null,2));
 const unexpected=[...englishText].filter(text=>!/Synthetic|SYNTHETIC|synthetic|Built production Python services|^Python$|^Python Engineer$|^qwen|^text-embedding|^[a-f\d]{20,}$|ap-southeast-1|OpenAI|\bAPI\b|\bJSON\b|\bSQLite\b|\bWAL\b|\bUTF-8\b|\bSHA-256\b|\bPDF\b|\bDOCX\b/.test(text));
 assert.deepEqual(unexpected,[],'Untranslated Persian interface text');
 await page.setViewportSize({width:1440,height:1000});
 await page.reload();await page.locator('html[lang=fa][dir=rtl]').waitFor();
 assert((await (await context.request.get('http://127.0.0.1:3000')).text()).includes('lang="fa"'));
 assert.equal(await page.evaluate(()=>localStorage.getItem('talentiq-language')),'fa');
 const sidebar=await page.locator('.sidebar').boundingBox();assert(Math.abs(sidebar.x+sidebar.width-1440)<2,'Persian sidebar is on the right');
 checks.push('Persian font, RTL sidebar, translated navigation and language persistence through server rendering');

 await page.getByRole('button',{name:fa['Overview'],exact:true}).first().click();
 await page.getByText(fa['YOUR NEXT STEP'],{exact:true}).waitFor();
 await page.getByRole('button',{name:fa['Refresh CV reviews'],exact:true}).waitFor();
 await page.getByRole('button',{name:fa['Candidate Library'],exact:true}).first().click();
 await page.locator('button.candidate-cell').filter({hasText:'Synthetic Candidate B'}).first().click();
 await page.getByText(fa['Checked against CV sources'],{exact:true}).waitFor();
 await page.getByText(fa['Demonstrated in work or projects'],{exact:true}).waitFor();
 for(const size of [{width:1440,height:1000},{width:390,height:844}]){
  await page.setViewportSize(size);const dims=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));assert(dims.scroll<=dims.width+1,'Persian CV brief fits');
 }
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:path.join(output,'fa-checked-cv-brief-synthetic.png'),fullPage:true});
 await page.getByRole('button',{name:fa['Check role match'],exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:fa['Human review'],exact:true}).click();
 const human=page.getByRole('group',{name:fa['Human hiring decision'],exact:true});
 await human.getByRole('button').filter({has:page.getByText(fa['Hire'],{exact:true})}).click();
 assert.equal(await page.getByLabel(fa['Pipeline stage'],{exact:true}).inputValue(),'Hired');
 assert(await page.getByRole('button',{name:fa['Save human review'],exact:true}).isDisabled());
 await human.getByRole('button').filter({has:page.getByText(fa['Hold'],{exact:true})}).click();
 assert.equal(await page.getByLabel(fa['Pipeline stage'],{exact:true}).inputValue(),'On Hold');
 await human.getByRole('button').filter({has:page.getByText(fa['Reject'],{exact:true})}).click();
 assert.equal(await page.getByLabel(fa['Pipeline stage'],{exact:true}).inputValue(),'Not Selected');
 await page.screenshot({path:path.join(output,'fa-human-hiring-decision-synthetic.png'),fullPage:true});
 checks.push('Persian human hiring choices, stable outcome values and required final confirmation');
 
 await page.getByRole('dialog').getByRole('button',{name:fa['Close dialog'],exact:true}).click();
 checks.push('Persian guided HR home and checked CV brief with source controls and mobile layout');

 await page.getByRole('button',{name:fa['Recruitment Profiles'],exact:true}).first().click();
 await page.getByRole('button',{name:fa['Create profile'],exact:true}).click();
 const modal=page.getByRole('dialog');
 await modal.getByLabel(fa['Profile name *'],{exact:true}).fill('الگوی آزمون فارسی');
 await modal.getByLabel(fa['Job title *'],{exact:true}).fill('کارشناس نرم‌افزار');
 await modal.getByLabel(fa['Seniority'],{exact:true}).selectOption('Senior');
 assert.equal(await modal.getByLabel(fa['Seniority'],{exact:true}).inputValue(),'Senior');
 await modal.getByRole('button',{name:fa['Switch to English'],exact:true}).click();
 assert.equal(await modal.getByLabel('Profile name *',{exact:true}).inputValue(),'الگوی آزمون فارسی');
 await modal.getByRole('button',{name:'Switch to Persian',exact:true}).click();
 await modal.getByRole('button',{name:fa['Continue'],exact:true}).click();
 await modal.getByRole('button',{name:fa['Add requirement'],exact:true}).click();
 await modal.getByLabel(fa['Description'],{exact:true}).fill('تجربهٔ توسعهٔ نرم‌افزار با پایتون');
 assert.equal(await modal.getByLabel(fa['Type'],{exact:true}).inputValue(),'Skill');
 assert.equal(await modal.getByLabel(fa['Classification'],{exact:true}).inputValue(),'Required');
 await modal.getByRole('button',{name:fa['Continue'],exact:true}).click();
 assert(/[\u0600-\u06ff]/.test(await modal.locator('.criterion-name').first().inputValue()));
 await modal.getByRole('button',{name:fa['Continue'],exact:true}).click();
 assert(/[\u0600-\u06ff]/.test(await modal.getByLabel(fa['Review instructions'],{exact:true}).inputValue()));
 assert.equal(await modal.getByLabel(fa['Evaluation language'],{exact:true}).inputValue(),'Persian');
 await page.screenshot({path:path.join(output,'fa-profile-guidance.png'),fullPage:true});
 await modal.getByRole('button',{name:fa['Continue'],exact:true}).click();
 const saving=page.waitForResponse(r=>r.url().endsWith('/api/profiles')&&r.request().method()==='POST');
 await modal.getByRole('button',{name:fa['Save profile'],exact:true}).click();
 const saved=await saving;assert(saved.ok());const savedProfile=await saved.json();
 assert.equal(savedProfile.config.language,'Persian');assert.equal(savedProfile.config.requirements[0].type,'Skill');
 await modal.waitFor({state:'hidden'});
 checks.push('Persian profile wizard, prefilled guidance, stable API enum values and form contents preserved across toggles');

 await page.getByRole('button',{name:fa['Talent Search'],exact:true}).first().click();
 await page.getByRole('button',{name:fa['Recruitment copilot'],exact:true}).click();
 const composer=page.getByLabel(fa['Message recruitment copilot'],{exact:true});
 await composer.waitFor();await page.getByRole('button',{name:fa['Review CV'],exact:true}).waitFor();
 await page.getByRole('button',{name:fa['Hiring review'],exact:true}).click();
 assert(/[\u0600-\u06ff]/.test(await composer.inputValue()));
 await page.getByRole('button',{name:fa['Review CV'],exact:true}).click();
 assert(/[\u0600-\u06ff]/.test(await composer.inputValue()));
 await page.getByText(fa['HR instructions · ready to use'],{exact:true}).click();
 const instructions=page.getByLabel(fa['Answer instructions'],{exact:true});
 assert(/[\u0600-\u06ff]/.test(await instructions.inputValue()));
 await instructions.fill('متن آزمایشی');await page.getByRole('button',{name:fa['Restore default instructions'],exact:true}).click();
 assert((await instructions.inputValue()).includes('پاسخ'));
 await page.getByText(fa['HR instructions · ready to use'],{exact:true}).click();
 let history=[],requestBody;
 await page.route('**/api/chat**',async route=>{
  if(new URL(route.request().url()).pathname.endsWith('/playbook'))return route.continue();
  if(route.request().method()==='POST'){
   requestBody=route.request().postDataJSON();
   const sources=[{source_id:'S1',candidate:'Synthetic Candidate A',candidate_id:requestBody.candidate_id,document_id:'fa-fixture',page:1,coverage_complete:true,chat_model:'qwen3.8-flash',ai_provider:'qwencloud',answer_language:'fa'}];
   const answer='کارجو سابقهٔ توسعهٔ خدمات پایتون دارد. [S1]';history=[{id:'fa-user',role:'user',content:requestBody.query,sources:[]},{id:'fa-answer',role:'assistant',content:answer,sources}];
   await route.fulfill({status:200,contentType:'application/x-ndjson',body:[{sources,coverage:{complete:true},provider:'qwencloud'},{token:answer},{done:true}].map(p=>JSON.stringify(p)).join('\n')+'\n'});
  }else await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(history)});
 });
 await page.getByRole('button',{name:fa['Ask copilot'],exact:true}).click();
 await page.getByText('کارجو سابقهٔ توسعهٔ خدمات پایتون دارد.',{exact:false}).waitFor();
 assert.equal(requestBody.language,'fa');assert(/[\u0600-\u06ff]/.test(requestBody.instructions));
 assert((await page.locator('.chat-markdown a').last().innerText()).includes('صفحه'));
 await page.unroute('**/api/chat**');
 await page.getByRole('button',{name:fa['Review CV'],exact:true}).click();
 await page.locator('.toast').waitFor({state:'hidden'});
 await page.screenshot({path:path.join(output,'fa-copilot.png'),fullPage:true});
 checks.push('Persian HR tasks, default restoration, language-aware chat request and Persian source labels');

 const loginContext=await browser.newContext({viewport:{width:1440,height:1000}});const login=await loginContext.newPage();
 await login.goto('http://127.0.0.1:3000');await login.getByRole('button',{name:'Switch to Persian',exact:true}).click();
 await login.getByRole('heading',{name:fa['A clearer perspective awaits.'],exact:true}).waitFor();
 assert.equal(await login.getByLabel(fa['Username'],{exact:true}).count(),1);
 await login.screenshot({path:path.join(output,'fa-login.png'),fullPage:true});
 await login.getByRole('button',{name:fa['Open workspace'],exact:true}).click();
 assert(/[\u0600-\u06ff]/.test(await login.locator('input[autocomplete=username]').evaluate(el=>el.validationMessage)),'Native required-field validation is Persian');
 await login.getByLabel(fa['Username'],{exact:true}).fill('not-a-real-user');
 await login.getByLabel(fa['Password'],{exact:true}).fill('synthetic-invalid-password');
 await login.getByRole('button',{name:fa['Open workspace'],exact:true}).click();
 await login.locator('.notice').waitFor();
 const errorText=await login.locator('.notice').innerText();assert(/[\u0600-\u06ff]/.test(errorText)&&!/[A-Za-z]{3}/.test(errorText));
 await login.goto('http://127.0.0.1:3000/page-that-does-not-exist');
 await login.getByRole('heading',{name:fa['Page not found'],exact:true}).waitFor();
 await login.goto('http://127.0.0.1:3000/api/docs');
 assert((await login.title()).includes('راهنمای'));
 await loginContext.close();
 checks.push('Fully Persian sign-in screen and accessible translated account labels');
 checks.push('Persian form validation, authentication error, not-found page and API guide');
 await page.getByRole('button',{name:fa['Switch to English'],exact:true}).click();
 await page.locator('html[lang=en][dir=ltr]').waitFor();
}
