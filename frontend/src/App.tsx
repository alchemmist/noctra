import {useState} from 'react';
import {
    Tab,
    TabList,
    TabProvider,
    ThemeProvider,
    Toaster,
    ToasterComponent,
    ToasterProvider,
} from '@gravity-ui/uikit';

const toaster = new Toaster();
import {useTheme} from './theme';
import {I18nProvider, useI18n} from './i18n';
import {useQueueState} from './useQueueState';
import {AppHeader} from './components/AppHeader';
import {StatsRow} from './components/StatsRow';
import {QueuePanel} from './components/QueuePanel';
import {HistoryPanel} from './components/HistoryPanel';
import {SettingsPanel} from './components/SettingsPanel';

type TabId = 'queue' | 'history' | 'settings';

function AppBody() {
    const [theme, toggleTheme] = useTheme();
    const {t} = useI18n();
    const state = useQueueState();
    const [tab, setTab] = useState<TabId>('queue');

    const jobs = state?.jobs ?? [];
    const historyCount = (state?.done ?? 0) + (state?.failed ?? 0) + (state?.canceled ?? 0);

    return (
        <ThemeProvider theme={theme}>
          <ToasterProvider toaster={toaster}>
            <div className="app">
                <AppHeader
                    theme={theme}
                    onToggleTheme={toggleTheme}
                    running={state?.running ?? false}
                />
                <StatsRow state={state} />

                <TabProvider value={tab} onUpdate={(value) => setTab(value as TabId)}>
                    <TabList className="tabs">
                        <Tab value="queue">{t('tab.queue')}</Tab>
                        <Tab value="history" counter={historyCount || undefined}>
                            {t('tab.history')}
                        </Tab>
                        <Tab value="settings">{t('tab.settings')}</Tab>
                    </TabList>
                </TabProvider>

                <div className="tab-body">
                    {tab === 'queue' && (
                        <QueuePanel jobs={jobs} running={state?.running ?? false} />
                    )}
                    {tab === 'history' && <HistoryPanel jobs={jobs} />}
                    {tab === 'settings' && <SettingsPanel />}
                </div>
            </div>
            <ToasterComponent />
          </ToasterProvider>
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
