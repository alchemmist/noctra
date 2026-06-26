import {Icon} from '@gravity-ui/uikit';
import {CircleCheckFill, CircleDashed, CircleXmarkFill, Clock, MagicWand} from '@gravity-ui/icons';
import type {Job, JobStatus} from '../api';
import {useI18n} from '../i18n';

const STATUS: Record<JobStatus, {icon: typeof Clock; labelKey: string}> = {
    pending: {icon: Clock, labelKey: 'job.pending'},
    processing: {icon: MagicWand, labelKey: 'job.processing'},
    done: {icon: CircleCheckFill, labelKey: 'job.done'},
    failed: {icon: CircleXmarkFill, labelKey: 'job.failed'},
    canceled: {icon: CircleDashed, labelKey: 'job.canceled'},
};

function basename(path: string): string {
    const parts = path.split('/');
    return parts[parts.length - 1] || path;
}

export function JobRow({job, index}: {job: Job; index: number}) {
    const {t} = useI18n();
    const status = STATUS[job.status];
    const label = t(status.labelKey);
    const percent = Math.round(job.progress * 100);

    return (
        <div className={`surface job job_${job.status}`}>
            <div className="job-icon">
                <Icon data={status.icon} size={20} />
            </div>

            <div className="job-main">
                <div className="job-name" title={job.path}>
                    {basename(job.path)}
                </div>
                <div className="job-path">{job.path}</div>
                {job.status === 'processing' && (
                    <div className="bar">
                        <div className="bar__fill" style={{width: `${percent}%`}} />
                    </div>
                )}
                {job.status === 'failed' && job.error && (
                    <div className="job-error">{job.error}</div>
                )}
            </div>

            <div className="job-meta">
                <span className="job-num">#{index + 1}</span>
                {job.model && <span className="job-model">{job.model}</span>}
                {job.status === 'processing' && <span className="job-time">{percent}%</span>}
                {job.status === 'done' && (
                    <span className="job-time">
                        {label}
                        {job.duration ? ` · ${t('job.seconds', {n: Math.round(job.duration)})}` : ''}
                    </span>
                )}
                {job.status !== 'processing' && job.status !== 'done' && (
                    <span className="job-time">{label}</span>
                )}
            </div>
        </div>
    );
}
