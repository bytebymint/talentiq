'use client';
import {useI18n,LanguageToggle} from './i18n';
export default function AppError({reset}:{error:Error;reset:()=>void}){const {t}=useI18n();return <main className="not-found"><LanguageToggle/><h1>{t('Something went wrong.')}</h1><p>{t('Please try again. Your saved records are still available.')}</p><button className="button primary" onClick={reset}>{t('Try again')}</button></main>;}
