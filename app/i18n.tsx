'use client';
import React,{createContext,useCallback,useContext,useEffect,useMemo,useRef,useState} from 'react';
import {Languages} from 'lucide-react';
import persian from './fa.json';

export type Locale='en'|'fa';
const catalog:Record<string,string>=persian;
const faDigits='۰۱۲۳۴۵۶۷۸۹';
const digits=(s:string)=>s.replace(/\d/g,n=>faDigits[Number(n)]);
const normalize=(s:string)=>s.replace(/\s+/g,' ').trim();
const escape=(s:string)=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const patterns=Object.entries(catalog).filter(([key])=>/\{\d+\}/.test(key)&&!key.startsWith('/')).sort((a,b)=>b[0].replace(/\{\d+\}/g,'').length-a[0].replace(/\{\d+\}/g,'').length).map(([key,value])=>({value,regex:new RegExp('^'+key.split(/\{\d+\}/).map(escape).join('(.+?)')+'$'),indices:[...key.matchAll(/\{(\d+)\}/g)].map(m=>Number(m[1]))}));
export function currentLocale():Locale{return typeof document!=='undefined'&&document.documentElement.lang==='fa'?'fa':'en';}
export function translate(text:string,locale:Locale):string{
 if(locale==='en'||!text)return text;
 const key=normalize(text),exact=catalog[key];
 const finish=(value:string)=>(text.match(/^\s*/)?.[0]||'')+value+(text.match(/\s*$/)?.[0]||'');
 if(exact!==undefined)return finish(exact);
 for(const {regex,value,indices} of patterns){const match=key.match(regex);if(!match)continue;const values:Record<number,string>={};indices.forEach((index,i)=>values[index]=translate(match[i+1],locale));return finish(value.replace(/\{(\d+)\}/g,(_,n)=>values[Number(n)]??''));}
 if(/^[\d.,%\s/–−-]+$/.test(key))return digits(text);
 return text;
}
export const localize=(text:string)=>translate(text,currentLocale());
type Translation={value?:string;error?:boolean;pending?:boolean};
type Context={locale:Locale;setLocale:(v:Locale)=>void;translations:Record<string,Translation>;requestTranslation:(text:string,retry?:boolean,terms?:string[])=>void};
const LanguageContext=createContext<Context|null>(null);

export function LocaleProvider({initialLocale,children}:{initialLocale:Locale;children:React.ReactNode}){
 const [locale,setLanguage]=useState<Locale>(initialLocale);
 const [translations,setTranslations]=useState<Record<string,Translation>>({});
 const pending=useRef(new Map<string,{text:string;locale:Locale;terms:string[]}>());
 const working=useRef(false);
 const requested=useRef(new Set<string>()),timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const setLocale=useCallback((value:Locale)=>{
  document.documentElement.lang=value;document.documentElement.dir=value==='fa'?'rtl':'ltr';
  document.cookie=`talentiq-language=${value}; Path=/; SameSite=Strict; Max-Age=31536000`;
  localStorage.setItem('talentiq-language',value);setLanguage(value);
 },[]);
 useEffect(()=>{document.title=translate('TalentIQ — Intelligence Behind Every Hire',locale);},[locale]);
 useEffect(()=>{
  const invalid=(event:Event)=>{const input=event.target as HTMLInputElement;if(locale!=='fa'||!input.validity)return;input.setCustomValidity(input.validity.valueMissing?'لطفاً این فیلد را تکمیل کنید.':input.validity.tooShort?`لطفاً دست‌کم ${digits(String(input.minLength))} نویسه وارد کنید.`:input.validity.typeMismatch?'لطفاً مقدار معتبری وارد کنید.':'لطفاً مقدار واردشده را بررسی کنید.');};
  const reset=(event:Event)=>{const input=event.target as HTMLInputElement;if(input.setCustomValidity)input.setCustomValidity('');};
  document.addEventListener('invalid',invalid,true);document.addEventListener('input',reset,true);
  return()=>{document.removeEventListener('invalid',invalid,true);document.removeEventListener('input',reset,true);document.querySelectorAll<HTMLInputElement>('input,textarea,select').forEach(input=>input.setCustomValidity(''));};
 },[locale]);
 const requestTranslation=useCallback((text:string,retry=false,terms:string[]=[])=>{
  const key=locale+':'+text+':'+JSON.stringify([...terms].sort());if(requested.current.has(key)&&!retry)return;
  requested.current.add(key);pending.current.set(key,{text,locale,terms});
  setTranslations(prev=>({...prev,[key]:{pending:true}}));
  if(timer.current||working.current)return;
  timer.current=setTimeout(async()=>{
   timer.current=null;working.current=true;do {const queue=[...pending.current];pending.current.clear();
   for(const language of ['fa','en'] as Locale[]){
    const items=queue.filter(([,row])=>row.locale===language);
    let batch:typeof items=[];let size=0;
    const flush=async()=>{
     if(!batch.length)return;const current=batch;batch=[];size=0;
     try{
      const response=await fetch('/api/translations',{method:'POST',headers:{'Content-Type':'application/json','X-TalentIQ-Request':'1','X-TalentIQ-Language':language},body:JSON.stringify({texts:current.map(([,r])=>r.text),language,protected_terms:[...new Set(current.flatMap(([,r])=>r.terms))]})});
      if(!response.ok)throw new Error('translation');const data=await response.json();if(data.translations.length!==current.length)throw new Error('translation');
      setTranslations(prev=>({...prev,...Object.fromEntries(current.map(([k],i)=>[k,{value:data.translations[i]}]))}));
     }catch{setTranslations(prev=>({...prev,...Object.fromEntries(current.map(([k])=>[k,{error:true}]))}));}
    };
    for(const item of items){if(size+item[1].text.length>10000)await flush();batch.push(item);size+=item[1].text.length;}await flush();
   }
   } while(pending.current.size);working.current=false;
  },60);
 },[locale]);
 return <LanguageContext.Provider value={{locale,setLocale,translations,requestTranslation}}>{children}</LanguageContext.Provider>;
}

