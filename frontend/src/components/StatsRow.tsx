import {Icon} from '@gravity-ui/uikit';
import {CircleCheck, CircleXmark, Clock, MagicWand} from '@gravity-ui/icons';
import type {QueueState} from '../api';

type Tone = 'neutral' | 'info' | 'success' | 'danger';

const METRICS: {key: keyof QueueState; label: string; tone: Tone; icon: typeof Clock}[] = [
    {key: 'pending', label: 'В очереди', tone: 'neutral', icon: Clock},
    {key: 'processing', label: 'В работе', tone: 'info', icon: MagicWand},
    {key: 'done', label: 'Готово', tone: 'success', icon: CircleCheck},
    {key: 'failed', label: 'Ошибки', tone: 'danger', icon: CircleXmark},
];

export function StatsRow({state}: {state: QueueState | null}) {
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
                        <span className="metric-label">{metric.label}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}
