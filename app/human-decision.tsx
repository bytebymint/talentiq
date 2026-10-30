'use client';
import {useI18n} from './i18n';

export default function HumanDecision({status,canEdit,onChange}:{status:string;canEdit:boolean;onChange:(status:string)=>void}){
 const {t}=useI18n();
 return <section className="human-decision"><h3>{t('Your hiring decision')}</h3><p>{t('Review the job evidence, choose an outcome and save your own rationale below.')}</p><div className="human-decision-options" role="group" aria-label={t('Human hiring decision')}>{[
  {label:'Hire',status:'Hired',description:'Record a decision to hire.'},
  {label:'Hold',status:'On Hold',description:'Keep the review open while you clarify details.'},
  {label:'Reject',status:'Not Selected',description:'Record a decision not to proceed.'}
 ].map(option=><button key={option.status} type="button" aria-pressed={status===option.status} disabled={!canEdit} onClick={()=>onChange(option.status)}><strong>{t(option.label)}</strong><span>{t(option.description)}</span></button>)}</div><small>{t('Selecting an option does not save it. Use Save human review to confirm your changes.')}</small></section>;
}