export function useI18n(){
 const context=useContext(LanguageContext);if(!context)throw new Error('LocaleProvider is required');
 const t=useCallback((text:unknown):string=>typeof text==='string'?translate(text,context.locale):text==null?'':String(text),[context.locale]);
 const tx=useCallback((value:React.ReactNode):React.ReactNode=>{
  if(typeof value==='string')return t(value);
  if(typeof value==='number')return context.locale==='fa'?digits(String(value)):value;
  if(Array.isArray(value))return value.map((v,i)=><React.Fragment key={i}>{typeof v==='string'?t(v):typeof v==='number'&&context.locale==='fa'?digits(String(v)):v}</React.Fragment>);
  return value;
 },[t,context.locale]);
 return {...context,t,tx};
}

export function LanguageToggle({compact=false}:{compact?:boolean}){
 const {locale,setLocale,t}=useI18n();
 return <button type="button" className={`language-toggle ${compact?'compact':''}`} aria-label={t(locale==='en'?'Switch to Persian':'Switch to English')} title={t('Choose interface language')} onClick={()=>setLocale(locale==='en'?'fa':'en')}><Languages size={17}/><span>{locale==='en'?'فارسی':'انگلیسی'}</span></button>;
}

export function useAITranslation(text:string,enabled=true,protectedTerms:string[]=[]){
 const {locale,t,translations,requestTranslation}=useI18n();
 const known=t(text),persianText=(text.match(/[\u0600-\u06ff]/g)?.length||0)/Math.max(1,(text.match(/[A-Za-z\u0600-\u06ff]/g)?.length||0))>.35;
 const needs=enabled&&text.length>2&&known===text&&((locale==='fa'&&!persianText&&/[a-zA-Z]{3}/.test(text))||(locale==='en'&&persianText));
 const termsKey=JSON.stringify([...new Set(protectedTerms)].sort());const terms=useMemo(()=>JSON.parse(termsKey) as string[],[termsKey]);
 const key=locale+':'+text+':'+termsKey;const row=translations[key];
 useEffect(()=>{if(needs)requestTranslation(text,false,terms);},[text,needs,requestTranslation,terms]);
 return {text:!needs?known:row?.value||t(row?.error?'Translation unavailable. Try again.':'Preparing translation…'),loading:needs&&!row?.value&&!row?.error,error:needs&&row?.error,retry:()=>requestTranslation(text,true,terms)};
}
export function AIText({text,protectedTerms=[]}:{text:string;protectedTerms?:string[]}){
 const value=useAITranslation(text,true,protectedTerms);const {t}=useI18n();
 return <span dir="auto" className={value.loading?'muted':undefined}>{value.text}{value.error&&<button type="button" className="text-button" onClick={value.retry}>{t('Retry translation')}</button>}</span>;
}

export function MetadataView({value}:{value:unknown}){
 const {locale,t}=useI18n();
 if(value===null||value===undefined)return <span>—</span>;
 if(Array.isArray(value))return value.length?<ul className="metadata-array">{value.map((v,i)=><li key={i}><MetadataView value={v}/></li>)}</ul>:<span>—</span>;
 if(typeof value==='object')return <dl className="metadata-list">{Object.entries(value).map(([key,v])=><div key={key}><dt>{locale==='fa'&&t(key)===key?'اطلاعات تکمیلی':t(key)}</dt><dd><MetadataView value={v}/></dd></div>)}</dl>;
 return <bdi dir="auto">{typeof value==='boolean'?t(value?'Yes':'No'):t(String(value))}</bdi>;
}
