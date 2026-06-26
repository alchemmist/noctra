import {Label} from '@gravity-ui/uikit';
import type {QueueState} from '../api';

type LabelTheme = 'unknown' | 'info' | 'success' | 'danger' | 'warning';

const ITEMS: {key: keyof QueueState; label: string; theme: LabelTheme}[] = [
    {key: 'pending', label: 'в очереди', theme: 'unknown'},
    {key: 'processing', label: 'идёт', theme: 'info'},
    {key: 'done', label: 'готово', theme: 'success'},
    {key: 'failed', label: 'ошибки', theme: 'danger'},
];

export function StatsBar({state}: {state: QueueState | null}) {
    return (
        <div className="stats">
            {ITEMS.map((item) => (
                <Label key={item.key} theme={item.theme} size="m">
                    {item.label}: {state ? (state[item.key] as number) : 0}
                </Label>
            ))}
        </div>
    );
}
