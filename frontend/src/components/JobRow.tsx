import {Button, Icon} from '@gravity-ui/uikit';
import {
    ArrowRotateLeft,
    ChevronDown,
    ChevronUp,
    CircleCheckFill,
    CircleDashed,
    CircleXmarkFill,
    Clock,
    MagicWand,
    TrashBin,
    Xmark,
} from '@gravity-ui/icons';
import {jobControl} from '../api';
import type {Job, JobAction, JobStatus} from '../api';
import {useI18n} from '../i18n';

const STATUS: Record<JobStatus, {icon: typeof Clock; labelKey: string}> = {
    pending: {icon: Clock, labelKey: 'job.pending'},
    processing: {icon: MagicWand, labelKey: 'job.processing'},
    done: {icon: CircleCheckFill, labelKey: 'job.done'},
    failed: {icon: CircleXmarkFill, labelKey: 'job.failed'},
    canceled: {icon: CircleDashed, labelKey: 'job.canceled'},
};

const ACTION = {
    up: {icon: ChevronUp, labelKey: 'job.up'},
    down: {icon: ChevronDown, labelKey: 'job.down'},
    cancel: {icon: Xmark, labelKey: 'job.cancel'},
    retry: {icon: ArrowRotateLeft, labelKey: 'job.retry'},
    delete: {icon: TrashBin, labelKey: 'job.delete'},
} as const;

//: Which actions each status offers.
const ACTIONS: Record<JobStatus, JobAction[]> = {
    pending: ['up', 'down', 'delete'],
    processing: ['cancel'],
    done: ['delete'],
    failed: ['retry', 'delete'],
    canceled: ['retry', 'delete'],
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

    const onAction = (action: JobAction) => {
        jobControl(job.id, action).catch(() => undefined);
    };

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
                {job.language && <span className="job-model">{job.language}</span>}
                {job.formats && job.formats !== 'txt' && (
                    <span className="job-model">{job.formats.replace(/,/g, ' · ')}</span>
                )}
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

            <div className="job-actions">
                {ACTIONS[job.status].map((action) => (
                    <Button
                        key={action}
                        view="flat"
                        size="s"
                        onClick={() => onAction(action)}
                        aria-label={t(ACTION[action].labelKey)}
                        title={t(ACTION[action].labelKey)}
                    >
                        <Icon data={ACTION[action].icon} size={16} />
                    </Button>
                ))}
            </div>
        </div>
    );
}
