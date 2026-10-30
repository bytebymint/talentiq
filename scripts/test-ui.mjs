// Browser tests use only synthetic documents in an isolated temporary workspace.
import { chromium, expect } from '@playwright/test';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';

const root=process.cwd();
const temp=await mkdtemp(path.join(os.tmpdir(),'talentiq-ui-'));
const output=path.join(root,'test-results');await mkdir(output,{recursive:true});
const python=process.env.TALENTIQ_PYTHON||path.join(root,'.venv','Scripts','python.exe');
const children=[];let browser;let backendLog='',frontendLog='';
const errors=[];const checks=[];const externalRequests=[];
async function waitFor(url){for(let i=0;i<60;i++){try{if((await fetch(url)).ok)return;}catch{}await new Promise(r=>setTimeout(r,500));}throw new Error('Server did not become ready: '+url);}
for(const port of [8000,3000]){try{await fetch(`http://127.0.0.1:${port}`,{signal:AbortSignal.timeout(1000)});throw new Error(`Port ${port} is in use. Stop the existing TalentIQ instance before browser QA.`);}catch(e){if(e.message.includes('is in use'))throw e;}}
try{
 const backend=spawn(python,['-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000','--no-access-log'],{cwd:root,env:{...process.env,TALENTIQ_DATA_DIR:path.join(temp,'data'),TALENTIQ_AUTO_WARM:'0',TALENTIQ_AI_PROVIDER:'local',TALENTIQ_OLLAMA_URL:'http://127.0.0.1:11435'},windowsHide:true});children.push(backend);backend.stdout.on('data',d=>backendLog+=d);backend.stderr.on('data',d=>backendLog+=d);
 const frontend=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000'],{cwd:root,env:{...process.env,NEXT_TELEMETRY_DISABLED:'1'},windowsHide:true});children.push(frontend);frontend.stdout.on('data',d=>frontendLog+=d);frontend.stderr.on('data',d=>frontendLog+=d);
 await Promise.all([waitFor('http://127.0.0.1:8000/api/health'),waitFor('http://127.0.0.1:3000')]);
 browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});context.on('request',request=>{const url=new URL(request.url());if(url.protocol.startsWith('http')&&!['127.0.0.1','localhost'].includes(url.hostname))externalRequests.push(url.origin);});const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:3000');await page.getByLabel('Your name').fill('Synthetic QA Reviewer');await page.getByLabel('Username',{exact:true}).fill('synthetic-ui-admin');await page.getByLabel('Password',{exact:true}).fill('synthetic-ui-password-123');await page.getByRole('button',{name:'Create local workspace'}).click();await page.getByRole('heading',{name:'A clearer view of your next hire.'}).waitFor();checks.push('First-run administrator setup and authenticated overview');
 await page.screenshot({path:path.join(output,'overview-empty.png'),fullPage:true});
 await page.getByRole('button',{name:'Create your first profile',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.getByLabel('Profile name *',{exact:true}).fill('Synthetic Python Engineer');await dialog.getByLabel('Job title *',{exact:true}).fill('Python Engineer');await dialog.getByLabel('Department',{exact:true}).fill('Engineering');await dialog.getByLabel('Job description',{exact:true}).fill('Synthetic test role. Build and maintain Python production services.');await dialog.getByRole('button',{name:'Continue'}).click();await dialog.getByRole('button',{name:'Add requirement'}).click();await dialog.getByLabel('Description',{exact:true}).fill('Documented Python service development');await dialog.getByRole('button',{name:'Continue'}).click();await dialog.getByRole('spinbutton',{name:'Relevant experience weight',exact:true}).fill('35');await dialog.getByRole('button',{name:'Continue'}).click();await dialog.getByText('Enabled weights must total exactly 100%.',{exact:true}).last().waitFor();await dialog.getByRole('spinbutton',{name:'Relevant experience weight',exact:true}).fill('30');await page.screenshot({path:path.join(output,'profile-builder.png'),fullPage:true});await dialog.getByRole('button',{name:'Continue'}).click();await dialog.getByRole('button',{name:'Continue'}).click();await dialog.getByRole('button',{name:'Save profile'}).click();await dialog.waitFor({state:'hidden'});checks.push('Profile wizard, required requirement, weight validation, save');
 await page.getByRole('button',{name:'Recruitment Projects',exact:true}).click();await page.getByRole('button',{name:'New project',exact:true}).click();await page.getByLabel('Project name *').fill('Synthetic engineering recruitment');await page.getByRole('button',{name:'Create project',exact:true}).last().click();await page.getByRole('heading',{name:'Synthetic engineering recruitment',exact:true,level:1}).waitFor();checks.push('Recruitment project creation and profile assignment');
 await page.getByRole('button',{name:'Overview',exact:true}).first().click();await page.getByRole('button',{name:'Upload CVs',exact:true}).waitFor();assert(await page.getByLabel('Hiring project').inputValue());checks.push('Guided HR home moves from role setup to adding CVs');
 await page.getByRole('button',{name:'Recruitment Projects',exact:true}).click();
 execFileSync(python,['-c',`import fitz,sys\nfrom pathlib import Path\nfor name in ['Synthetic Candidate A','Synthetic Candidate B']:\n p=fitz.open();page=p.new_page();page.insert_text((60,70),name+'\\nSynthetic test resume only.\\nBuilt production services using Python.\\nComputer Science degree documented.');p.save(str(Path(sys.argv[1])/(name+'.pdf')));p.close()`,temp]);
 await page.getByRole('button',{name:'Import resumes',exact:true}).click();await page.locator('input[type=file][accept=".pdf,.docx,.zip"]').setInputFiles([path.join(temp,'Synthetic Candidate A.pdf'),path.join(temp,'Synthetic Candidate B.pdf')]);await page.getByRole('dialog').getByRole('button',{name:'Import resumes',exact:true}).click();await page.getByText('Imported and parsed',{exact:false}).first().waitFor();await page.getByRole('dialog').getByText('2 finished',{exact:true}).waitFor();await page.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();checks.push('Multi-PDF upload with actual parsing and progress');
 execFileSync(python,['-m','scripts.seed-ui-evaluations'],{cwd:root,env:{...process.env,TALENTIQ_DATA_DIR:path.join(temp,'data'),TALENTIQ_TEST_FIXTURE:'1'}});
 await page.reload();await page.getByRole('button',{name:'Candidate Library',exact:true}).click();await page.getByRole('button',{name:'Add Synthetic Candidate A to shortlist',exact:true}).click();await page.getByRole('button',{name:'Remove Synthetic Candidate A from shortlist',exact:true}).waitFor();
 await page.getByRole('button',{name:/Synthetic Candidate A Built production Python services/}).click();await page.getByRole('dialog').getByText('SYNTHETIC BROWSER TEST FIXTURE',{exact:false}).waitFor();await page.screenshot({path:path.join(output,'candidate-intelligence-synthetic.png'),fullPage:true});await page.getByRole('dialog').getByRole('button',{name:/Built production services using Python/}).first().click();await page.getByRole('dialog',{name:'Source evidence'}).getByRole('blockquote').waitFor();await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),1,'Escape must only close the topmost dialog');checks.push('Annotated evaluation, evidence dialog, nested Escape/focus behavior');await page.getByRole('dialog').getByRole('button',{name:'Human review',exact:true}).click();
 const humanPanel=page.getByRole('dialog');
 await humanPanel.getByRole('group',{name:'Human hiring decision'}).getByRole('button',{name:/^Hold/}).click();
 await humanPanel.getByLabel('Internal reviewer note').fill('Synthetic retry: preserve this reviewer rationale.');
 await page.route('**/api/candidates/*',async route=>{if(route.request().method()==='PATCH')await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic temporary save failure'})});else await route.continue();});
 await humanPanel.getByRole('button',{name:'Save human review',exact:true}).click();await page.getByText('Synthetic temporary save failure',{exact:true}).waitFor();
 await expect(humanPanel.getByLabel('Internal reviewer note')).toHaveValue('Synthetic retry: preserve this reviewer rationale.');
 await page.unroute('**/api/candidates/*');checks.push('Failed human review save preserves the draft rationale for retry');
 for(const outcome of [{label:'Hire',stage:'Hired'},{label:'Hold',stage:'On Hold'},{label:'Reject',stage:'Not Selected'}]){
  await humanPanel.getByRole('button',{name:outcome.label,exact:false}).filter({has:page.locator('strong')}).click();
  assert.equal(await humanPanel.getByLabel('Pipeline stage',{exact:true}).inputValue(),outcome.stage);
  if(outcome.stage!=='On Hold')assert(await humanPanel.getByRole('button',{name:'Save human review',exact:true}).isDisabled());
  await humanPanel.getByLabel('Internal reviewer note').fill('Synthetic human decision: '+outcome.label+'. Source evidence reviewed.');
  if(outcome.stage!=='On Hold')await humanPanel.getByRole('checkbox',{name:'I confirm this final decision as a human reviewer. A rationale note is required.',exact:true}).check();
  await humanPanel.getByRole('button',{name:'Save human review',exact:true}).click();
  await expect(humanPanel.getByLabel('Internal reviewer note')).toHaveValue('');
  await humanPanel.getByText('Synthetic human decision: '+outcome.label+'. Source evidence reviewed.',{exact:true}).waitFor();
  const recorded=(await (await context.request.get('http://127.0.0.1:3000/api/candidates')).json()).find(c=>c.name==='Synthetic Candidate A');assert.equal(recorded.status,outcome.stage);
 }
 await page.screenshot({path:path.join(output,'human-hiring-decision-synthetic.png'),fullPage:true});
 await humanPanel.getByLabel('Pipeline stage',{exact:true}).selectOption('Under HR Review');
 checks.push('Human Hire/Hold/Reject controls, final confirmation, rationale and persisted outcomes');
 await page.getByLabel('Internal reviewer note').fill('Synthetic QA: verify project architecture during the interview.');await page.getByRole('button',{name:'Save human review',exact:true}).click();await expect(page.getByLabel('Internal reviewer note')).toHaveValue('');await page.getByText('Synthetic QA: verify project architecture during the interview.',{exact:true}).waitFor();await page.getByRole('dialog').getByRole('button',{name:'Close dialog'}).click();checks.push('Manual shortlist and persistent human notes');
 await page.getByRole('checkbox',{name:'Select Synthetic Candidate A',exact:true}).check();await page.getByRole('checkbox',{name:'Select Synthetic Candidate B',exact:true}).check();await page.getByRole('button',{name:'Compare',exact:true}).click();await page.getByRole('heading',{name:'Candidate comparisons',exact:true}).waitFor();await page.getByRole('button',{name:'Save session',exact:true}).click();await page.getByLabel('Session name').fill('Synthetic QA comparison');await page.getByRole('button',{name:'Save comparison',exact:true}).click();checks.push('Side-by-side candidate comparison and saved session');
 await page.getByRole('button',{name:'Candidate Library',exact:true}).click();
 await page.getByRole('button',{name:/Synthetic Candidate B Built production Python services/}).click();
 await page.getByText('Checked against CV sources',{exact:true}).waitFor();
 await page.getByText('Synthetic CV states Python services and a Computer Science degree.',{exact:true}).waitFor();
 await page.getByText('Demonstrated in work or projects',{exact:true}).waitFor();
 await page.getByRole('dialog').getByRole('button',{name:/CV source/}).first().click();
 await page.getByRole('dialog',{name:'Source evidence'}).getByRole('blockquote').waitFor();await page.keyboard.press('Escape');
 await page.screenshot({path:path.join(output,'checked-cv-brief-synthetic.png'),fullPage:true});
 await page.getByRole('button',{name:'Check role match',exact:true}).click();await page.getByText('SYNTHETIC BROWSER TEST FIXTURE',{exact:false}).waitFor();
 await page.getByRole('dialog').getByRole('button',{name:'Close dialog'}).click();
 await page.getByRole('button',{name:'Comparisons',exact:true}).click();
 checks.push('Checked CV brief, demonstrated skills, missing employment, source evidence and role-match navigation');
 // Synthetic chat transport isolates UI/schema wiring; real-model checks run separately.
 let comparisonIds=[];let syntheticHistory=[];
 await page.route('**/api/chat**',async route=>{
  if(new URL(route.request().url()).pathname.endsWith('/playbook')){await route.continue();return;}
  if(route.request().method()==='POST'){
   const body=route.request().postDataJSON();comparisonIds=body.candidate_ids;
   assert(body.instructions.includes('plain HR language'),'HR guidance must accompany the request');
   const sources=[{source_id:'S1',candidate:'Synthetic Candidate A',candidate_id:comparisonIds[0],document_id:'synthetic-doc',page:1,chat_model:'SYNTHETIC UI FIXTURE',coverage_complete:true,answer_seconds:2,answer_checked:true}];
   const answer='**Documented comparison**\n\n| Candidate | Evidence |\n| --- | --- |\n| Synthetic A | Python services [S1] |\n\n![Untrusted remote image](https://example.invalid/leak?fixture=synthetic)';
   syntheticHistory=[{id:'synthetic-user',role:'user',content:body.query,sources:[]},{id:'synthetic-answer',role:'assistant',content:answer,sources,legacy:false}];
   await route.fulfill({status:200,contentType:'application/x-ndjson',body:[{sources,coverage:{complete:true},model:'SYNTHETIC UI FIXTURE'},{token:answer},{done:true}].map(v=>JSON.stringify(v)).join('\n')+'\n'});
  }else await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(syntheticHistory)});
 });
 await page.getByRole('button',{name:'Discuss these candidates with AI',exact:true}).click();
 await page.getByRole('button',{name:'Compare CVs',exact:true}).waitFor();
 assert((await page.getByLabel('Message recruitment copilot').inputValue()).includes('Compare'),'Comparison question is prefilled');
 await page.getByText('HR instructions · ready to use',{exact:true}).click();
 assert((await page.getByLabel('Answer instructions').inputValue()).includes('plain HR language'));
 await page.getByRole('button',{name:'Interview questions',exact:true}).click();
 assert((await page.getByLabel('Message recruitment copilot').inputValue()).includes('five focused interview questions'));
 await page.getByRole('button',{name:'Hiring review',exact:true}).click();
 assert((await page.getByLabel('Message recruitment copilot').inputValue()).includes('evidence for my hiring decision'));
 await page.getByRole('button',{name:'Compare CVs',exact:true}).click();
 checks.push('Prefilled HR instructions, comparison prompt and editable interview-question task');
 await page.getByLabel('Message recruitment copilot').fill('Compare these candidates and cite their CVs.');
 await page.getByRole('button',{name:'Ask copilot',exact:true}).click();
 await page.getByText('SYNTHETIC UI FIXTURE · All selected CV pages',{exact:true}).waitFor();
 await page.getByText('Answer checked against CV sources',{exact:true}).waitFor();
 assert.equal(comparisonIds.length,2,'Comparison must send both selected candidate IDs');
 assert.equal(await page.locator('.chat-markdown table').count(),1,'Markdown comparison table must render');
 assert.equal(await page.getByRole('link',{name:'Synthetic Candidate A · p. 1',exact:true}).count(),1,'Inline citation must link to the original page');
 await page.unroute('**/api/chat**');checks.push('Selected comparison IDs, rendered Markdown table, inline source-page link and model/coverage metadata');
 await page.getByRole('button',{name:'Talent Search',exact:true}).click();
 await page.getByRole('button',{name:'Recruitment copilot',exact:true}).click();
 const candidatePicker=page.getByLabel('Candidate to review');await candidatePicker.waitFor();
 await page.getByRole('button',{name:'Review CV',exact:true}).waitFor();
 assert((await page.getByLabel('Message recruitment copilot').inputValue()).includes('HR review'));
 await page.locator('.toast').waitFor({state:'hidden'});
 await page.screenshot({path:path.join(output,'hr-copilot-ready.png'),fullPage:true});
 const candidateOptions=await candidatePicker.locator('option').evaluateAll(options=>options.map(o=>({value:o.value,text:o.textContent})));
 const secondCandidate=candidateOptions.filter(o=>o.value!=='all')[1];await candidatePicker.selectOption(secondCandidate.value);
 await page.getByRole('button',{name:'Work experience',exact:true}).click();
 assert((await page.getByLabel('Message recruitment copilot').inputValue()).includes('employer, job title, dates'));
 await candidatePicker.selectOption('all');
 await page.getByRole('button',{name:'Compare CVs',exact:true}).waitFor();
 assert.equal(await page.locator('.chat-message').count(),0,'Candidate-scoped history does not leak into the project conversation');
 checks.push('Candidate picker, ready CV-review question, work-history task and isolated all-candidate history');

 await page.getByRole('button',{name:'Resume Folders',exact:true}).click();await page.getByRole('button',{name:'New folder',exact:true}).click();await page.getByLabel('Folder name').fill('Synthetic QA folder');await page.getByRole('button',{name:'Save folder',exact:true}).click();await page.getByRole('checkbox',{name:'Select Synthetic Candidate A.pdf',exact:true}).check();await page.getByRole('button',{name:'Move to folder',exact:false}).click();const dest=page.getByLabel('Destination folder');await dest.selectOption({label:'Synthetic QA folder'});await page.getByRole('button',{name:'Move 1 documents',exact:true}).click();await page.getByRole('button',{name:'Synthetic QA folder 1',exact:true}).click();await page.getByRole('button',{name:'Preview Synthetic Candidate A.pdf',exact:true}).click();await page.getByRole('button',{name:'Extracted text',exact:true}).click();await page.getByText('Built production services using Python.',{exact:false}).waitFor();await page.getByRole('dialog').getByRole('button',{name:'Close dialog'}).click();checks.push('Internal folder creation, bulk move, original and extracted-text preview');
 await page.getByRole('button',{name:'AI Workspace',exact:true}).click();await page.getByRole('heading',{name:'AI workspace',exact:true}).waitFor();await page.getByText('Intelligence, waiting to connect.',{exact:true}).waitFor();await page.screenshot({path:path.join(output,'ai-workspace-offline.png'),fullPage:true});checks.push('Truthful Ollama offline state and setup instructions');
 await page.route('**/api/events',route=>route.abort());
 const seedProgress=state=>execFileSync(python,['-m','scripts.seed-ui-job',state],{cwd:root,env:{...process.env,TALENTIQ_DATA_DIR:path.join(temp,'data'),TALENTIQ_TEST_FIXTURE:'1'}});
 seedProgress('processing');await page.reload();await page.getByText('SYNTHETIC STATUS CHECK PROCESSING',{exact:true}).waitFor();
 seedProgress('completed');await page.getByText('SYNTHETIC STATUS CHECK COMPLETED',{exact:true}).waitFor({timeout:8000});
 await page.unroute('**/api/events');checks.push('Live completion updates without page reload when EventSource is unavailable');

 await page.keyboard.press('Control+k');await page.getByRole('dialog').getByLabel('Command search').fill('Candidate Library');await page.getByRole('dialog').getByRole('button',{name:'Candidate Library',exact:true}).click();checks.push('Ctrl+K command palette and navigation');
 await page.reload();await page.getByRole('button',{name:'Remove Synthetic Candidate A from shortlist',exact:true}).waitFor();checks.push('Browser refresh restores project, candidates, shortlist');
 for(const size of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:390,height:844}]){
  await page.setViewportSize(size);for(const route of ['Overview','Recruitment Projects','Candidate Library','Resume Folders','Talent Search','AI Workspace','Candidate Rankings','Comparisons','Recruitment Analytics','Recruitment Profiles','Activity & Audit','Settings']){await page.getByRole('button',{name:route,exact:true}).first().click();await page.waitForTimeout(60);assert(await page.locator('main').isVisible(),route);const dims=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));assert(dims.scroll<=dims.width+1,`${route}: overflow at ${size.width}: ${JSON.stringify(dims)}`);}checks.push(`12 screens render without document overflow at ${size.width}×${size.height}`);
 }
 await page.getByRole('button',{name:'Overview',exact:true}).click();await page.screenshot({path:path.join(output,'overview-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.getByRole('button',{name:'Switch to dark theme'}).click();await page.getByRole('button',{name:'Overview',exact:true}).click();await page.screenshot({path:path.join(output,'overview-dark.png'),fullPage:true});await page.getByRole('button',{name:'Switch to light theme'}).click();await page.screenshot({path:path.join(output,'overview-with-synthetic-fixtures.png'),fullPage:true});checks.push('Light/dark theme switching and reduced-motion browser rendering');
 await page.getByRole('button',{name:'Switch to dark theme'}).click();
 for(const size of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:390,height:844}]){
  await page.setViewportSize(size);for(const route of ['Overview','Recruitment Projects','Candidate Library','Resume Folders','Talent Search','AI Workspace','Candidate Rankings','Comparisons','Recruitment Analytics','Recruitment Profiles','Activity & Audit','Settings']){await page.getByRole('button',{name:route,exact:true}).first().click();await page.waitForTimeout(60);const dims=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));assert(dims.scroll<=dims.width+1,`${route}: dark overflow at ${size.width}`);}checks.push(`12 dark-theme screens render without document overflow at ${size.width}×${size.height}`);
 }

 const providerConfig=await (await context.request.get('http://127.0.0.1:3000/api/settings')).json();
 await context.request.put('http://127.0.0.1:3000/api/settings',{headers:{'X-TalentIQ-Request':'1'},data:{...providerConfig,provider:'unconfigured'}});
 await page.setViewportSize({width:1440,height:1000});await page.reload();
 await page.getByRole('heading',{name:'Where should TalentIQ run intelligence?',exact:true}).waitFor();
 assert.equal(await page.getByRole('heading',{name:'Local models',exact:true}).count(),0,'No local controls before provider choice');
 await page.getByRole('button',{name:/Third-party API · QwenCloud/}).click();
 await page.getByLabel('QwenCloud API key',{exact:true}).fill('synthetic-browser-contract-key');
 await page.getByRole('button',{name:'Use QwenCloud',exact:true}).click();
 await page.getByText('Local AI disabled',{exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Start AI',exact:true}).count(),0);
 assert.equal(await page.getByRole('button',{name:'Download model',exact:true}).count(),0);
 assert.equal(await page.getByLabel('QwenCloud API key',{exact:true}).inputValue(),'');
 const safeConfig=await (await context.request.get('http://127.0.0.1:3000/api/settings')).text();
 assert(!safeConfig.includes('synthetic-browser-contract-key'),'Saved key must not return to the browser');
 await page.screenshot({path:path.join(output,'qwencloud-provider-synthetic.png'),fullPage:true});
 checks.push('First AI-provider choice, cloud disclosure, write-only key and cloud UI without local model controls');
 const {checkFarsi}=await import('./fa-ui-checks.mjs');await checkFarsi({page,context,browser,output,checks});
 await page.getByRole('button',{name:'Settings',exact:true}).first().click();await page.getByRole('button',{name:'Account',exact:true}).click();
 const account=page.getByRole('form',{name:'Account sign-in settings'});
 await account.getByLabel('Username',{exact:true}).fill('synthetic-updated-admin');
 await account.getByLabel('Current password',{exact:true}).fill('synthetic-wrong-password');
 await account.getByRole('button',{name:'Save sign-in details',exact:true}).click();await account.getByText('Current password is incorrect.',{exact:true}).waitFor();
 await account.getByLabel('Current password',{exact:true}).fill('synthetic-ui-password-123');
 await account.getByLabel('New password',{exact:true}).fill('synthetic-updated-password-456');await account.getByLabel('Confirm new password',{exact:true}).fill('synthetic-different-password-789');
 await account.getByRole('button',{name:'Save sign-in details',exact:true}).click();await account.getByText('The new passwords do not match.',{exact:true}).waitFor();
 await account.getByLabel('Confirm new password',{exact:true}).fill('synthetic-updated-password-456');await account.getByRole('button',{name:'Save sign-in details',exact:true}).click();
 await account.getByText('Your sign-in details were updated. You are still signed in; other sessions have been signed out.',{exact:true}).waitFor();
 for(const label of ['Current password','New password','Confirm new password'])await expect(account.getByLabel(label,{exact:true})).toHaveValue('');
 assert.equal((await (await context.request.get('http://127.0.0.1:3000/api/auth/me')).json()).username,'synthetic-updated-admin');
 await page.screenshot({path:path.join(output,'account-settings-synthetic.png'),fullPage:true});
 const faAccount=JSON.parse(await readFile('app/fa.json','utf8'));
 await page.getByRole('button',{name:'Switch to Persian',exact:true}).click();await page.getByRole('heading',{name:faAccount['Account'],exact:true}).waitFor();
 for(const size of [{width:1440,height:1000},{width:390,height:844}]){await page.setViewportSize(size);await page.getByLabel(faAccount['Current password'],{exact:true}).waitFor();const dims=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));assert(dims.scroll<=dims.width+1,'Persian account form fits');}
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:path.join(output,'fa-account-settings-synthetic.png'),fullPage:true});
 await page.getByRole('button',{name:faAccount['Switch to English'],exact:true}).click();
 await context.request.post('http://127.0.0.1:3000/api/auth/logout',{headers:{'X-TalentIQ-Request':'1'}});await page.reload();
 await page.getByLabel('Username',{exact:true}).fill('synthetic-updated-admin');await page.getByLabel('Password',{exact:true}).fill('synthetic-updated-password-456');await page.getByRole('button',{name:'Open workspace',exact:true}).click();await page.getByRole('button',{name:'Settings',exact:true}).first().waitFor();
 checks.push('Account form, current-password errors, confirmation mismatch, saved username/password, cleared secret fields and fresh sign-in');
 checks.push('Persian account settings and password labels fit desktop and mobile');
 assert.equal(errors.length,0,'Browser errors: '+errors.join('\n'));assert.equal(externalRequests.length,0,'Unexpected external browser requests: '+externalRequests.join(', '));checks.push('No external browser asset, font, analytics, or API requests during normal workflows');
 const apiContext=context.request;const response=await apiContext.get('http://127.0.0.1:3000/api/projects');const projects=await response.json();const report=await apiContext.get(`http://127.0.0.1:3000/api/reports/${projects[0].id}?format=pdf&kind=comparison`);assert(report.ok());assert((await report.body()).subarray(0,5).toString()==='%PDF-');checks.push('Authenticated report download through frontend proxy');
 await writeFile(path.join(output,'ui-results.json'),JSON.stringify({syntheticFixturesOnly:true,checks,browserErrors:errors},null,2));console.log(checks.map(s=>'PASS '+s).join('\n'));
}catch(error){console.error(error);console.error('BACKEND:',backendLog.slice(-5000));console.error('FRONTEND:',frontendLog.slice(-5000));process.exitCode=1;}
finally{if(browser)await browser.close();for(const child of children)child.kill();await new Promise(r=>setTimeout(r,500));await writeFile(path.join(output,'ui-server-logs.txt'),backendLog+'\n'+frontendLog);}

