import {Microphone} from '@gravity-ui/icons';
import type {Job} from '../api';
import {useI18n} from '../i18n';
import {CommandBar} from './CommandBar';
import {JobList} from './JobList';

export function QueuePanel({jobs, running}: {jobs: Job[]; running: boolean}) {
    const {t} = useI18n();
    const active = jobs.filter((j) => j.status === 'pending' || j.status === 'processing');
    return (
        <div className="app-grid">
            <CommandBar running={running} />
            <JobList
                title={t('queue.title')}
                jobs={active}
                emptyText={t('queue.empty')}
                emptyIcon={Microphone}
            />
        </div>
    );
}
