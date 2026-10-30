'use client';
import {useI18n,LanguageToggle,AIText,useAITranslation} from './i18n';
import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BrainCircuit, ArrowUpRight, Trash2, Send, Square, RotateCcw } from 'lucide-react';
import { Button, Field, Notice } from './components';
import { api, Item } from './lib';
function ChatAnswer({ text, sources = [] }: {
    text: string;
    sources?: Item[];
}) {
    const { t, tx, locale, setLocale } = useI18n();
    const translated=useAITranslation(text,true,sources.map(s=>s.candidate).filter(Boolean));
    const linked = translated.text.replace(/\[S(\d+)\]/g, (label, n) => {
        const source = sources.find(s => s.source_id === `S${n}`);
        return source ? `[${source.candidate} · ${t('p.')} ${t(String(source.page))}](/api/documents/${source.document_id}/original#page=${source.page})` : label;
    });
    return <div className="chat-markdown"><ReactMarkdown disallowedElements={['img']} remarkPlugins={[remarkGfm]} components={{ a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer"/> }}>{linked}</ReactMarkdown></div>;
}
export default function Copilot({ projectId, candidateId, candidateIds, notify, initialPrompt = '' }: {
    projectId: string;
    candidateId?: string;
    candidateIds?: string[];
    notify: (s: string) => void;
    initialPrompt?: string;
}) {
    const { t, tx, locale, setLocale } = useI18n();
    const [messages, setMessages] = useState<Item[]>([]);
    const [prompt, setPrompt] = useState(initialPrompt);
    const [playbook, setPlaybook] = useState<Item | null>(null);
    const [instructions, setInstructions] = useState('');
    const [candidates, setCandidates] = useState<Item[]>([]);
    const [selected, setSelected] = useState('');
    const [taskId, setTaskId] = useState('review');
    const [busy, setBusy] = useState(false), [answer, setAnswer] = useState(''), [sources, setSources] = useState<Item[]>([]), [info, setInfo] = useState<Item>({}), [elapsed, setElapsed] = useState(0);
    const controller = useRef<AbortController | null>(null), end = useRef<HTMLDivElement>(null), composer = useRef<HTMLTextAreaElement>(null);
    const comparison = !!candidateIds?.length;
    const activeCandidate = candidateId || (comparison || selected === 'all' ? undefined : selected || undefined);
    const scope = candidateIds?.join(',') || '';
    const historyUrl = '/chat?project_id=' + projectId + (activeCandidate ? '&candidate_id=' + activeCandidate : '') + (scope ? '&candidate_ids=' + scope : '');
    const currentScope = useRef(historyUrl);
    currentScope.current = historyUrl;
    const ready = !!projectId && !!playbook && (!!activeCandidate || comparison || selected === 'all') && candidates.length > 0;
    const multiple = comparison || selected === 'all';
    const taskPrompt = useCallback((task: Item) => multiple && task.comparison_prompt ? task.comparison_prompt : task.prompt, [multiple]);
    useEffect(() => {
        const abort = new AbortController();
        setCandidates([]);
        setSelected('');
        if (!projectId)
            return;
        Promise.all([api('/chat/playbook', { signal: abort.signal }), api('/candidates?project_id=' + projectId, { signal: abort.signal })]).then(([book, rows]) => {
            setPlaybook({...book,answer_instructions:t(book.answer_instructions),tasks:book.tasks.map((task:Item)=>({...task,label:t(task.label),comparison_label:task.comparison_label?t(task.comparison_label):undefined,prompt:t(task.prompt),comparison_prompt:task.comparison_prompt?t(task.comparison_prompt):undefined}))});
            setInstructions(t(book.answer_instructions));
            setCandidates(rows);
            setSelected([...rows].sort((a, b) => a.name.localeCompare(b.name,locale))[0]?.id || '');
        }).catch(e => { if (e.name !== 'AbortError')
            notify(e.message); });
        return () => abort.abort();
    }, [projectId,locale]);
    const load = useCallback(async (url: string, signal?: AbortSignal) => {
        const rows = await api(url, { signal });
        if (currentScope.current === url)
            setMessages(rows);
    }, []);
    useEffect(() => {
        setMessages([]);
        setAnswer('');
        setSources([]);
        setInfo({});
        setTaskId('review');
        const abort = new AbortController();
        if (ready)
            load(historyUrl, abort.signal).catch(e => { if (e.name !== 'AbortError')
                notify(e.message); });
        return () => { abort.abort(); controller.current?.abort(); };
    }, [historyUrl, ready, load]);
    useEffect(() => {
        if (playbook)
            setPrompt(t(initialPrompt || taskPrompt(playbook.tasks[0])));
    }, [playbook, historyUrl, initialPrompt, taskPrompt]);
    useEffect(() => { end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [answer, messages.length]);
    useEffect(() => {
        if (!busy)
            return;
        const started = Date.now();
        setElapsed(0);
        const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
        return () => clearInterval(timer);
    }, [busy]);
    const ask = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!ready || !prompt.trim() || busy)
            return;
        const q = prompt, url = historyUrl;
        setPrompt('');
        setTaskId('');
        setBusy(true);
        setAnswer('');
        setSources([]);
        setInfo({});
        setMessages(m => [...m, { id: 'pending', role: 'user', content: q }]);
        const abort = new AbortController();
        controller.current = abort;
        try {
            const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-TalentIQ-Request': '1', 'X-TalentIQ-Language':locale }, body: JSON.stringify({ project_id: projectId, query: q, language:locale, candidate_id: activeCandidate === 'all' ? null : activeCandidate || null, candidate_ids: candidateIds || null, instructions }), signal: abort.signal });
            if (!response.ok) {
                const d = await response.json();
                throw new Error(d.detail || 'The assistant could not start.');
            }
            const reader = response.body!.getReader(), decoder = new TextDecoder();
            let buffer = '';
            const packet = (line: string) => {
                if (!line.trim() || currentScope.current !== url)
                    return;
                const d = JSON.parse(line);
                if (d.token)
                    setAnswer(a => a + d.token);
                if (d.sources)
                    setSources(d.sources);
                if (d.coverage || d.status)
                    setInfo(old=>({...old,...d}));
                if (d.error)
                    throw new Error(d.error);
            };
            for (;;) {
                const { value, done } = await reader.read();
                if (done)
                    break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                lines.forEach(packet);
            }
            buffer += decoder.decode();
            if (buffer.trim())
                packet(buffer);
        }
        catch (e) {
            abort.abort();
            if ((e as Error).name !== 'AbortError') {
                notify((e as Error).message);
                if (currentScope.current === url)
                    setPrompt(q);
            }
        }
        finally {
            try {
                if (currentScope.current === url)
                    await load(url);
            }
            catch (e) {
                notify((e as Error).message);
            }
            if (controller.current === abort) {
                setBusy(false);
                setAnswer('');
                setSources([]);
                controller.current = null;
            }
        }
    };
    return <div className="copilot">
  <div className="copilot-heading"><span className="engine-symbol"><BrainCircuit size={20}/></span><div><h3>{tx("Recruitment copilot")}</h3><p>{tx("Review CVs, check role requirements and prepare for interviews.")}</p></div><Button variant="ghost" disabled={busy || !messages.length} onClick={async () => { try {
        await api('/chat?project_id=' + projectId, { method: 'DELETE' });
        setMessages([]);
    }
    catch (e) {
        notify((e as Error).message);
    } }}><Trash2 size={14}/>{tx("Clear project chat")}</Button></div>
  <div className="hr-review-toolbar">
   {tx(!candidateId && !comparison ? <Field label={t("Candidate")}><select aria-label={t("Candidate to review")} value={selected} disabled={busy || !projectId || !candidates.length} onChange={e => setSelected(e.target.value)}>{tx(!candidates.length && <option value="">{tx("Import CVs to begin")}</option>)}{tx([...candidates].sort((a, b) => a.name.localeCompare(b.name,locale)).map(c => <option key={c.id} value={c.id}>{tx(c.name)}</option>))}{tx(candidates.length > 1 && <option value="all">{tx("All ")}{tx(candidates.length)}{tx(" candidates")}</option>)}</select></Field> : <p className="hr-review-scope">{tx(comparison ? `Comparing ${candidateIds!.length} candidates` : candidates.find(c => c.id === candidateId)?.name || 'Selected candidate')}<span>{tx("CV evidence and this role's requirements")}</span></p>)}
   <div className="hr-task-list" role="group" aria-label={t("HR tasks")}>{tx(playbook?.tasks.map((task: Item) => <button type="button" key={task.id} aria-pressed={taskId === task.id} disabled={busy || !ready} onClick={() => { setTaskId(task.id); setPrompt(taskPrompt(task)); composer.current?.focus(); }}>{tx(multiple && task.comparison_label ? task.comparison_label : task.label)}</button>))}</div>
  </div>
  <details className="hr-instructions"><summary>{tx("HR instructions \u00B7 ready to use")}</summary><p>{tx("These instructions are included automatically. Adjust the answer style if needed.")}</p><Field label={t("Answer instructions")}><textarea rows={3} maxLength={2000} value={instructions} disabled={busy || !playbook} onChange={e => setInstructions(e.target.value)}/></Field><Button variant="ghost" disabled={busy || !playbook} onClick={() => setInstructions(playbook!.answer_instructions)}><RotateCcw size={13}/>{tx("Restore default instructions")}</Button></details>
  {tx(selected === 'all' && candidates.length > 6 && <Notice>{tx("For a detailed comparison, choose up to six CVs in Comparisons. Large selections may use excerpts.")}</Notice>)}
  <div className="chat-messages">
   {tx(!messages.length && !busy && <div className="hr-chat-welcome"><h3>{tx(!candidates.length ? 'Import CVs to get started' : 'Your first review is ready')}</h3><p>{tx(!candidates.length ? 'Add candidates to this recruitment project, then return here.' : 'Choose a task above, edit the question if needed, then select Ask copilot. Each answer links to the CV evidence.')}</p></div>)}
   {tx(messages.map((m, i) => <div className={`chat-message ${m.role}`} key={m.id || i}><span>{tx(m.role === 'user' ? 'YOU' : m.legacy ? 'EARLIER ANSWER · RECHECK AGAINST THE CV' : 'AI · CV EVIDENCE')}</span>{tx(m.role === 'assistant' && !m.legacy && m.sources?.[0]?.chat_model && <p className="small muted">{tx(m.sources[0].chat_model)}{tx(" \u00B7 ")}{tx(m.sources[0].coverage_complete ? 'All selected CV pages' : 'Focused excerpts')}</p>)}{m.role==='assistant'&&m.sources?.[0]?.answer_checked&&<p className="small muted">{t('Answer checked against CV sources')}</p>}<ChatAnswer text={m.content} sources={m.sources}/>{tx(m.role === 'assistant' && m.sources?.filter((s: Item) => s.document_id).length > 0 && <details><summary>{tx(m.sources.filter((s: Item) => s.document_id).length)}{tx(" source pages")}</summary>{tx(m.sources.filter((s: Item) => s.document_id).map((s: Item, n: number) => <a key={n} href={`/api/documents/${s.document_id}/original#page=${s.page}`} target="_blank" rel="noreferrer">{tx(s.candidate)}{tx(" \u00B7 p. ")}{tx(s.page)}<ArrowUpRight size={12}/></a>))}</details>)}</div>))}
   {tx(busy && <div className="chat-message assistant" role="status"><span>{tx("AI REVIEW \u00B7 ")}{tx(elapsed)}{tx("s")}</span>{tx(info.coverage && <p className="small muted">{tx(info.coverage.complete ? 'Reading all selected CV pages.' : 'Using focused excerpts; other details may be in the original CV.')}</p>)}<ChatAnswer text={answer || t(info.checking?'Checking the answer against the CV sources':'Reading the CV and preparing a draft…')} sources={sources}/></div>)}<div ref={end}/>
  </div>
  <form className="chat-compose hr-compose" onSubmit={ask}><label htmlFor={`hr-question-${candidateId || 'project'}`}>{tx("Your question")}</label><textarea id={`hr-question-${candidateId || 'project'}`} ref={composer} aria-label={t("Message recruitment copilot")} value={prompt} maxLength={2000} onChange={e => { setPrompt(e.target.value); setTaskId(''); }} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        e.currentTarget.form?.requestSubmit();
    } }} placeholder={t(projectId ? 'Ask a follow-up or choose a task above…' : 'Select a project to begin')} disabled={!ready || busy} rows={4}/><div className="hr-compose-actions"><span>{tx("You can edit this question before sending.")}</span>{tx(busy ? <Button type="button" onClick={() => controller.current?.abort()}><Square size={15}/>{tx("Stop generation")}</Button> : <Button type="submit" variant="primary" disabled={!ready || !prompt.trim()}><Send size={16}/><span>{tx("Ask copilot")}</span></Button>)}</div></form>
  <p className="small muted">{tx("CV claims need human verification. You make the hiring decision.")}</p>
 </div>;
}
