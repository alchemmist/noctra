import {Button, Icon} from '@gravity-ui/uikit';
import {Microphone, Moon, Sun} from '@gravity-ui/icons';
import type {Theme} from '../theme';
import {useI18n} from '../i18n';

interface Props {
    theme: Theme;
    onToggleTheme: () => void;
    running: boolean;
}

export function AppHeader({theme, onToggleTheme, running}: Props) {
    const {t, lang, setLang} = useI18n();

    return (
        <header className="app-header">
            <div className="brand">
                <div className="brand-mark">
                    <Icon data={Microphone} size={22} />
                </div>
                <div>
                    <div className="brand-title">Noctra</div>
                    <div className="brand-sub">{t('brand.sub')}</div>
                </div>
            </div>

            <div className="header-actions">
                <span className={`run-chip ${running ? 'run-chip_on' : ''}`}>
                    <span className="run-chip__dot" />
                    {running ? t('status.running') : t('status.idle')}
                </span>
                <Button
                    view="outlined"
                    size="l"
                    onClick={() => setLang(lang === 'en' ? 'ru' : 'en')}
                    aria-label={t('action.toggleLang')}
                >
                    <span className="lang-code">{lang.toUpperCase()}</span>
                </Button>
                <Button
                    view="outlined"
                    size="l"
                    onClick={onToggleTheme}
                    aria-label={t('action.toggleTheme')}
                >
                    <Icon data={theme === 'dark' ? Sun : Moon} size={18} />
                </Button>
            </div>
        </header>
    );
}
