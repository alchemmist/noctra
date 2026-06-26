import {Text} from '@gravity-ui/uikit';
import {useQueueState} from './useQueueState';
import {StatsBar} from './components/StatsBar';
import {EnqueueForm} from './components/EnqueueForm';
import {JobList} from './components/JobList';

export function App() {
    const state = useQueueState();

    return (
        <div className="app">
            <header className="app-header">
                <Text variant="display-1">Noctra</Text>
                <StatsBar state={state} />
            </header>

            <div className="app-grid">
                <EnqueueForm running={state?.running ?? false} />
                <JobList jobs={state?.jobs ?? []} />
            </div>
        </div>
    );
}
