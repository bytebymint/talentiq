import type { Metadata } from 'next';
import '@fontsource-variable/inter';
import '@fontsource-variable/vazirmatn';
import {cookies} from 'next/headers';
import {LocaleProvider} from './i18n';
import './globals.css';
export async function generateMetadata():Promise<Metadata>{
 const fa=(await cookies()).get('talentiq-language')?.value==='fa';
 return {title:fa?'تلنت‌آی‌کیو — هوشمندی در مسیر هر استخدام':'TalentIQ — Intelligence Behind Every Hire',description:fa?'فضای کاری خصوصی شما برای بررسی رزومه و استخدام آگاهانه.':'Your private, local recruitment intelligence workspace.'};
}
export default async function RootLayout({children}:{children:React.ReactNode}) {
 const locale=(await cookies()).get('talentiq-language')?.value==='fa'?'fa':'en';
 return <html lang={locale} dir={locale==='fa'?'rtl':'ltr'} suppressHydrationWarning><body><LocaleProvider initialLocale={locale}>{children}</LocaleProvider></body></html>;
}
