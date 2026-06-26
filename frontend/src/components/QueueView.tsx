import {Icon} from '@gravity-ui/uikit';
import {Microphone} from '@gravity-ui/icons';
import type {Job} from '../api';
import {useI18n} from '../i18n';
import {JobRow} from './JobRow';

export function QueueView({jobs}: {jobs: Job[]}) {
    const {t} = useI18n();
    return (
        <section>
            <div className="queue-head">
                <div className="panel-title">{t('queue.title')}</div>
                <span className="queue-count">{t('queue.count', {count: jobs.length})}</span>
            </div>

            {jobs.length === 0 ? (
                <div className="empty">
                    <Icon data={Microphone} size={36} />
                    <div>{t('queue.empty')}</div>
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
