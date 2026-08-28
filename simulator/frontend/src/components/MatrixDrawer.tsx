import { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Button, Drawer, InputNumber, Modal, Segmented, Space, Tag, Typography, message } from 'antd';
import { removeCoupling, setCoupling } from '../api';
import type { Dataset, SystemState } from '../types';

interface Props {
  open: boolean;
  state: SystemState | null;
  dataset: Dataset;
  onClose: () => void;
  onStateChange: (state: SystemState) => void;
}

interface CellEdit {
  target: string;
  source: string;
  weight: number;
  lagDays: number;
  isManual: boolean;
  significance?: number;
}

export default function MatrixDrawer({ open, state, dataset, onClose, onStateChange }: Props) {
  const [edit, setEdit] = useState<CellEdit | null>(null);
  const [saving, setSaving] = useState(false);

  if (!state) return null;
  const channelNames = state.channels.map((c) => c.name);
  const names = channelNames.map((n) => n.replace(/_/g, ' '));
  const matrix = state.influence_matrix;
  const relByPair = new Map(state.relationships.map((r) => [`${r.target}|${r.source}`, r]));

  // Every cell is clickable (zero cells too, to add new couplings)
  const data: [number, number, number][] = [];
  let maxAbs = 0.01;
  matrix.forEach((row, i) =>
    row.forEach((w, j) => {
      data.push([j, i, Number(w.toFixed(3))]);
      maxAbs = Math.max(maxAbs, Math.abs(w));
    }),
  );
  const manualCells = new Set(
    state.relationships.filter((r) => r.manual).map(
      (r) => `${channelNames.indexOf(r.source)}|${channelNames.indexOf(r.target)}`,
    ),
  );

  const option = {
    animation: false,
    grid: { left: 130, right: 20, top: 90, bottom: 40 },
    tooltip: {
      formatter: (p: { value: [number, number, number] }) => {
        const manual = manualCells.has(`${p.value[0]}|${p.value[1]}`);
        return `${names[p.value[1]]} ← ${names[p.value[0]]}: <b>${p.value[2]}</b>${manual ? ' (manual)' : ''}<br/><i>click to edit</i>`;
      },
    },
    xAxis: {
      type: 'category', data: names, position: 'top',
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'category', data: names, inverse: true, axisLabel: { fontSize: 10 } },
    visualMap: {
      min: -maxAbs, max: maxAbs, calculable: true, orient: 'horizontal',
      left: 'center', bottom: 0,
      inRange: { color: ['#c0392b', '#ffffff', '#27ae60'] },
    },
    series: [{
      type: 'heatmap', data,
      label: {
        show: true, fontSize: 9,
        formatter: (p: { value: [number, number, number] }) =>
          p.value[2] === 0 ? '' : String(p.value[2]),
      },
      itemStyle: {
        borderWidth: 0.5,
        borderColor: (p: { value: [number, number, number] }) =>
          manualCells.has(`${p.value[0]}|${p.value[1]}`) ? '#f5222d' : '#eee',
      },
      emphasis: { itemStyle: { shadowBlur: 6 } },
    }],
  };

  const openEditor = (sourceIdx: number, targetIdx: number, weight: number) => {
    const target = channelNames[targetIdx];
    const source = channelNames[sourceIdx];
    const rel = relByPair.get(`${target}|${source}`);
    setEdit({
      target, source,
      weight: rel?.weight ?? weight,
      lagDays: rel?.lag_days ?? 0,
      isManual: rel?.manual ?? false,
      significance: rel?.significance,
    });
  };

  const apply = async (fn: () => Promise<SystemState>) => {
    setSaving(true);
    try {
      onStateChange(await fn());
      setEdit(null);
    } catch (e) {
      message.error(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer title="Influence matrix (target ← source) — click a cell to edit" open={open} onClose={onClose} width={640}>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        Pairwise weights in standardized increment space; couplings are fitted
        on each pair's own historical overlap with soft-threshold shrinkage
        (|r| ≥ {state.min_corr.toFixed(2)} full weight). Red borders are pinned
        manually or come from priors. α = {state.alpha} — v2 β = {state.beta_v2.toFixed(3)}
        (spectral radius capped ≤ {state.max_spectral_radius}); v1 β = {state.beta_v1.toFixed(3)}
        (per-step clamp at ±{state.clamp_v1} z-units instead).
      </Typography.Paragraph>
      <ReactECharts
        option={option}
        style={{ height: 560 }}
        notMerge
        onEvents={{
          click: (p: { value?: [number, number, number] }) => {
            if (p.value) openEditor(p.value[0], p.value[1], p.value[2]);
          },
        }}
      />

      <Modal
        title={edit ? `${edit.target.replace(/_/g, ' ')} ← ${edit.source.replace(/_/g, ' ')}` : ''}
        open={!!edit}
        onCancel={() => setEdit(null)}
        footer={null}
        width={380}
      >
        {edit && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              {edit.isManual
                ? <Tag color="red">manual / prior</Tag>
                : edit.significance != null
                  ? <Tag color="blue">auto · r = {edit.significance.toFixed(2)}</Tag>
                  : <Tag>not fitted</Tag>}
            </Space>
            <Space>
              <span>Weight</span>
              <InputNumber
                value={edit.weight} step={0.05} style={{ width: 120 }}
                onChange={(v) => v != null && setEdit({ ...edit, weight: v })}
              />
              <span style={{ color: '#999', fontSize: 12 }}>z per z, one step</span>
            </Space>
            <Space>
              <span>Lag</span>
              <Segmented
                value={edit.lagDays}
                options={[{ label: 'same month', value: 0 }, { label: '1 month', value: 30 }]}
                onChange={(v) => setEdit({ ...edit, lagDays: v as number })}
              />
            </Space>
            <Space style={{ marginTop: 8 }}>
              <Button
                type="primary" loading={saving}
                onClick={() => apply(() => setCoupling(edit.target, edit.source, edit.weight, edit.lagDays, dataset))}
              >
                Pin coupling
              </Button>
              {edit.isManual && (
                <Button
                  danger loading={saving}
                  onClick={() => apply(() => removeCoupling(edit.target, edit.source, dataset))}
                >
                  Remove (let data decide)
                </Button>
              )}
            </Space>
          </Space>
        )}
      </Modal>
    </Drawer>
  );
}
