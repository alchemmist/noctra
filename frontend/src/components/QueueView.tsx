import {Icon} from '@gravity-ui/uikit';
import {Microphone} from '@gravity-ui/icons';
import type {Job} from '../api';
import {JobRow} from './JobRow';

export function QueueView({jobs}: {jobs: Job[]}) {
    return (
        <section>
            <div className="queue-head">
                <div className="panel-title">Очередь</div>
                <span className="queue-count">{jobs.length} задач</span>
            </div>

            {jobs.length === 0 ? (
                <div className="empty">
                    <Icon data={Microphone} size={36} />
                    <div>Очередь пуста — добавьте файлы или папки слева и нажмите «Старт».</div>
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
