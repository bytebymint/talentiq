'use client';
import {useI18n,LanguageToggle} from './i18n';
export default function NotFound(){const {t}=useI18n();return <main className="not-found"><LanguageToggle/><h1>{t('Page not found')}</h1><p>{t('This page is not available. Return to your workspace to continue.')}</p><a className="button primary" href="/">{t('Return to workspace')}</a></main>;}
