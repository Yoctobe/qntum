import { useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import { Card } from 'antd';
import type { SimChannel } from '../types';
import { PINNED } from '../types';

interface Props {
  channel: SimChannel;
  dates: string[];
  simStart: number;
  actual?: number[]; // original observed history (comparison in counterfactuals)
  nObserved: number;
  cursorIdx: number;
  compare?: (number | null)[]; // overlaid saved-scenario path (nulled before its sim start)
  compareName?: string;
  onPointClick: (dateIdx: number, value: number) => void;
}

const fmt = (v: number) =>
  Math.abs(v) >= 1000 ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : v.toFixed(2);

export default function ChannelChart({
  channel, dates, simStart, actual, nObserved, cursorIdx, compare, compareName, onPointClick,
}: Props) {
  const T = dates.length;
  // onChartReady fires once per chart instance; keep click data fresh via ref
  const latest = useRef({ levels: channel.levels, T, onPointClick });
  latest.current = { levels: channel.levels, T, onPointClick };
  const isCounterfactual = simStart < nObserved;

  // The blue line is always what actually happened — real observed history,
  // solid, never dotted — regardless of where the cursor or a replay sits.
  const history = dates.map((_, i) => (i < nObserved ? (actual ? actual[i] : channel.levels[i]) ?? null : null));
  const scenario = channel.levels.map((v, i) => (i >= simStart - 1 ? v : null));
  const pinPoints = channel.status
    .map((s, i) => (s === PINNED ? [i, channel.levels[i]] : null))
    .filter(Boolean) as [number, number][];

  const series: object[] = [];

  if (channel.lower && channel.upper) {
    const pad = (arr: number[]) =>
      Array(simStart).fill(null).concat(arr).slice(0, T);
    series.push(
      {
        name: 'ci-low', type: 'line', stack: `ci-${channel.name}`, symbol: 'none',
        lineStyle: { opacity: 0 }, silent: true, z: 0,
        data: pad(channel.lower), tooltip: { show: false },
      },
      {
        name: '90% CI', type: 'line', stack: `ci-${channel.name}`, symbol: 'none',
        lineStyle: { opacity: 0 }, silent: true, z: 0,
        areaStyle: { color: 'rgba(250,140,22,0.15)' },
        data: pad(channel.upper.map((u, k) => u - channel.lower![k])),
        tooltip: { show: false },
      },
    );
  }

  series.push(
    {
      name: 'History', type: 'line', symbol: 'none', z: 2,
      lineStyle: { color: '#1677ff', width: 2 },
      itemStyle: { color: '#1677ff' },
      data: history,
    },
    {
      name: isCounterfactual ? 'Counterfactual' : 'Forecast',
      type: 'line', symbol: 'none', z: 3,
      lineStyle: { color: '#fa8c16', width: 2, type: 'dashed' },
      itemStyle: { color: '#fa8c16' },
      data: scenario,
      markLine: {
        silent: true, symbol: 'none',
        label: { show: false },
        lineStyle: { color: '#999', type: 'solid', width: 1 },
        data: [{ xAxis: Math.min(cursorIdx, T - 1) }],
      },
    },
    {
      name: 'Pinned', type: 'scatter', z: 5,
      symbol: 'diamond', symbolSize: 11,
      itemStyle: { color: '#f5222d' },
      data: pinPoints,
    },
  );

  if (compare) {
    series.push({
      name: compareName ?? 'Compare', type: 'line', symbol: 'none', z: 4,
      lineStyle: { color: '#722ed1', width: 1.5, type: 'dashed' },
      itemStyle: { color: '#722ed1' },
      data: compare.slice(0, T),
    });
  }

  const option = {
    animation: false,
    grid: { left: 56, right: 12, top: 30, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => (v == null ? '—' : fmt(v)),
    },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { formatter: (d: string) => d.slice(0, 7), fontSize: 10 },
    },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10, formatter: fmt } },
    series,
  };

  return (
    <Card
      size="small"
      title={channel.name.replace(/_/g, ' ')}
      styles={{ body: { padding: 4 } }}
      extra={<span style={{ fontSize: 11, color: '#999' }}>click a point to pin</span>}
    >
      <ReactECharts
        option={option}
        style={{ height: 210 }}
        notMerge
        onChartReady={(chart: EChartsType) => {
          // Click anywhere on the plot: snap to the nearest date
          const zr = chart.getZr();
          zr.off('click');
          zr.on('click', (ev: { offsetX: number; offsetY: number }) => {
            const [xi] = chart.convertFromPixel({ gridIndex: 0 }, [ev.offsetX, ev.offsetY]) as unknown as number[];
            const idx = Math.round(xi);
            const { levels, T: len, onPointClick: handler } = latest.current;
            if (Number.isFinite(idx) && idx > 0 && idx < len) {
              handler(idx, levels[idx]);
            }
          });
        }}
      />
    </Card>
  );
}
