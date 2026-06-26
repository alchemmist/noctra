import {Button, Icon} from '@gravity-ui/uikit';
import {Microphone, Moon, Sun} from '@gravity-ui/icons';
import type {Theme} from '../theme';

interface Props {
    theme: Theme;
    onToggleTheme: () => void;
    running: boolean;
}

export function AppHeader({theme, onToggleTheme, running}: Props) {
    return (
        <header className="app-header">
            <div className="brand">
                <div className="brand-mark">
                    <Icon data={Microphone} size={22} />
                </div>
                <div>
                    <div className="brand-title">Noctra</div>
                    <div className="brand-sub">локальная транскрибация аудио</div>
                </div>
            </div>

            <div className="header-actions">
                <span className={`run-chip ${running ? 'run-chip_on' : ''}`}>
                    <span className="run-chip__dot" />
                    {running ? 'идёт обработка' : 'ожидание'}
                </span>
                <Button
                    view="outlined"
                    size="l"
                    onClick={onToggleTheme}
                    aria-label="Переключить тему"
                >
                    <Icon data={theme === 'dark' ? Sun : Moon} size={18} />
                </Button>
            </div>
        </header>
    );
}
