import {ThemeProvider} from '@gravity-ui/uikit';
import {useTheme} from './theme';
import {I18nProvider} from './i18n';
import {useQueueState} from './useQueueState';
import {AppHeader} from './components/AppHeader';
import {StatsRow} from './components/StatsRow';
import {CommandBar} from './components/CommandBar';
import {QueueView} from './components/QueueView';

function AppBody() {
    const [theme, toggleTheme] = useTheme();
    const state = useQueueState();

    return (
        <ThemeProvider theme={theme}>
            <div className="app">
                <AppHeader
                    theme={theme}
                    onToggleTheme={toggleTheme}
                    running={state?.running ?? false}
                />
                <StatsRow state={state} />
                <div className="app-grid">
                    <CommandBar running={state?.running ?? false} />
                    <QueueView jobs={state?.jobs ?? []} />
                </div>
            </div>
        </ThemeProvider>
    );
}

export function App() {
    return (
        <I18nProvider>
            <AppBody />
        </I18nProvider>
    );
}
