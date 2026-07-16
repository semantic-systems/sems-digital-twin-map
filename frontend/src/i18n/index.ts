import de from './de.json';
import en from './en.json';

const translations: Record<string, Record<string, string>> = { de, en };

export function getLang(): 'de' | 'en' {
  const params = new URLSearchParams(window.location.search);
  const urlLang = params.get('lang');
  if (urlLang === 'de' || urlLang === 'en') return urlLang;
  const browser = navigator.language.split('-')[0];
  if (browser === 'de' || browser === 'en') return browser as 'de' | 'en';
  return 'de';
}

export function t(key: string, params?: Record<string, string | number>): string {
  const lang = getLang();
  const val = translations[lang]?.[key] ?? translations['de']?.[key] ?? key;
  if (!params) return val;
  return val.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? ''));
}

export function newPostsLabel(count: number): string {
  if (count === 0) return t('new_posts_0');
  return t(count === 1 ? 'new_posts_one' : 'new_posts_many', { n: count });
}
