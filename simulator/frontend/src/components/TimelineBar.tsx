import { Card, Slider, Tag, Typography } from 'antd';
import type { EventInstance } from '../types';

interface Props {
  dates: string[];
  nObserved: number;
  cursorIdx: number;
  onCursorChange: (idx: number) => void;
  events: EventInstance[];
}

export default function TimelineBar({ dates, nObserved, cursorIdx, onCursorChange, events }: Props) {
  if (dates.length === 0) return null;

  const marks: Record<number, { label: JSX.Element }> = {
    [nObserved - 1]: {
      label: <Tag color="blue" style={{ fontSize: 10, marginTop: 4 }}>today</Tag>,
    },
  };
  for (const e of events) {
    const idx = dates.indexOf(e.date);
    if (idx >= 0) {
      marks[idx] = {
        label: <Tag color="volcano" style={{ fontSize: 10, marginTop: 4 }}>{e.name}</Tag>,
      };
    }
  }

  const cursorDate = dates[Math.min(cursorIdx, dates.length - 1)];
  const zone = cursorIdx < nObserved ? 'past' : 'future';

  return (
    <Card size="small" styles={{ body: { padding: '8px 24px 20px' } }}>
      <Typography.Text strong>
        Time cursor: {cursorDate?.slice(0, 7)}{' '}
        <Tag color={zone === 'past' ? 'blue' : 'orange'}>{zone}</Tag>
      </Typography.Text>
      <Slider
        min={1}
        max={dates.length - 1}
        value={cursorIdx}
        onChange={onCursorChange}
        marks={marks}
        tooltip={{ formatter: (v) => dates[v ?? 0]?.slice(0, 7) }}
      />
    </Card>
  );
}
