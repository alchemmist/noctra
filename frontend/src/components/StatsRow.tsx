import {Icon} from '@gravity-ui/uikit';
import {CircleCheck, CircleXmark, Clock, MagicWand} from '@gravity-ui/icons';
import type {QueueState} from '../api';
import {useI18n} from '../i18n';

type Tone = 'neutral' | 'info' | 'success' | 'danger';

const METRICS: {key: keyof QueueState; labelKey: string; tone: Tone; icon: typeof Clock}[] = [
    {key: 'pending', labelKey: 'stats.pending', tone: 'neutral', icon: Clock},
    {key: 'processing', labelKey: 'stats.processing', tone: 'info', icon: MagicWand},
    {key: 'done', labelKey: 'stats.done', tone: 'success', icon: CircleCheck},
    {key: 'failed', labelKey: 'stats.failed', tone: 'danger', icon: CircleXmark},
];

export function StatsRow({state}: {state: QueueState | null}) {
    const {t} = useI18n();
    return (
        <div className="stats-row">
            {METRICS.map((metric) => (
                <div key={metric.key} className={`surface metric metric_${metric.tone}`}>
                    <div className="metric-icon">
                        <Icon data={metric.icon} size={20} />
                    </div>
                    <div className="metric-body">
                        <span className="metric-num">
                            {state ? (state[metric.key] as number) : 0}
                        </span>
                        <span className="metric-label">{t(metric.labelKey)}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}
