import {ClockArrowRotateLeft} from '@gravity-ui/icons';
import type {Job, JobStatus} from '../api';
import {useI18n} from '../i18n';
import {JobList} from './JobList';

const TERMINAL: JobStatus[] = ['done', 'failed', 'canceled'];

export function HistoryPanel({jobs}: {jobs: Job[]}) {
    const {t} = useI18n();
    // Most recent first.
    const history = jobs.filter((j) => TERMINAL.includes(j.status)).slice().reverse();
    return (
        <JobList
            title={t('history.title')}
            jobs={history}
            emptyText={t('history.empty')}
            emptyIcon={ClockArrowRotateLeft}
        />
    );
}
