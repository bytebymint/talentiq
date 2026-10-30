'use client';
import {useI18n,LanguageToggle,AIText,useAITranslation} from './i18n';
import { useState, useEffect, useRef, useCallback } from 'react';
import { LayoutDashboard, BriefcaseBusiness, Users, FolderOpen, Search, BrainCircuit, ListOrdered, Columns3, ChartNoAxesCombined, SlidersHorizontal, History, Settings, PanelLeftClose, PanelLeftOpen, Command, ChevronDown, ChevronRight, ArrowUpRight, ArrowRight, Plus, Upload, ShieldCheck, Sparkles, Sun, Moon, LogOut, FileText, Check, Play, Pause, Square, Power, Download, RefreshCw, Trash2, Copy, Archive, FolderPlus, ArrowLeft, MessageSquare, Send, CheckCircle2, Clock3, AlertCircle, MoreHorizontal, X, FileUp, LoaderCircle, LockKeyhole, HardDrive, Keyboard, CheckCheck, Filter, GitCompareArrows, Bell, UserRound } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api, send, Item, fmt, bytes, stages } from './lib';
import {uploadResume} from './uploads';
import { Button, Badge, Empty, Field, Modal, Notice, Score, PageHead } from './components';
import ProfileBuilder from './profile-builder';
import {HRDesk,HRReviewGuide} from './hr-desk';
import { AIWorkspace, FolderExplorer, CandidateDetail, DocumentPreview, Comparisons, TalentSearch, Analytics, Activity, SettingsPage } from './workspaces';
const nav: [
    string,
    [
        string,
        string,
        LucideIcon
    ][]
][] = [['WORKSPACE', [['overview', 'Overview', LayoutDashboard], ['projects', 'Recruitment Projects', BriefcaseBusiness], ['candidates', 'Candidate Library', Users], ['folders', 'Resume Folders', FolderOpen], ['search', 'Talent Search', Search]]], ['INTELLIGENCE', [['ai', 'AI Workspace', BrainCircuit], ['rankings', 'Candidate Rankings', ListOrdered], ['comparisons', 'Comparisons', Columns3], ['analytics', 'Recruitment Analytics', ChartNoAxesCombined]]], ['MANAGEMENT', [['profiles', 'Recruitment Profiles', SlidersHorizontal], ['activity', 'Activity & Audit', History], ['settings', 'Settings', Settings]]]];
const titles = Object.fromEntries(nav.flatMap(([, items]) => items.map(([id, title]) => [id, title])));
const emptyData = { projects: [], profiles: [], candidates: [], documents: [], folders: [], audit: [], jobs: [], analytics: { candidates: 0, evaluated: 0, shortlisted: 0, needs_review: 0, projects: 0, pipeline: {}, gaps: {}, skills: {}, score_distribution: {} } } as Record<string, any>;
export default function App() {
    const { t, tx, locale, setLocale } = useI18n();
    const [health, setHealth] = useState<Item | null>(null), [user, setUser] = useState<Item | null>(null), [data, setData] = useState(emptyData), [engine, setEngine] = useState<Item>({ state: 'checking', models: [], running: [] });
    const [page, setPage] = useState('overview'), [projectId, setProjectId] = useState(''), [collapsed, setCollapsed] = useState(false), [dark, setDark] = useState(false), [loading, setLoading] = useState(true), [backendError, setBackendError] = useState('');
    const [toast, setToast] = useState(''), [modal, setModal] = useState<string | null>(null), [editProfile, setEditProfile] = useState<Item | undefined>(), [candidate, setCandidate] = useState<Item | null>(null), [preview, setPreview] = useState<Item | null>(null), [evidence, setEvidence] = useState<Item | null>(null);
    const [busy, setBusy] = useState(''), [query, setQuery] = useState(''), [selection, setSelection] = useState<string[]>([]), [command, setCommand] = useState(false), [globalQuery, setGlobalQuery] = useState(''), [versions, setVersions] = useState<Item[] | null>(null), [confirmation, setConfirmation] = useState<{
        title: string;
        text: string;
        action: () => Promise<any>;
    } | null>(null);
    const [projectDraft, setProjectDraft] = useState<Item>({ name: '', department: '', profile_id: '' }), [editingProject, setEditingProject] = useState<Item | null>(null), [projectTab, setProjectTab] = useState('Overview');
    const profileImport = useRef<HTMLInputElement>(null);
    const projectRef = useRef(projectId);
    projectRef.current = projectId;
    const jobsRef = useRef<Item[]>([]);
    jobsRef.current = data.jobs;
    const providerPrompted = useRef(false);
    useEffect(() => { if (user && engine.provider === 'unconfigured' && !providerPrompted.current) {
        providerPrompted.current = true;
        navigate('ai');
    } }, [user, engine.provider]);
    const notify = useCallback((s: string) => { setToast(s); }, []);
    useEffect(() => { if (toast) {
        const id = setTimeout(() => setToast(''), 6500);
        return () => clearTimeout(id);
    } }, [toast]);
    const navigate = useCallback((p: string) => { setPage(p); setQuery(''); setProjectTab('Overview'); window.location.hash = p; }, []);
    useEffect(() => { setDark(localStorage.getItem('talentiq-theme') === 'dark'); setCollapsed(localStorage.getItem('talentiq-sidebar') === 'collapsed'); setProjectId(localStorage.getItem('talentiq-project') || ''); const p = window.location.hash.slice(1); if (titles[p])
        setPage(p); const hash = () => { const v = window.location.hash.slice(1); if (titles[v])
        setPage(v); }; window.addEventListener('hashchange', hash); return () => window.removeEventListener('hashchange', hash); }, []);
    useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('talentiq-theme', dark ? 'dark' : 'light'); }, [dark]);
    useEffect(() => { localStorage.setItem('talentiq-project', projectId); setSelection([]); setQuery(''); }, [projectId]);
    const refresh = useCallback(async () => { try {
        const keys = ['projects', 'profiles', 'candidates', 'documents', 'folders', 'audit', 'jobs', 'analytics'];
        const values = await Promise.all(keys.map(k => api('/' + k)));
        const result = Object.fromEntries(keys.map((k, i) => [k, values[i]]));
        setData(result);
        setBackendError('');
        if (projectRef.current && !result.projects.some((p: Item) => p.id === projectRef.current))
            setProjectId('');
        return result;
    }
    catch (e) {
        setBackendError((e as Error).message);
    }
    finally {
        setLoading(false);
    } }, []);
    const diagnostic = useCallback(async () => { try {
        setEngine(await api('/ai/status'));
    }
    catch (e) {
        notify((e as Error).message);
    } }, [notify]);
    const boot = useCallback(async () => { setLoading(true); try {
        const h = await api('/health');
        setHealth(h);
        if (!h.setup_required) {
            try {
                setUser(await api('/auth/me'));
            }
            catch {
                setUser(null);
            }
        }
        setBackendError('');
    }
    catch {
        setBackendError('TalentIQ cannot reach the local backend. Start it with Start-TalentIQ.ps1, then retry.');
    }
    finally {
        setLoading(false);
    } }, []);
    useEffect(() => { boot(); }, [boot]);
    useEffect(() => {
        if (!user)
            return;
        refresh();
        diagnostic();
        const stream = new EventSource('/api/events');
        let revision: number | undefined, lastEvent = 0, lastPoll = 0, polling = false, closed = false;
        const checkpoint = (rows: Item[]) => JSON.stringify(rows.map(j => [j.id, j.state, j.items.map((i: Item) => [i.candidate_id, i.state, i.index_state])]));
        const applyJobs = (rows: Item[]) => { const changed = checkpoint(rows) !== checkpoint(jobsRef.current); jobsRef.current = rows; setData(d => ({ ...d, jobs: rows })); return changed; };
        stream.onmessage = e => { try {
            const s = JSON.parse(e.data);
            if (!Array.isArray(s.jobs))
                throw new Error('Invalid progress event');
            lastEvent = Date.now();
            applyJobs(s.jobs);
            setEngine(old => ({ ...old, state: s.engine_state, pull: s.pull }));
            if (revision !== undefined && revision !== s.revision)
                refresh();
            revision = s.revision;
        }
        catch {
            lastEvent = 0;
        } };
        stream.addEventListener('heartbeat', () => { lastEvent = Date.now(); });
        stream.onerror = () => { lastEvent = 0; };
        const poll = async () => { const active = jobsRef.current.some(j => ['queued', 'processing', 'pausing', 'stopping'].includes(j.state)); if (closed || polling || Date.now() - lastEvent < 4500 || Date.now() - lastPoll < (active ? 2000 : 15000))
            return; polling = true; lastPoll = Date.now(); try {
            const rows = await api('/jobs');
            if (!closed) {
                if (applyJobs(rows))
                    await refresh();
            }
        }
        catch { /* EventSource reconnects; the next bounded poll retries. */ }
        finally {
            polling = false;
        } };
        const fallback = setInterval(poll, 2000), interval = setInterval(diagnostic, 15000);
        return () => { closed = true; stream.close(); clearInterval(fallback); clearInterval(interval); };
    }, [user, refresh, diagnostic]);
    useEffect(() => { const key = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommand(c => !c);
    } if (e.key === 'Escape') {
        setCommand(false);
    } if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'u') {
        e.preventDefault();
        setModal('upload');
    } }; document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key); }, []);
    const act = async (label: string, fn: () => Promise<any>, message?: string) => { setBusy(label); try {
        const result = await fn();
        if (message)
            notify(message);
        await refresh();
        return result;
    }
    catch (e) {
        notify((e as Error).message);
        return null;
    }
    finally {
        setBusy('');
    } };
    const openCandidate = async (c: Item) => { try {
        setCandidate(await api('/candidates/' + c.id));
    }
    catch (e) {
        notify((e as Error).message);
    } };
    const review = async (c: Item, changes: Item) => { const updated = await act('review', () => send('/candidates/' + c.id, changes, 'PATCH'), 'Review saved.'); if (updated) {
        setCandidate(current=>current?.id===c.id?updated:current);
    } return updated; };
    const selectProject = (id: string) => { setProjectId(id); };
    const project = data.projects.find((p: Item) => p.id === projectId), profile = data.profiles.find((p: Item) => p.id === project?.profile_id);
    const projectCandidates = data.candidates.filter((c: Item) => !projectId || c.project_id === projectId);
    const job = data.jobs.find((j: Item) => !projectId || j.project_id === projectId);
    const metrics = { candidates: projectCandidates.length, evaluated: projectCandidates.filter((c: Item) => c.evaluation).length, shortlisted: projectCandidates.filter((c: Item) => c.shortlisted).length, review: projectCandidates.filter((c: Item) => ['Needs Review', 'Under HR Review'].includes(c.status)).length };
    const requestDelete = (title: string, text: string, action: () => Promise<any>) => setConfirmation({ title, text, action });
    const createProject = () => { setEditingProject(null); setProjectDraft({ name: '', department: '', profile_id: data.profiles.find((p: Item) => !p.archived)?.id || '' }); setModal('project'); };
    const startAnalysis = async (ids?: string[], candidateProject?: string) => { const pid = candidateProject || projectId; if (!pid) {
        notify('Select a recruitment project first.');
        navigate('ai');
        return;
    } if (candidateProject)
        setProjectId(candidateProject); const result = await act('analysis', () => send('/jobs', { project_id: pid, ...(ids ? { candidate_ids: ids, reevaluate: true } : {}) }), 'Analysis queued. Progress is saved after each candidate.'); if (result)
        setCandidate(null); navigate('ai'); };
    const newProfile = () => { setEditProfile(undefined); setModal('profile'); };
    const canEdit = user?.role !== 'viewer';
    const exportMenu = (kind = 'rankings', ids?: string[]) => { if (!projectId) {
        notify('Select a project to export its report.');
        return;
    } setReportDraft({ kind, ids: ids || [] }); setModal('export'); };
    const [reportDraft, setReportDraft] = useState<{
        kind: string;
        ids: string[];
    }>({ kind: 'rankings', ids: [] });
    if (loading && !user)
        return <div className="boot"><Logo /><LoaderCircle size={24} className="spin"/><p>{tx("Opening your local workspace\u2026")}</p></div>;
    if (!user)
        return <Auth health={health} backendError={backendError} onRetry={boot} onSignedIn={u => { setUser(u); setHealth(h => ({ ...h, setup_required: false })); }}/>;
    const candidateTable = (shortlist = false, ranking = false) => <CandidateTable rows={projectCandidates} query={query} setQuery={setQuery} selection={selection} setSelection={setSelection} shortlist={shortlist} ranking={ranking} onOpen={openCandidate} onReview={review} canEdit={canEdit} onCompare={() => navigate('comparisons')} onExport={() => exportMenu(shortlist ? 'shortlist' : 'rankings')} onUpload={() => setModal('upload')} projectSelected={!!projectId}/>;
    const renderOverview = () => <><PageHead eyebrow={t("YOUR RECRUITMENT WORKSPACE")} title={t(`A clearer view of your next hire.`)} description={t("Every candidate. Every qualification. One thoughtful decision at a time.")} actions={<><Button onClick={() => setModal('upload')} disabled={!canEdit}><Upload size={16}/>{tx("Import resumes")}</Button><Button variant="primary" onClick={createProject} disabled={!canEdit}><Plus size={17}/>{tx("New project")}</Button></>}/>
  <HRDesk profiles={data.profiles} projects={data.projects} projectId={projectId} candidates={data.candidates} jobs={data.jobs} canEdit={canEdit} onProject={selectProject} onProfile={newProfile} onNewProject={createProject} onUpload={()=>setModal('upload')} onAnalyze={()=>startAnalysis(projectCandidates.filter((c:Item)=>!c.cv_brief||c.stale).map((c:Item)=>c.id))} onNavigate={navigate}/><div className="privacy-strip"><span><ShieldCheck size={15}/>{tx("Private by design")}</span><p>{tx(engine.provider === 'qwencloud' ? 'AI tasks use QwenCloud in Singapore. Originals stay in your workspace.' : engine.provider === 'local' ? 'Your resumes and AI processing stay on this computer.' : 'Choose Local AI or QwenCloud to control where AI processing runs.')}</p><button onClick={() => navigate('ai')}>{tx("AI Workspace ")}<ArrowUpRight size={14}/></button></div>
  <div className="metrics">{tx([[Users, 'Candidates', metrics.candidates, 'In your talent workspace'], [BriefcaseBusiness, 'Active projects', data.projects.filter((p: Item) => !p.archived).length, 'Hiring, with intention'], [CheckCheck, 'AI evaluations', metrics.evaluated, `${metrics.candidates ? Math.round(metrics.evaluated / metrics.candidates * 100) : 0}% of candidates evaluated`], [CheckCircle2, 'Human shortlist', metrics.shortlisted, `${metrics.review} awaiting human review`]].map(([Icon, label, value, detail]: any, i) => <button className="metric" key={label} onClick={() => { if (i === 1)
        navigate('projects');
    else {
        navigate(i === 2 ? 'rankings' : 'candidates');
        if (i === 3)
            setProjectTab('Shortlist');
    } }}><div className="metric-label">{tx(label)}<Icon size={16}/></div><strong>{tx(value.toLocaleString(locale==='fa'?'fa-IR-u-ca-persian':'en-GB'))}</strong><div className="metric-detail">{tx(detail)}<ArrowUpRight size={13}/></div></button>))}</div>
  {tx(data.projects.length === 0 ? <div className="welcome-panel"><div className="welcome-copy"><Badge tone="violet"><Sparkles size={12}/>{tx("A MORE CONSIDERED WAY TO HIRE")}</Badge><h2>{tx("Great hiring starts")}<br />{tx("with a clear perspective.")}</h2><p>{tx("Turn a folder of resumes into a structured, evidence-led view of your talent. Your judgment stays at the center.")}</p><Button variant="primary" onClick={newProfile} disabled={!canEdit}>{tx("Create your first profile")}<ArrowRight size={16}/></Button><span className="small muted">{tx("Local AI or QwenCloud. Your choice.")}</span></div><div className="onboarding-list"><div className="row between"><strong>{tx("Your workspace, in four steps")}</strong><span className="small muted">{tx([data.profiles.length > 0, data.projects.length > 0, data.documents.length > 0, engine.state === 'ready'].filter(Boolean).length)}{tx("/4 ready")}</span></div>{tx([[data.profiles.length > 0, 'Define the role', 'Create a reusable recruitment profile', newProfile], [data.projects.length > 0, 'Open a hiring project', 'Keep each recruitment process organized', createProject], [data.documents.length > 0, 'Bring your resumes', 'Import PDF, DOCX, or a resume folder', () => setModal('upload')], [engine.state === 'ready', 'Connect local intelligence', 'Check Ollama and select your models', () => navigate('ai')]].map(([done, title, desc, action]: any, i) => <button key={title} onClick={action} className="onboarding-step"><span className={done ? 'done' : ''}>{tx(done ? <Check size={16}/> : String(i + 1).padStart(2, '0'))}</span><div><strong>{tx(title)}</strong><p>{tx(desc)}</p></div><ChevronRight size={16}/></button>))}</div></div> : null)}
  <div className="dashboard-grid"><section className="panel projects-panel"><div className="panel-head"><div><h3>{tx("Active recruitment projects ")}<span className="count">{tx(data.projects.filter((p: Item) => !p.archived).length)}</span></h3><p>{tx("The roles moving your team forward.")}</p></div><button className="text-button" onClick={() => navigate('projects')}>{tx("View all")}<ArrowRight size={14}/></button></div>{tx(!data.projects.filter((p: Item) => !p.archived).length ? <Empty title={t("A home for every hiring process")} description={t("Create a project and bring its profile, resumes, and reviews together.")} action={<Button variant="ghost" onClick={createProject}>{tx("Create a project")}<Plus size={14}/></Button>}/> : <div className="project-list">{tx(data.projects.filter((p: Item) => !p.archived).slice(0, 4).map((p: Item) => <button key={p.id} className="project-list-row" onClick={() => { selectProject(p.id); navigate('projects'); setProjectTab('Candidates'); }}><span className="role-icon"><BriefcaseBusiness size={20}/></span><div><strong>{tx(p.name)}</strong><p>{tx(p.profile_name)}</p></div><div className="project-list-count"><strong>{tx(p.candidate_count)}</strong><span>{tx("candidates")}</span></div><Badge tone={p.job_state === 'processing' ? 'violet' : ''}>{tx(p.job_state || 'Open')}</Badge><ArrowUpRight size={16}/></button>))}</div>)}</section><HRReviewGuide/></div>
  <div className="dashboard-grid bottom-grid"><section className="panel"><div className="panel-head"><div><h3>{tx("Recent candidates")}</h3><p>{tx("A fresh perspective on your talent pool.")}</p></div><button className="text-button" onClick={() => navigate('candidates')}>{tx("View library")}<ArrowRight size={14}/></button></div>{tx(!data.candidates.length ? <div className="quiet-empty"><FileText size={24}/><span>{tx("Your next candidate will appear here.")}</span><button className="text-button" onClick={() => setModal('upload')}>{tx("Import resumes")}</button></div> : data.candidates.slice().sort((a: Item, b: Item) => b.created_at.localeCompare(a.created_at)).slice(0, 4).map((c: Item) => <button className="recent-row" key={c.id} onClick={() => openCandidate(c)}><div className="document-icon"><FileText size={18}/></div><div><strong>{tx(c.name)}</strong><p>{tx(c.status)}</p></div><Score value={c.score}/><ChevronRight size={15}/></button>))}</section><section className="panel"><div className="panel-head"><div><h3>{tx("Recruitment pipeline")}</h3><p>{tx("Progress guided by your team.")}</p></div><GitCompareArrows size={18} className="muted"/></div><div className="pipeline">{tx(['Imported', 'Needs Review', 'Shortlisted', 'Interview Scheduled', 'Hired'].map((s, i) => { const n = projectCandidates.filter((c: Item) => s === 'Shortlisted' ? c.shortlisted : c.status === s).length; return <button key={s} onClick={() => { navigate('candidates'); setQuery(s === 'Shortlisted' ? '' : s); if (s === 'Shortlisted')
        setProjectTab('Shortlist'); }}><span className="pipeline-dot" style={{ background: `var(--chart-${i})` }}/><span>{tx(s === 'Imported' ? 'Imported & pending' : s === 'Interview Scheduled' ? 'Interview' : s)}</span><strong>{tx(s === 'Imported' ? projectCandidates.filter((c: Item) => ['Imported', 'Pending Analysis'].includes(c.status)).length : n)}</strong><div><i style={{ width: `${metrics.candidates ? n / metrics.candidates * 100 : 0}%`, background: `var(--chart-${i})` }}/></div></button>; }))}</div></section></div><div className="workspace-foot"><span><LockKeyhole size={12}/>{tx("Local workspace \u00B7 Human decisions, supported by evidence")}</span><button onClick={() => setModal('shortcuts')}><Keyboard size={13}/>{tx("Keyboard shortcuts")}</button></div>
 </>;
    return <div className={`app-shell ${collapsed ? 'collapsed' : ''}`}><aside className="sidebar"><div className="brand-row"><Logo compact={collapsed}/><button className="icon-button collapse" title={t("Toggle sidebar")} aria-label={t("Toggle sidebar")} onClick={() => { setCollapsed(c => { localStorage.setItem('talentiq-sidebar', !c ? 'collapsed' : 'expanded'); return !c; }); }}>{tx(collapsed ? <PanelLeftOpen size={16}/> : <PanelLeftClose size={16}/>)}</button></div><button className="workspace-switch" onClick={() => { navigate('settings'); }} title={t("Workspace settings")}><span className="workspace-mark">{tx("T")}</span><div><strong>{tx("Talent workspace")}</strong><small>{tx("Local workspace")}</small></div><ChevronDown size={13}/></button><nav>{tx(nav.map(([section, items]) => <div className="nav-group" key={section}><p>{tx(section)}</p>{tx(items.map(([id, title, Icon]) => <button key={id} onClick={() => navigate(id)} className={page === id ? 'active' : ''} title={t(title)} aria-label={t(title)} aria-current={page === id ? 'page' : undefined}><Icon size={17}/><span>{tx(title)}</span>{tx(id === 'candidates' && data.candidates.length > 0 && <small>{tx(data.candidates.length)}</small>)}{tx(page === id && <i />)}</button>))}</div>))}</nav><div className="sidebar-bottom"><button className="sidebar-ai" onClick={() => navigate('ai')}><span className={`status-dot ${engine.online ? 'green' : ''}`}/><div><strong>{tx(engine.state === 'processing' ? 'AI processing' : engine.provider === 'qwencloud' ? 'QwenCloud · ' + engine.state : engine.provider === 'local' ? 'Local AI · ' + engine.state : 'Choose AI provider')}</strong><small>{tx(engine.provider === 'qwencloud' ? 'Cloud inference · Singapore' : engine.provider === 'local' ? 'Private, on this device' : 'Local or QwenCloud')}</small></div><ChevronRight size={14}/></button><div className="user-row"><span className="user-avatar"><UserRound size={17}/></span><button onClick={() => setModal('account')}><strong>{tx(user.name)}</strong><small>{tx(user.role === 'admin' ? 'Workspace administrator' : user.role)}</small></button><button className="icon-button" onClick={() => setDark(d => !d)} aria-label={t(dark ? 'Switch to light theme' : 'Switch to dark theme')} title={t("Change theme")}>{tx(dark ? <Sun size={17}/> : <Moon size={17}/>)}</button></div></div></aside>
 <div className="workspace-main"><header className="topbar"><div className="breadcrumbs"><span>{tx("Workspace")}</span><ChevronRight size={13}/><strong>{tx(titles[page])}</strong></div><div className="header-actions"><LanguageToggle/><button className="global-search" onClick={() => setCommand(true)}><Search size={15}/><span>{tx("Search anything\u2026")}</span><kbd>{tx("Ctrl K")}</kbd></button><span className="header-divider"/><button className="local-badge" onClick={() => navigate('ai')} title={t("Open AI diagnostics")}><span className={`status-dot ${engine.online ? 'green' : ''}`}/>{tx(engine.provider === 'qwencloud' ? 'QwenCloud' : engine.provider === 'local' ? 'Local AI' : 'Choose AI')}</button><button className="icon-button" aria-label={t("Recent activity")} title={t("Recent activity")} onClick={() => navigate('activity')}><Bell size={18}/>{tx(data.audit.length > 0 && <i className="notification-dot"/>)}</button></div></header>
 <main>{page!=='overview'&&<div className="context-row"><span><span className="context-dot"/>{tx("INTELLIGENCE BEHIND EVERY HIRE")}</span><select aria-label={t("Current recruitment project")} value={projectId} onChange={e => selectProject(e.target.value)}><option value="">{tx("All recruitment projects")}</option>{tx(data.projects.map((p: Item) => <option value={p.id} key={p.id}>{tx(p.name)}{tx(p.archived ? ' (archived)' : '')}</option>))}</select></div>}{tx(backendError && <Notice tone="danger">{tx(backendError)} <button className="text-button" onClick={refresh}>{tx("Retry connection")}</button></Notice>)}
 {tx(page === 'overview' && renderOverview())}
 {tx(page === 'projects' && <><PageHead eyebrow={t("PURPOSEFUL HIRING")} title={t(project ? project.name : 'Recruitment projects')} description={t(project ? `${project.profile_name} · ${project.department || 'Your local hiring workspace'}` : 'Give every open role a focused workspace, from first resume to final review.')} actions={<><Button onClick={newProfile} disabled={!canEdit}>{tx("Create profile")}</Button><Button variant="primary" onClick={createProject} disabled={!canEdit}><Plus size={16}/>{tx("New project")}</Button></>}/>{tx(project ? <><div className="tabs">{tx(['Overview', 'Candidates', 'AI Analysis', 'Rankings', 'Shortlist', 'Comparisons', 'Activity'].map(t => <button key={t} className={projectTab === t ? 'active' : ''} onClick={() => setProjectTab(t)}>{tx(t)}</button>))}<button className="tab-back" onClick={() => setProjectId('')}><ArrowLeft size={14}/>{tx("All projects")}</button></div>{tx(projectTab === 'Overview' && <div className="detail-grid"><section className="panel padded"><Badge tone="violet">{tx(project.archived ? 'Archived' : 'Active recruitment')}</Badge><h2>{tx(project.name)}</h2><p>{tx(profile?.config.description || 'The assigned profile defines this project’s requirements and weighted scoring rubric.')}</p><div className="mini-metrics"><div><strong>{tx(metrics.candidates)}</strong><span>{tx("Candidates")}</span></div><div><strong>{tx(metrics.evaluated)}</strong><span>{tx("Evaluated")}</span></div><div><strong>{tx(metrics.shortlisted)}</strong><span>{tx("Human shortlist")}</span></div></div><div className="actions"><Button variant="primary" onClick={() => setModal('upload')} disabled={!canEdit}><Upload size={16}/>{tx("Import resumes")}</Button><Button onClick={() => startAnalysis()} disabled={!canEdit || !metrics.candidates}>{tx("Start analysis")}<Play size={14}/></Button></div></section><section className="panel padded"><h3>{tx("Project configuration")}</h3><dl className="definition-list"><dt>{tx("Profile")}</dt><dd>{tx(profile?.name)}</dd><dt>{tx("Profile version")}</dt><dd>{tx("v")}{tx(profile?.version)}</dd><dt>{tx("Language model")}</dt><dd>{tx(profile?.config.model)}</dd><dt>{tx("Created")}</dt><dd>{tx(fmt(project.created_at))}</dd></dl><div className="stack"><Button disabled={!canEdit} onClick={() => { setEditingProject(project); setProjectDraft({ name: project.name, department: project.department, profile_id: project.profile_id }); setModal('project'); }}>{tx("Edit project")}</Button><Button onClick={() => exportMenu('summary')}>{tx("Export project summary")}</Button><Button disabled={!canEdit} variant="ghost" onClick={() => act('archive', () => send('/projects/' + project.id + '/archive'), project.archived ? 'Project reopened.' : 'Project archived.')}><Archive size={15}/>{tx(project.archived ? 'Reopen project' : 'Archive project')}</Button></div></section></div>)}{tx(['Candidates', 'Rankings', 'Shortlist'].includes(projectTab) && candidateTable(projectTab === 'Shortlist', projectTab === 'Rankings'))}{tx(projectTab === 'AI Analysis' && <AIWorkspace notify={notify} canConfigure={user.role === 'admin'} engine={engine} job={job} project={project} candidates={projectCandidates} busy={busy} canEdit={canEdit} onStart={() => startAnalysis()} onControl={action => act('control', () => send(`/jobs/${job.id}/${action}`))} onEngine={action => act('engine', async () => { await send('/ai/' + action); await diagnostic(); })} onRefresh={diagnostic} onPull={model => requestDelete('Download local model?', `Ollama will download ${model}. Model files may require several gigabytes and internet access.`, () => send('/ai/pull', { model, confirm_download: true }))}/>)}{tx(projectTab === 'Comparisons' && <Comparisons rows={projectCandidates} selection={selection} setSelection={setSelection} projectId={projectId} onOpen={openCandidate} onExport={() => exportMenu('comparison', selection)} notify={notify}/>)} {tx(projectTab === 'Activity' && <Activity items={data.audit.filter((a: Item) => a.project_id === projectId)}/>)}</> : <div className="project-grid">{tx(data.projects.length ? data.projects.map((p: Item) => <button className="project-card panel" key={p.id} onClick={() => { selectProject(p.id); setProjectTab('Overview'); }}><div className="row between"><span className="role-icon"><BriefcaseBusiness size={23}/></span><Badge tone={p.archived ? '' : 'success'}>{tx(p.archived ? 'Archived' : 'Active')}</Badge></div><h3>{tx(p.name)}</h3><p>{tx(p.profile_name)}</p><div className="project-card-progress"><span>{tx(p.evaluated)}{tx(" of ")}{tx(p.candidate_count)}{tx(" evaluated")}</span><strong>{tx(p.candidate_count ? Math.round(p.evaluated / p.candidate_count * 100) : 0)}{tx("%")}</strong></div><div className="progress"><i style={{ width: `${p.candidate_count ? p.evaluated / p.candidate_count * 100 : 0}%` }}/></div><footer><span>{tx(p.department || 'Recruitment')}</span><ArrowUpRight size={17}/></footer></button>) : <section className="panel full-span"><Empty title={t("Build a home for your next hire")} description={t("Create a recruitment profile first, then open a project to start collecting resumes.")} action={<Button variant="primary" onClick={data.profiles.length ? createProject : newProfile}>{tx(data.profiles.length ? 'Create project' : 'Create recruitment profile')}<ArrowRight size={16}/></Button>}/></section>)}</div>)}</>)}
 {tx(['candidates', 'rankings'].includes(page) && <><PageHead eyebrow={t(page === 'rankings' ? 'DOCUMENTED FIT, EXPLAINED' : 'YOUR TALENT, ORGANIZED')} title={t(page === 'rankings' ? 'Candidate rankings' : 'Candidate library')} description={t(page === 'rankings' ? 'Compare documented qualifications against a consistent rubric. Every score has a source.' : 'A complete view of the people in your recruitment workspace.')} actions={<><Button onClick={() => exportMenu(page === 'rankings' ? 'rankings' : 'summary')}><Download size={16}/>{tx("Export")}</Button><Button variant="primary" onClick={() => setModal('upload')} disabled={!canEdit}><Upload size={16}/>{tx("Import resumes")}</Button></>}/>{tx(page === 'rankings' && <Notice>{tx("Rankings assist human review. \u201CNot established\u201D means information is missing, not that a candidate lacks the qualification. ")}{tx(projectCandidates.some((c: Item) => c.stale) && <strong>{tx("Some evaluations use an older profile. Re-evaluate before comparing scores.")}</strong>)}</Notice>)}{tx(candidateTable(projectTab === 'Shortlist', page === 'rankings'))}</>)}
 {tx(page === 'folders' && <FolderExplorer data={data} projectId={projectId} canEdit={canEdit} onUpload={() => setModal('upload')} onPreview={setPreview} act={act} notify={notify} confirm={requestDelete}/>)}
 {tx(page === 'profiles' && <><PageHead eyebrow={t("CONSISTENCY STARTS HERE")} title={t("Recruitment profiles")} description={t("Your definition of a great fit. Reusable, weighted, and versioned.")} actions={<><Button onClick={() => profileImport.current?.click()} disabled={!canEdit}><FileUp size={15}/>{tx("Import JSON")}</Button><Button variant="primary" onClick={newProfile} disabled={!canEdit}><Plus size={16}/>{tx("Create profile")}</Button></>}/><input type="file" ref={profileImport} hidden accept=".json" onChange={async (e) => { const f = e.target.files?.[0]; if (f) {
        await act('import', async () => send('/profiles', JSON.parse(await f.text())), 'Profile imported.');
        e.target.value = '';
    } }}/>{tx(!data.profiles.length ? <section className="panel"><Empty title={t("A thoughtful rubric makes all the difference")} description={t("Define the role, choose legitimate requirements, and weight the qualifications that matter.")} action={<Button variant="primary" onClick={newProfile}>{tx("Create your first profile")}<ArrowRight size={16}/></Button>}/></section> : <div className="profile-grid">{tx(data.profiles.map((p: Item) => <section className="panel profile-card" key={p.id}><div className="row between"><span className="role-icon"><SlidersHorizontal size={21}/></span><Badge tone={p.archived ? '' : 'violet'}>{tx(p.archived ? 'Archived' : `Version ${p.version}`)}</Badge></div><h3>{tx(p.name)}</h3><p>{tx(p.config.job_title)}{tx(" \u00B7 ")}{tx(p.config.department || 'Recruitment')}</p><div className="weight-bar">{tx(p.config.criteria.filter((c: Item) => c.enabled).map((c: Item, i: number) => <i key={c.id} style={{ width: `${c.weight}%`, background: `var(--chart-${i % 6})` }} title={t(`${c.name} ${c.weight}%`)}/>))}</div><div className="profile-meta"><span>{tx(p.config.criteria.filter((c: Item) => c.enabled).length)}{tx(" scoring criteria")}</span><span>{tx(p.config.requirements.length)}{tx(" requirements")}</span></div><div className="profile-criteria">{tx(p.config.criteria.filter((c: Item) => c.enabled).map((c: Item) => <span key={c.id}>{tx(c.name)}<strong>{tx(c.weight)}{tx("%")}</strong></span>))}</div><div className="profile-actions"><Button onClick={() => { setEditProfile(p); setModal('profile'); }} disabled={!canEdit}>{tx("Edit profile")}<ArrowUpRight size={13}/></Button><button className="icon-button" title={t("Duplicate profile")} aria-label={t(`Duplicate ${p.name}`)} disabled={!canEdit} onClick={() => act('duplicate', () => send('/profiles/' + p.id + '/duplicate'), 'Profile duplicated.')}><Copy size={16}/></button><button className="icon-button" title={t("Version history")} aria-label={t(`Version history of ${p.name}`)} onClick={async () => { try {
        setVersions(await api('/profiles/' + p.id + '/versions'));
    }
    catch (e) {
        notify((e as Error).message);
    } }}><History size={16}/></button><button className="icon-button" title={t("Export profile JSON")} aria-label={t(`Export ${p.name}`)} onClick={() => downloadJson(p.config, p.name + '.json')}><Download size={16}/></button><button className="icon-button" title={t(p.archived ? 'Unarchive' : 'Archive')} aria-label={t(`${p.archived ? 'Unarchive' : 'Archive'} ${p.name}`)} disabled={!canEdit} onClick={() => act('archive', () => send('/profiles/' + p.id + '/archive'), 'Profile archive updated.')}><Archive size={16}/></button><button className="icon-button" title={t("Delete profile")} aria-label={t(`Delete ${p.name}`)} disabled={!canEdit} onClick={() => requestDelete('Delete recruitment profile?', `Permanently delete “${p.name}”? Profiles referenced by projects or evaluations must be archived instead.`, () => send('/profiles/' + p.id, undefined, 'DELETE'))}><Trash2 size={15}/></button></div></section>))}</div>)}</>)}
 {tx(page === 'ai' && <><PageHead eyebrow={t("PRIVATE INTELLIGENCE")} title={t("AI workspace")} description={t("A clear view of your AI provider, every request, and every saved checkpoint.")} actions={<Button onClick={diagnostic}><RefreshCw size={15}/>{tx("Refresh diagnostics")}</Button>}/><AIWorkspace notify={notify} canConfigure={user.role === 'admin'} engine={engine} job={job} project={project} candidates={projectCandidates} busy={busy} canEdit={canEdit} onStart={() => startAnalysis()} onControl={action => act('control', () => send(`/jobs/${job.id}/${action}`))} onEngine={action => act('engine', async () => { await send('/ai/' + action); await diagnostic(); })} onRefresh={diagnostic} onPull={model => requestDelete('Download local model?', `Ollama will download ${model}. This requires internet access and may use several gigabytes.`, () => send('/ai/pull', { model, confirm_download: true }))}/></>)}
 {tx(page === 'comparisons' && <><PageHead eyebrow={t("PERSPECTIVE, SIDE BY SIDE")} title={t("Candidate comparisons")} description={t("Look beyond a single number. Compare the documented evidence and the unanswered questions.")} actions={<Button onClick={() => exportMenu('comparison', selection)} disabled={selection.length < 2}><Download size={15}/>{tx("Export comparison")}</Button>}/><Comparisons rows={projectCandidates} selection={selection} setSelection={setSelection} projectId={projectId} onOpen={openCandidate} onExport={() => exportMenu('comparison', selection)} notify={notify}/></>)}
 {tx(page === 'search' && <TalentSearch projectId={projectId} onOpen={id => { const c = data.candidates.find((c: Item) => c.id === id); if (c)
        openCandidate(c); }} onEvidence={setEvidence} notify={notify}/>)}
 {tx(page === 'analytics' && <Analytics candidates={projectCandidates} jobs={data.jobs.filter((j: Item) => !projectId || j.project_id === projectId)} onExport={() => exportMenu('summary')}/>)}
 {tx(page === 'activity' && <><PageHead eyebrow={t("A TRACEABLE WORKSPACE")} title={t("Activity & audit history")} description={t("A chronological record of human reviews, application actions, and AI evaluations.")} actions={<Button onClick={() => exportMenu('activity')}><Download size={15}/>{tx("Export activity")}</Button>}/><Activity items={data.audit.filter((a: Item) => !projectId || a.project_id === projectId)}/></>)}
 {tx(page === 'settings' && <SettingsPage onUserUpdated={setUser} user={user} dark={dark} setDark={setDark} notify={notify} act={act} confirm={requestDelete} onRestored={() => { setUser(null); boot(); }}/>)}
 </main></div>
 {tx(toast && <div className="toast" role="status"><AlertCircle size={18}/><span>{tx(toast)}</span><button className="icon-button" aria-label={t("Dismiss notification")} onClick={() => setToast('')}><X size={15}/></button></div>)}
 {tx(modal === 'profile' && <ProfileBuilder provider={engine.provider} cloudModel={engine.cloud_model} profile={editProfile} onClose={() => setModal(null)} onSaved={refresh} notify={notify}/>)}
 {tx(modal === 'project' && <Modal title={t(editingProject ? 'Edit recruitment project' : 'A new hiring chapter')} subtitle={t("Connect a role profile to a focused recruitment workspace.")} onClose={() => setModal(null)}><form onSubmit={async (e) => { e.preventDefault(); const result = await act('project', () => send(editingProject ? '/projects/' + editingProject.id : '/projects', projectDraft, editingProject ? 'PUT' : 'POST'), editingProject ? 'Project updated.' : 'Project created.'); if (result) {
        selectProject(result.id);
        setModal(null);
        navigate('projects');
    } }}><div className="modal-body"><Field label={t("Project name *")}><input required autoFocus value={projectDraft.name} onChange={e => setProjectDraft(d => ({ ...d, name: e.target.value }))} placeholder={t("e.g. Software Engineer \u00B7 October recruitment")}/></Field><Field label={t("Department")}><input value={projectDraft.department} onChange={e => setProjectDraft(d => ({ ...d, department: e.target.value }))}/></Field><Field label={t("Recruitment profile *")}><select required value={projectDraft.profile_id} onChange={e => setProjectDraft(d => ({ ...d, profile_id: e.target.value }))}><option value="">{tx("Select a profile")}</option>{tx(data.profiles.filter((p: Item) => !p.archived).map((p: Item) => <option key={p.id} value={p.id}>{tx(p.name)}{tx(" \u00B7 v")}{tx(p.version)}</option>))}</select></Field>{tx(!data.profiles.some((p: Item) => !p.archived) && <Notice>{tx("Create a recruitment profile before opening a project. ")}<button type="button" className="text-button" onClick={newProfile}>{tx("Create profile")}<ArrowRight size={14}/></button></Notice>)}</div><footer className="modal-foot"><Button type="button" onClick={() => setModal(null)}>{tx("Cancel")}</Button><Button variant="primary" type="submit" busy={busy === 'project'} disabled={!projectDraft.profile_id}>{tx(editingProject ? 'Save changes' : 'Create project')}<ArrowRight size={15}/></Button></footer></form></Modal>)}
 {tx(modal === 'upload' && <UploadModal projects={data.projects} folders={data.folders} defaultProject={projectId} onClose={() => setModal(null)} onDone={refresh} notify={notify}/>)}
 {tx(candidate && <CandidateDetail candidate={candidate} projects={data.projects} canEdit={canEdit} onClose={() => setCandidate(null)} onReview={changes => review(candidate, changes)} onEvidence={setEvidence} onPreview={setPreview} onAnalyze={() => startAnalysis([candidate.id], candidate.project_id)} onDelete={() => requestDelete('Delete candidate and resumes?', `Permanently remove ${candidate.name}, their evaluations, reviewer notes, and original documents from this project?`, async () => { await send('/candidates/' + candidate.id, undefined, 'DELETE'); setCandidate(null); })} onReuse={pid => act('reuse', () => send('/candidates/' + candidate.id + '/reuse', { project_id: pid }), 'Candidate copied into the selected project; its reviews and evaluations are independent.')} notify={notify}/>)}
 {tx(preview && <DocumentPreview doc={preview} onClose={() => setPreview(null)}/>)}
 {tx(evidence && <Modal title={t("Source evidence")} subtitle={t(`Document ${evidence.document_id} · Page / text section ${evidence.page}`)} onClose={() => setEvidence(null)}><div className="modal-body"><blockquote>{tx(evidence.quote || evidence.text)}</blockquote><p className="muted small">{tx("This passage was retrieved from the imported document. Verify the underlying claim with the candidate.")}</p><Button onClick={() => { const d = data.documents.find((d: Item) => d.id === evidence.document_id); if (d) {
        setPreview({ ...d, page: evidence.page });
        setEvidence(null);
    }
    else
        notify('Source document no longer exists.'); }}>{tx("Open original at source")}<ArrowUpRight size={15}/></Button></div></Modal>)}
 {tx(confirmation && <Modal title={t(confirmation.title)} onClose={() => setConfirmation(null)}><div className="modal-body"><Notice tone="warning">{tx(confirmation.text)}</Notice></div><footer className="modal-foot"><Button onClick={() => setConfirmation(null)}>{tx("Cancel")}</Button><Button variant="danger" busy={busy === 'confirm'} onClick={async () => { const result = await act('confirm', confirmation.action, 'Action completed.'); if (result)
        setConfirmation(null); }}>{tx("Confirm")}</Button></footer></Modal>)}
 {tx(versions && <Modal title={t("Profile version history")} subtitle={t("Historical evaluations retain their original profile snapshot.")} onClose={() => setVersions(null)}><div className="modal-body stack">{tx(versions.map(v => <details key={v.id} className="version-row"><summary>{tx("Version ")}{tx(v.version)}{tx(" \u00B7 ")}{tx(fmt(v.created_at))}</summary><p>{tx(v.config.name)}</p>{tx(v.config.criteria.map((c: Item) => <p className="small" key={c.id}>{tx(c.name)}{tx(": ")}{tx(c.weight)}{tx("% ")}{tx(c.enabled ? '' : '(disabled)')}</p>))}<Button onClick={() => downloadJson(v.config, `profile-v${v.version}.json`)}>{tx("Export version")}<Download size={14}/></Button></details>))}</div></Modal>)}
 {tx(modal === 'export' && <Modal title={t("Export recruitment report")} subtitle={t("Reports include human review status and evaluation provenance.")} onClose={() => setModal(null)}><div className="modal-body"><Field label={t("Report type")}><select value={reportDraft.kind} onChange={e => setReportDraft(d => ({ ...d, kind: e.target.value }))}>{tx(['rankings', 'shortlist', 'candidate', 'comparison', 'summary', 'activity'].map(k => <option key={k} value={k}>{tx(k.charAt(0).toUpperCase() + k.slice(1))}</option>))}</select></Field><p className="muted">{tx(reportDraft.ids.length ? `${reportDraft.ids.length} selected candidates` : 'All applicable candidates in this project')}</p><div className="export-options">{tx([['pdf', 'PDF document'], ['xlsx', 'Excel workbook'], ['csv', 'CSV spreadsheet']].map(([ext, label]) => <a key={ext} className="button" href={`/api/reports/${projectId}?format=${ext}&kind=${reportDraft.kind}&candidate_ids=${reportDraft.ids.join(',')}`} download onClick={() => notify('Report generation requested. Your browser will download the file.')}><Download size={17}/>{tx(label)}</a>))}</div><Notice>{tx("PDF evaluation and comparison reports include criterion explanations and source passages. Candidate contact and administrative details are excluded.")}</Notice></div></Modal>)}
 {tx(command && <Modal title={t("Where would you like to go?")} subtitle={t("Search navigation, recruitment projects, profiles, and candidate names.")} onClose={() => { setCommand(false); setGlobalQuery(''); }}><div className="command-input"><Search size={19}/><input aria-label={t("Command search")} autoFocus placeholder={t("Search your workspace\u2026")} value={globalQuery} onChange={e => setGlobalQuery(e.target.value)}/><kbd>{tx("ESC")}</kbd></div><div className="command-results">{tx(nav.flatMap(([, items]) => items).filter(([, title]) => title.toLowerCase().includes(globalQuery.toLowerCase())).map(([id, title, Icon]) => <button key={id} onClick={() => { navigate(id); setCommand(false); setGlobalQuery(''); }}><Icon size={17}/><span>{tx(title)}</span><ArrowUpRight size={14}/></button>))}{tx(globalQuery && [...data.projects.map((p: Item) => ({ ...p, type: 'Project' })), ...data.profiles.map((p: Item) => ({ ...p, type: 'Profile' })), ...data.candidates.map((c: Item) => ({ ...c, type: 'Candidate' }))].filter((i: Item) => i.name.toLowerCase().includes(globalQuery.toLowerCase())).slice(0, 20).map((i: Item) => <button key={i.id} onClick={() => { if (i.type === 'Candidate')
        openCandidate(i);
    else if (i.type === 'Project') {
        setProjectId(i.id);
        navigate('projects');
    }
    else {
        setEditProfile(i);
        setModal('profile');
    } setCommand(false); }}><Search size={16}/><span>{tx(i.name)}</span><Badge>{tx(i.type)}</Badge></button>))}</div></Modal>)}
 {tx(modal === 'shortcuts' && <Modal title={t("A faster way around")} onClose={() => setModal(null)}><div className="modal-body shortcuts"><p><span>{tx("Search the workspace")}</span><kbd>{tx("Ctrl K")}</kbd></p><p><span>{tx("Import resumes")}</span><kbd>{tx("Ctrl Shift U")}</kbd></p><p><span>{tx("Close a dialog")}</span><kbd>{tx("Esc")}</kbd></p><p><span>{tx("Move between controls")}</span><kbd>{tx("Tab / Shift Tab")}</kbd></p></div></Modal>)}
 {tx(modal === 'account' && <Modal title={t("Your local account")} onClose={() => setModal(null)}><div className="modal-body"><h3>{tx(user.name)}</h3><p>{tx(user.username)}{tx(" \u00B7 ")}{tx(user.role)}</p><Notice>{tx("Your session expires after 12 hours. Authentication and workspace data stay on this computer.")}</Notice><Button onClick={async () => { await send('/auth/logout'); setUser(null); setModal(null); }}><LogOut size={16}/>{tx("Sign out")}</Button></div></Modal>)}
 </div>;
}
function Logo({compact=false}:{compact?:boolean}){const {locale}=useI18n();return <div className="logo"><span className="logo-symbol"><i/><i/><i/></span>{!compact&&(locale==='fa'?<span className="fa-brand">تلنت‌آی‌کیو<sup>®</sup></span>:<span>Talent<span>IQ</span><sup>®</sup></span>)}</div>}
function downloadJson(data: unknown, name: string) { const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
function Auth({ health, backendError, onRetry, onSignedIn }: {
    health: Item | null;
    backendError: string;
    onRetry: () => void;
    onSignedIn: (u: Item) => void;
}) {
    const { t, tx, locale, setLocale } = useI18n();
    const [error, setError] = useState(''), [busy, setBusy] = useState(false), [form, setForm] = useState({ name: '', username: '', password: '' });
    const setup = health?.setup_required;
    return <div className="auth-screen"><div className="auth-language"><LanguageToggle/></div><div className="auth-story"><Logo /><div><Badge tone="violet"><ShieldCheck size={13}/>{tx("LOCAL BY DESIGN")}</Badge><h1>{tx("Intelligence behind")}<br />{tx("every hire.")}</h1><p>{tx("A considered recruitment workspace.")}<br />{tx("Powered by your chosen AI. Guided by your judgment.")}</p><div className="auth-principles"><span><HardDrive size={17}/>{tx("Your data, on your device")}</span><span><FileText size={17}/>{tx("Evidence behind every assessment")}</span><span><Users size={17}/>{tx("Human decisions, always")}</span></div></div><small>{tx("TalentIQ \u00B7 Private recruitment intelligence")}</small></div><div className="auth-form"><div className="auth-card"><span className="eyebrow">{tx(setup ? 'YOUR WORKSPACE STARTS HERE' : 'WELCOME BACK')}</span><h2>{tx(setup ? 'Make room for your next great hire.' : 'A clearer perspective awaits.')}</h2><p>{tx(setup ? 'Create your local administrator account. This protects the resumes and reviews stored on this computer.' : 'Sign in to your private TalentIQ workspace.')}</p>{tx(backendError ? <Notice tone="danger">{tx(backendError)}<Button onClick={onRetry}><RefreshCw size={15}/>{tx("Retry backend")}</Button></Notice> : <form onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(''); try {
        onSignedIn(await send(setup ? '/auth/setup' : '/auth/login', setup ? form : { username: form.username, password: form.password }));
    }
    catch (e) {
        setError((e as Error).message);
    }
    finally {
        setBusy(false);
    } }}>{tx(setup && <Field label={t("Your name")}><input required autoComplete="name" value={form.name} minLength={2} onChange={e => setForm(d => ({ ...d, name: e.target.value }))} placeholder={t("How should we address you?")}/></Field>)}<Field label={t("Username")}><input required minLength={3} autoComplete="username" value={form.username} onChange={e => setForm(d => ({ ...d, username: e.target.value }))} placeholder={t("Your local username")}/></Field><Field label={t("Password")} hint={t(setup ? 'At least 12 characters. Keep this password safe; there is no cloud recovery.' : undefined)}><input required type="password" minLength={setup ? 12 : 1} autoComplete={setup ? 'new-password' : 'current-password'} value={form.password} onChange={e => setForm(d => ({ ...d, password: e.target.value }))} placeholder={t(setup ? 'Create a strong password' : 'Enter your password')}/></Field>{tx(error && <Notice tone="danger">{tx(error)}</Notice>)}<Button variant="primary full" type="submit" busy={busy}>{tx(setup ? 'Create local workspace' : 'Open workspace')}<ArrowRight size={17}/></Button></form>)}<div className="auth-private"><LockKeyhole size={13}/>{tx("Local accounts. Choose Local AI or QwenCloud.")}</div></div></div></div>;
}
function CandidateTable({ rows, query, setQuery, selection, setSelection, shortlist, ranking, onOpen, onReview, canEdit, onCompare, onExport, onUpload, projectSelected }: {
    rows: Item[];
    query: string;
    setQuery: (s: string) => void;
    selection: string[];
    setSelection: (s: string[]) => void;
    shortlist: boolean;
    ranking: boolean;
    onOpen: (c: Item) => void;
    onReview: (c: Item, d: Item) => void;
    canEdit: boolean;
    onCompare: () => void;
    onExport: () => void;
    onUpload: () => void;
    projectSelected: boolean;
}) {
    const { t, tx, locale, setLocale } = useI18n();
    const [filter, setFilter] = useState('All stages'), [top, setTop] = useState(0), [customTop, setCustomTop] = useState(10), [sort, setSort] = useState('score'), [asc, setAsc] = useState(false), [page, setPage] = useState(0);
    const pageSize = 15;
    const filtered = rows.filter(c => (!shortlist || c.shortlisted) && (filter === 'All stages' || c.status === filter) && `${c.name} ${c.status} ${c.evaluation?.result.facts.map((f: Item) => f.value).join(' ') || ''}`.toLowerCase().includes(query.toLowerCase()));
    let sorted = [...filtered].sort((a, b) => { let result = sort === 'score' ? (a.score === null ? 1 : b.score === null ? -1 : b.score - a.score) : sort === 'name' ? a.name.localeCompare(b.name) : a.status.localeCompare(b.status); if (result === 0)
        result = a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id); return asc ? -result : result; });
    if (ranking && top)
        sorted = sorted.slice(0, top === -1 ? customTop : top);
    const pageRows = sorted.slice(page * pageSize, (page + 1) * pageSize);
    useEffect(() => setPage(0), [query, filter, top, customTop, rows.length]);
    const toggle = (id: string) => setSelection(selection.includes(id) ? selection.filter(x => x !== id) : [...selection, id]);
    return <section className="panel table-panel"><div className="table-toolbar"><div className="table-search"><Search size={16}/><input placeholder={t("Search candidates, skills, or status\u2026")} aria-label={t("Search candidates")} value={query} onChange={e => setQuery(e.target.value)}/></div><div className="actions"><select aria-label={t("Filter by pipeline stage")} value={filter} onChange={e => setFilter(e.target.value)}><option value={"All stages"}>{tx("All stages")}</option>{tx(stages.map(s => <option key={s} value={s}>{tx(s)}</option>))}</select>{tx(ranking && <><select value={top} aria-label={t("Recommendation count")} onChange={e => setTop(Number(e.target.value))}><option value={0}>{tx("All candidates")}</option>{tx([5, 10, 20, 50].map(n => <option key={n} value={n}>{tx("Top ")}{tx(n)}</option>))}<option value={-1}>{tx("Custom")}</option></select>{tx(top === -1 && <input className="tiny-input" type="number" min={1} max={10000} value={customTop} aria-label={t("Custom recommendation count")} onChange={e => setCustomTop(Math.max(1, Number(e.target.value)))}/>)}</>)}</div></div>{tx(selection.length > 0 && <div className="selection-bar"><span>{tx(selection.length)}{tx(" selected")}</span><Button variant="ghost" onClick={onCompare} disabled={!projectSelected || selection.length < 2 || selection.length > 6}><Columns3 size={14}/>{tx("Compare")}</Button><Button variant="ghost" onClick={() => setSelection([])}>{tx("Clear selection")}</Button></div>)}
 {tx(!sorted.length ? <Empty title={t(rows.length ? 'No candidates match this view' : 'Your talent pool starts here')} description={t(rows.length ? 'Try another search, pipeline stage, or shortlist view.' : 'Import resumes to browse, evaluate, and review candidates in one place.')} action={!rows.length && canEdit ? <Button onClick={onUpload}><Upload size={15}/>{tx("Import resumes")}</Button> : <Button variant="ghost" onClick={() => { setQuery(''); setFilter('All stages'); }}>{tx("Clear filters")}</Button>}/> : <><div className="table-scroll"><table><thead><tr><th><input type="checkbox" aria-label={t("Select visible candidates")} checked={pageRows.length > 0 && pageRows.every(c => selection.includes(c.id))} onChange={e => setSelection(e.target.checked ? Array.from(new Set([...selection, ...pageRows.map(c => c.id)])) : selection.filter(id => !pageRows.some(c => c.id === id)))}/></th><th><button onClick={() => { if (sort === 'name')
        setAsc(!asc);
    else {
        setSort('name');
        setAsc(false);
    } }}>{tx("Candidate")}<ChevronDown size={12}/></button></th><th><button onClick={() => { if (sort === 'score')
        setAsc(!asc);
    else {
        setSort('score');
        setAsc(false);
    } }}>{tx("Documented match")}<ChevronDown size={12}/></button></th><th>{tx("Evidence coverage")}</th><th><button onClick={() => { if (sort === 'status')
        setAsc(!asc);
    else {
        setSort('status');
        setAsc(false);
    } }}>{tx("Human review")}<ChevronDown size={12}/></button></th><th>{tx("Shortlist")}</th><th /></tr></thead><tbody>{tx(pageRows.map((c, index) => <tr key={c.id} className={selection.includes(c.id) ? 'selected' : ''}><td><input type="checkbox" checked={selection.includes(c.id)} aria-label={t(`Select ${c.name}`)} onChange={() => toggle(c.id)}/></td><td><button className="candidate-cell" onClick={() => onOpen(c)}><span className="candidate-rank">{tx(ranking ? String(page * pageSize + index + 1).padStart(2, '0') : <FileText size={18}/>)}</span><span><strong>{tx(c.name)}</strong><small>{tx(c.evaluation ? c.evaluation.result.facts.find((f: Item) => f.kind === 'Employment')?.value || 'Evidence-based evaluation available' : c.documents[0]?.filename || 'Resume imported')}</small></span></button></td><td><div className="row"><Score value={c.score} coverage={c.coverage}/>{tx(c.stale && <Badge tone="warning">{tx("Older rubric")}</Badge>)}</div></td><td><span>{tx(c.evaluation ? `${c.coverage}% established` : 'Awaiting analysis')}</span></td><td><Badge tone={c.status === 'Hired' ? 'success' : c.status === 'Needs Review' ? 'warning' : ''}>{tx(c.status)}</Badge></td><td><button className={`shortlist-button ${c.shortlisted ? 'active' : ''}`} aria-label={t(`${c.shortlisted ? 'Remove' : 'Add'} ${c.name} ${c.shortlisted ? 'from' : 'to'} shortlist`)} disabled={!canEdit} onClick={() => onReview(c, { shortlisted: !c.shortlisted })}>{tx(c.shortlisted ? <Check size={15}/> : <Plus size={15}/>)}<span>{tx(c.shortlisted ? 'Shortlisted' : 'Add')}</span></button></td><td><button className="icon-button" aria-label={t(`Open ${c.name}`)} onClick={() => onOpen(c)}><ArrowUpRight size={17}/></button></td></tr>))}</tbody></table></div><div className="table-footer"><span>{tx(sorted.length)}{tx(" candidates \u00B7 ")}{tx(selection.length)}{tx(" selected")}</span><div className="actions"><Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>{tx("Previous")}</Button><span>{tx("Page ")}{tx(page + 1)}{tx(" / ")}{tx(Math.max(1, Math.ceil(sorted.length / pageSize)))}</span><Button variant="ghost" disabled={(page + 1) * pageSize >= sorted.length} onClick={() => setPage(page + 1)}>{tx("Next")}</Button></div></div></>)}
 </section>;
}
function UploadModal({ projects, folders, defaultProject, onClose, onDone, notify }: {
    projects: Item[];
    folders: Item[];
    defaultProject: string;
    onClose: () => void;
    onDone: () => void;
    notify: (s: string) => void;
}) {
    const { t, tx, locale, setLocale } = useI18n();
    const [pid, setPid] = useState(defaultProject || projects.find(p => !p.archived)?.id || ''), [fid, setFid] = useState(''), [files, setFiles] = useState<File[]>([]), [records, setRecords] = useState<Record<string, Item>>({}), [busy, setBusy] = useState(false), [drag, setDrag] = useState(false), [recursive, setRecursive] = useState(true);
    const fileInput = useRef<HTMLInputElement>(null), folderInput = useRef<HTMLInputElement>(null), abort = useRef<AbortController | null>(null);
    const add = (items: File[]) => { const supported = items.filter(f => /\.(pdf|docx|zip)$/i.test(f.name)); if (supported.length < items.length)
        notify(`${items.length - supported.length} unsupported files skipped. Choose PDF, DOCX, or ZIP.`); setFiles(old => Array.from(new Map([...old, ...supported].map(f => [(f.webkitRelativePath || f.name) + f.size, f])).values())); };
    const key = (f: File) => (f.webkitRelativePath || f.name) + f.size;
    const list = files.filter(f => recursive || !f.webkitRelativePath || f.webkitRelativePath.split('/').length <= 2);
    const setRecord = (f: File, value: Item) => setRecords(r => ({ ...r, [key(f)]: value }));
    const run = async () => { if (!pid)
        return; setBusy(true); for (const f of list) {
        if (records[key(f)]?.status === 'done')
            continue;
        setRecord(f, { status: 'preparing', progress: 0 });
        try {
            const controller=new AbortController();abort.current=controller;
            const result:Item=await uploadResume(f,pid,fid,controller.signal,()=>setRecord(f,{status:'uploading',progress:0}));
            const errors = result.results.filter((r: Item) => r.error);
            setRecord(f, { status: errors.length ? 'error' : 'done', progress: 100, results: result.results, error: errors.map((r: Item) => `${r.filename}: ${r.error}`).join('; ') });
        }
        catch (e) {
            setRecord(f, { status: 'error', error: (e as Error).message });
        }
        onDone();
    } abort.current = null; setBusy(false); };
    return <Modal title={t("Make room for new talent")} subtitle={t("Import original resumes. Original files are stored in your workspace. AI processing follows your selected provider.")} wide onClose={() => { if (!busy)
        onClose();
    else
        notify('Wait for the current import to finish before closing.'); }}><div className="modal-body"><div className="form-grid"><Field label={t("Recruitment project *")}><select value={pid} disabled={busy} onChange={e => setPid(e.target.value)}><option value="">{tx("Choose a project")}</option>{tx(projects.filter(p => !p.archived).map(p => <option key={p.id} value={p.id}>{tx(p.name)}</option>))}</select></Field><Field label={t("Internal destination folder")}><select value={fid} disabled={busy} onChange={e => setFid(e.target.value)}><option value="">{tx("Unfiled resumes")}</option>{tx(folders.map(f => <option key={f.id} value={f.id}>{tx(f.name)}</option>))}</select></Field></div>{tx(!projects.length && <Notice>{tx("Create a recruitment project before importing resumes.")}</Notice>)}<div className={`dropzone ${drag ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); if (!busy)
        add(Array.from(e.dataTransfer.files)); }}><div className="upload-art"><FileText size={23}/><Upload size={18}/></div><h3>{tx("A new perspective is one upload away.")}</h3><p>{tx("Drop resumes here, or choose files from your computer.")}</p><div className="actions"><Button disabled={busy} onClick={() => fileInput.current?.click()}><Plus size={15}/>{tx("Choose files")}</Button><Button disabled={busy} onClick={() => folderInput.current?.click()}><FolderOpen size={15}/>{tx("Choose folder")}</Button></div><small>{tx("PDF, DOCX, ZIP \u00B7 Up to 25 MB per file \u00B7 Secure duplicate detection")}</small><input type="file" multiple accept=".pdf,.docx,.zip" hidden ref={fileInput} onChange={e => { add(Array.from(e.target.files || [])); }}/><input type="file" multiple hidden ref={folderInput} {...({ webkitdirectory: '', directory: '' } as any)} onChange={e => { add(Array.from(e.target.files || [])); }}/></div><label className="check-label"><input type="checkbox" disabled={busy} checked={recursive} onChange={e => setRecursive(e.target.checked)}/>{tx("Include files in subfolders \u00B7 original folder structure is preserved internally")}</label>{tx(list.length > 0 && <div className="upload-list"><div className="row between"><strong>{tx(list.length)}{tx(" files selected")}</strong><span className="small muted">{tx(Object.values(records).filter(r => r.status === 'done').length)}{tx(" finished")}</span></div>{tx(list.map(f => { const r = records[key(f)]; return <div className="upload-row" key={key(f)}><FileText size={18}/><div><strong>{tx(f.webkitRelativePath || f.name)}</strong><small>{tx(bytes(f.size))}{tx(" \u00B7 ")}{tx(r?.status === 'done' ? r.results?.some((x: Item) => x.duplicate) ? 'Duplicate detected; original record retained' : 'Imported and parsed' : r?.status === 'preparing' ? 'Reading file…' : r?.status === 'parsing' ? 'Uploaded · parsing document' : r?.status === 'uploading' ? 'Uploading and reading resume…' : r?.status === 'error' ? r.error : 'Ready to import')}</small>{tx(r?.results?.flatMap((x: Item) => x.warnings || []).map((w: string, i: number) => <small className="text-warning" key={i}>{tx(w)}</small>))}{tx(r?.status === 'uploading' && <div className="progress"><i style={{ width: '100%', opacity: .4 }}/></div>)}</div>{tx(r?.status === 'done' ? <CheckCircle2 size={18} className="text-success"/> : r?.status === 'error' ? <AlertCircle size={18} className="text-danger"/> : ['preparing', 'uploading', 'parsing'].includes(r?.status) ? <LoaderCircle className="spin" size={18}/> : !busy ? <button className="icon-button" aria-label={t(`Remove ${f.name}`)} onClick={() => setFiles(files.filter(x => x !== f))}><X size={15}/></button> : null)}</div>; }))}</div>)}</div><footer className="modal-foot"><span className="small muted"><ShieldCheck size={13}/>{tx("Original files are preserved")}</span><div className="actions"><Button disabled={busy} onClick={onClose}>{tx("Close")}</Button><Button variant="primary" disabled={!pid || !list.length} busy={busy} onClick={run}><Upload size={16}/>{tx(Object.values(records).some(r => r.status === 'error') ? 'Retry failed imports' : 'Import resumes')}</Button></div></footer></Modal>;
}
