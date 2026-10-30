'use client';
import {useState} from 'react';
import {useI18n} from './i18n';
import {Button,Field,Notice} from './components';
import {Item,send} from './lib';

export default function AccountSettings({user,onUpdated}:{user:Item;onUpdated:(user:Item)=>void}){
 const {t}=useI18n();
 const [username,setUsername]=useState(user.username),[current,setCurrent]=useState(''),[password,setPassword]=useState(''),[confirmation,setConfirmation]=useState('');
 const [saving,setSaving]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
 return <form className="account-settings stack" aria-label={t('Account sign-in settings')} onSubmit={async event=>{
  event.preventDefault();setError('');setSaved(false);
  if(password!==confirmation){setError('The new passwords do not match.');return;}
  setSaving(true);
  try{
   const updated=await send('/auth/account',{username,current_password:current,...(password?{new_password:password,confirm_new_password:confirmation}:{})},'PATCH');
   setCurrent('');setPassword('');setConfirmation('');setUsername(updated.username);onUpdated(updated);setSaved(true);
  }catch(e){setError((e as Error).message);}finally{setSaving(false);}
 }}>
  <p className="muted">{t('Change your username, password, or both. Confirm your current password to save.')}</p>
  {saved&&<Notice>{t('Your sign-in details were updated. You are still signed in; other sessions have been signed out.')}</Notice>}
  {error&&<Notice tone="danger">{t(error)}</Notice>}
  <Field label={t('Username')}><input name="username" autoComplete="username" required minLength={3} maxLength={80} value={username} disabled={saving} onChange={event=>{setUsername(event.target.value);setSaved(false);}}/></Field>
  <Field label={t('Current password')}><input name="current-password" type="password" autoComplete="current-password" required maxLength={200} value={current} disabled={saving} onChange={event=>setCurrent(event.target.value)}/></Field>
  <Field label={t('New password')} hint={t('Leave blank to keep your password. Use at least 12 characters for a new password.')}><input name="new-password" type="password" autoComplete="new-password" minLength={12} maxLength={200} value={password} disabled={saving} onChange={event=>setPassword(event.target.value)}/></Field>
  <Field label={t('Confirm new password')}><input name="confirm-new-password" type="password" autoComplete="new-password" required={!!password} maxLength={200} value={confirmation} disabled={saving} onChange={event=>setConfirmation(event.target.value)}/></Field>
  <p className="small muted">{t('Saving signs out your other sessions. Your workspace data and AI connection stay the same.')}</p>
  <div><Button type="submit" variant="primary" busy={saving} disabled={saving||!current||(!password&&username.trim().toLowerCase()===user.username)}>{t('Save sign-in details')}</Button></div>
 </form>;
}
