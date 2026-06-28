import {Icon} from '@gravity-ui/uikit';
import type {IconData} from '@gravity-ui/uikit';
import type {Job} from '../api';
import {useI18n} from '../i18n';
import {JobRow} from './JobRow';

interface Props {
    title: string;
    jobs: Job[];
    emptyText: string;
    emptyIcon: IconData;
}

export function JobList({title, jobs, emptyText, emptyIcon}: Props) {
    const {t} = useI18n();
    return (
        <section>
            <div className="queue-head">
                <div className="panel-title">{title}</div>
                <span className="queue-count">{t('queue.count', {count: jobs.length})}</span>
            </div>

            {jobs.length === 0 ? (
                <div className="empty">
                    <Icon data={emptyIcon} size={36} />
                    <div>{emptyText}</div>
                </div>
            ) : (
                <div className="queue">
                    {jobs.map((job, index) => (
                        <JobRow key={job.id} job={job} index={index} />
                    ))}
                </div>
            )}
        </section>
    );
}
