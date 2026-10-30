'use client';
import {useI18n,LanguageToggle,AIText,useAITranslation} from './i18n';
import { useEffect, useRef, useState, useId, isValidElement, cloneElement, ReactElement } from 'react';
import { X, ArrowRight, Inbox, LoaderCircle, Check, AlertCircle } from 'lucide-react';
export function Button({ children, variant = '', busy = false, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: string;
    busy?: boolean;
}) { const { t, tx, locale, setLocale } = useI18n(); return <button {...props} disabled={props.disabled || busy} className={`button ${variant} ${props.className || ''}`}>{tx(busy ? <LoaderCircle size={16} className="spin"/> : null)}{tx(children)}</button>; }
export function Badge({ children, tone = '' }: {
    children: React.ReactNode;
    tone?: string;
}) { const { t, tx, locale, setLocale } = useI18n(); return <span className={`badge ${tone}`}>{tx(children)}</span>; }
export function Empty({ title, description, action }: {
    title: string;
    description: string;
    action?: React.ReactNode;
}) { const { t, tx, locale, setLocale } = useI18n(); return <div className="empty"><div className="empty-icon"><Inbox size={25}/></div><h3>{tx(title)}</h3><p>{tx(description)}</p>{tx(action)}</div>; }
export function Field({ label, children, hint }: {
    label: string;
    children: React.ReactNode;
    hint?: string;
}) { const { t, tx, locale, setLocale } = useI18n(); const id = useId(); return <div className="field"><label htmlFor={id}>{tx(label)}</label>{tx(isValidElement(children) ? cloneElement(children as ReactElement<Record<string, unknown>>, { id, 'aria-describedby': hint ? id + '-hint' : undefined }) : children)}{tx(hint && <small id={id + '-hint'}>{tx(hint)}</small>)}</div>; }
export function Modal({ title, subtitle, children, onClose, wide = false }: {
    title: string;
    subtitle?: string;
    children: React.ReactNode;
    onClose: () => void;
    wide?: boolean;
}) {
    const { t, tx, locale, setLocale } = useI18n();
    const ref = useRef<HTMLDivElement>(null);
    const close = useRef(onClose);
    close.current = onClose;
    useEffect(() => { const previous = document.activeElement as HTMLElement; const old = document.body.style.overflow; document.body.style.overflow = 'hidden'; ref.current?.querySelector<HTMLElement>('input,button,select,textarea')?.focus(); const key = (e: KeyboardEvent) => { const dialogs = document.querySelectorAll('[role="dialog"]'); if (dialogs[dialogs.length - 1] !== ref.current)
        return; if (e.key === 'Escape') {
        e.preventDefault();
        close.current();
    } if (e.key === 'Tab') {
        const els = ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]');
        if (!els?.length)
            return;
        const first = els[0], last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        }
        else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    } }; document.addEventListener('keydown', key); return () => { document.removeEventListener('keydown', key); document.body.style.overflow = old; previous?.focus(); }; }, []);
    return <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget)
        onClose(); }}><div ref={ref} className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={t(title)}><header className="modal-head"><div><h2>{tx(title)}</h2>{tx(subtitle && <p>{tx(subtitle)}</p>)}</div><LanguageToggle compact/><button className="icon-button" onClick={onClose} aria-label={t("Close dialog")}><X size={20}/></button></header>{tx(children)}</div></div>;
}
export function Notice({ children, tone = '' }: {
    children: React.ReactNode;
    tone?: string;
}) { const { t, tx, locale, setLocale } = useI18n(); return <div className={`notice ${tone}`}><AlertCircle size={17}/><div>{tx(children)}</div></div>; }
export function Score({ value, coverage, large = false }: {
    value: number | null;
    coverage?: number;
    large?: boolean;
}) { const { t, tx, locale, setLocale } = useI18n(); return <div className={`score ${large ? 'large' : ''}`}><span>{tx(value === null ? '—' : Math.round(value))}</span>{tx(large && <small>{tx("documented points / 100")}</small>)}{tx(coverage !== undefined && <div className="score-track" title={t(`${coverage}% of rubric has evidence`)}><i style={{ width: `${value || 0}%` }}/></div>)}</div>; }
export function PageHead({ eyebrow, title, description, actions }: {
    eyebrow?: string;
    title: string;
    description: string;
    actions?: React.ReactNode;
}) { const { t, tx, locale, setLocale } = useI18n(); return <div className="page-heading"><div>{tx(eyebrow && <div className="eyebrow">{tx(eyebrow)}</div>)}<h1>{tx(title)}</h1><p>{tx(description)}</p></div><div className="actions">{tx(actions)}</div></div>; }
export function Steps({ items, current }: {
    items: string[];
    current: number;
}) { const { t, tx, locale, setLocale } = useI18n(); return <div className="steps">{tx(items.map((label, i) => <div className={i === current ? 'active' : i < current ? 'done' : ''} key={label}><span>{tx(i < current ? <Check size={13}/> : i + 1)}</span>{tx(label)}{tx(i < items.length - 1 && <ArrowRight size={12}/>)}</div>))}</div>; }
