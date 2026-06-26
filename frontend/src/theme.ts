import {useEffect, useState} from 'react';

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'noctra-theme';

function readInitial(): Theme {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === 'light' || stored === 'dark' ? stored : 'dark';
}

export function useTheme(): [Theme, () => void] {
    const [theme, setTheme] = useState<Theme>(readInitial);

    useEffect(() => {
        window.localStorage.setItem(STORAGE_KEY, theme);
    }, [theme]);

    const toggle = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
    return [theme, toggle];
}
