import {createContext, createElement, useContext, useEffect, useState} from 'react';
import type {ReactNode} from 'react';
import {configure} from '@gravity-ui/uikit';

export type Lang = 'en' | 'ru';

const STORAGE_KEY = 'noctra-lang';

/** Translation strings. English is the source language; Russian is optional. */
const MESSAGES: Record<Lang, Record<string, string>> = {
    en: {
        'brand.sub': 'local audio transcription',
        'status.running': 'processing',
        'status.idle': 'idle',
        'action.toggleTheme': 'Toggle theme',
        'action.toggleLang': 'Switch language',

        'stats.pending': 'Queued',
        'stats.processing': 'Processing',
        'stats.done': 'Done',
        'stats.failed': 'Failed',

        'command.title': 'New queue',
        'command.hint': 'Paths to audio files or folders — one per line.',
        'command.drop': 'Drag & drop audio here, or click to choose',
        'command.uploading': 'Uploading…',
        'command.model': 'Model',
        'command.language': 'Language',
        'command.formats': 'Output',
        'command.add': 'Add',
        'command.start': 'Start',
        'command.needPath': 'Add at least one path',
        'command.added': 'Added: {added} · skipped: {skipped} · missing: {missing}',
        'command.cleared': 'Queue cleared',

        'queue.title': 'Queue',
        'queue.count': '{count} jobs',
        'queue.empty': 'Queue is empty — add files or folders on the left and press Start.',

        'job.pending': 'queued',
        'job.processing': 'running',
        'job.done': 'done',
        'job.failed': 'failed',
        'job.canceled': 'canceled',
        'job.seconds': '{n} s',
        'job.cancel': 'Cancel',
        'job.retry': 'Retry',
        'job.delete': 'Remove',
    },
    ru: {
        'brand.sub': 'локальная транскрибация аудио',
        'status.running': 'идёт обработка',
        'status.idle': 'ожидание',
        'action.toggleTheme': 'Переключить тему',
        'action.toggleLang': 'Сменить язык',

        'stats.pending': 'В очереди',
        'stats.processing': 'В работе',
        'stats.done': 'Готово',
        'stats.failed': 'Ошибки',

        'command.title': 'Новая очередь',
        'command.hint': 'Пути к аудиофайлам или папкам — по одному на строку.',
        'command.drop': 'Перетащите аудио сюда или нажмите, чтобы выбрать',
        'command.uploading': 'Загрузка…',
        'command.model': 'Модель',
        'command.language': 'Язык',
        'command.formats': 'Формат',
        'command.add': 'Добавить',
        'command.start': 'Старт',
        'command.needPath': 'Добавьте хотя бы один путь',
        'command.added': 'Добавлено: {added} · пропущено: {skipped} · не найдено: {missing}',
        'command.cleared': 'Очередь очищена',

        'queue.title': 'Очередь',
        'queue.count': '{count} задач',
        'queue.empty': 'Очередь пуста — добавьте файлы или папки слева и нажмите «Старт».',

        'job.pending': 'в очереди',
        'job.processing': 'идёт',
        'job.done': 'готово',
        'job.failed': 'ошибка',
        'job.canceled': 'отменено',
        'job.seconds': '{n} с',
        'job.cancel': 'Отменить',
        'job.retry': 'Повторить',
        'job.delete': 'Удалить',
    },
};

export type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

interface I18nValue {
    lang: Lang;
    setLang: (lang: Lang) => void;
    t: TranslateFn;
}

const I18nContext = createContext<I18nValue | null>(null);

function readInitial(): Lang {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === 'ru' || stored === 'en' ? stored : 'en';
}

function translate(lang: Lang, key: string, params?: Record<string, string | number>): string {
    const template = MESSAGES[lang][key] ?? MESSAGES.en[key] ?? key;
    if (!params) {
        return template;
    }
    return template.replace(/\{(\w+)\}/g, (_, name: string) =>
        name in params ? String(params[name]) : `{${name}}`,
    );
}

export function I18nProvider({children}: {children: ReactNode}) {
    const [lang, setLangState] = useState<Lang>(readInitial);

    useEffect(() => {
        window.localStorage.setItem(STORAGE_KEY, lang);
        // Switch Gravity UI's own built-in component strings too.
        configure({lang});
    }, [lang]);

    const value: I18nValue = {
        lang,
        setLang: setLangState,
        t: (key, params) => translate(lang, key, params),
    };

    return createElement(I18nContext.Provider, {value}, children);
}

export function useI18n(): I18nValue {
    const value = useContext(I18nContext);
    if (value === null) {
        throw new Error('useI18n must be used within <I18nProvider>');
    }
    return value;
}
