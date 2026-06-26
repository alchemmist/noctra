import {ThemeProvider} from '@gravity-ui/uikit';
import {useTheme} from './theme';
import {useQueueState} from './useQueueState';
import {AppHeader} from './components/AppHeader';
import {StatsRow} from './components/StatsRow';
import {CommandBar} from './components/CommandBar';
import {QueueView} from './components/QueueView';

export function App() {
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
