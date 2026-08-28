import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button, Col, Grid, InputNumber, Layout, Modal, Row, Slider, Space, Spin, Tabs, Tag, Tooltip, Typography, message,
} from 'antd';
import {
  ApartmentOutlined, ExperimentOutlined, LineChartOutlined, ReloadOutlined,
} from '@ant-design/icons';
import {
  deleteScenario, fetchLibrary, fetchScenarios, fetchState, saveScenario, simulate,
} from './api';
import type { Dataset, EventInstance, EventTemplate, ModelVersion, Pin, Scenario, SimResult, SystemState } from './types';
import ChannelChart from './components/ChannelChart';
import TimelineBar from './components/TimelineBar';
import ScenarioPanel from './components/ScenarioPanel';
import NewEventWizard from './components/NewEventWizard';
import AddChannelModal from './components/AddChannelModal';
import MatrixDrawer from './components/MatrixDrawer';
import './App.css';

const HORIZON_DEFAULT = 24;

const DATASET_TOOLTIPS: Record<Dataset, string> = {
  monthly: 'Well-conditioned live US macro panel — the spectral cap stays idle, v1 ≈ v2',
  medical: 'Synthetic glucose/insulin regulation (Bergman-style constants) — same engine, a physiological domain: insulin lowers glucose, glucose drives secretion',
  ecosystem: 'Synthetic predator/prey population (Lotka–Volterra, monthly) — same engine, an ecological domain: predators suppress prey growth',
};

interface PinEdit {
  channel: string;
  date: string;
  value: number;
  idx: number;
  ramp: number; // months to reach the value (1 = instant pin)
}

export default function App() {
  const [activeModel, setActiveModel] = useState<ModelVersion>('v2');
  const [dataset, setDataset] = useState<Dataset>('monthly');
  const [state, setState] = useState<SystemState | null>(null);
  const [library, setLibrary] = useState<EventTemplate[]>([]);
  const [pins, setPins] = useState<Pin[]>([]);
  const [events, setEvents] = useState<EventInstance[]>([]);
  const [horizon, setHorizon] = useState(HORIZON_DEFAULT);
  const [anticipation, setAnticipation] = useState(0);
  const [result, setResult] = useState<SimResult | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [compareScenario, setCompareScenario] = useState<Scenario | null>(null);
  const [compareResult, setCompareResult] = useState<SimResult | null>(null);
  const [cursorIdx, setCursorIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [channelOpen, setChannelOpen] = useState(false);
  const [matrixOpen, setMatrixOpen] = useState(false);
  const [pinEdit, setPinEdit] = useState<PinEdit | null>(null);
  const debounceRef = useRef<number>();

  const loadState = useCallback(async (ds: Dataset) => {
    const [s, lib, sc] = await Promise.all([fetchState(ds), fetchLibrary(ds), fetchScenarios()]);
    setState(s);
    setLibrary(lib);
    setScenarios(sc);
    setCursorIdx(s.dates.length - 1);
  }, []);

  useEffect(() => {
    // Switching dataset changes the channel set entirely; stale pins/events
    // from the other dataset would silently no-op or point at unknown channels.
    setPins([]);
    setEvents([]);
    setCompareScenario(null);
    loadState(dataset).catch((e) => message.error(String(e)));
  }, [dataset, loadState]);

  // Cursor moved into the past (no pin/event needed): replay the fitted model
  // from that date forward, so the chart shows model output vs what actually
  // happened next to it — a quick "how good is the model" check. The default
  // cursor position (last observed month) is excluded so the normal forward
  // forecast still shows until the user actually drags back in time.
  const replayFrom = state && cursorIdx < state.dates.length - 1 ? state.dates[cursorIdx] : undefined;

  useEffect(() => {
    if (!state) return;
    window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(async () => {
      setLoading(true);
      try {
        setResult(await simulate(pins, events, horizon, 60, anticipation, replayFrom, activeModel, dataset));
      } catch (e) {
        message.error(String(e));
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(debounceRef.current);
  }, [state, pins, events, horizon, anticipation, replayFrom, activeModel, dataset]);

  // Overlay: evaluate the compared scenario on the current timeline
  useEffect(() => {
    if (!state || !compareScenario) {
      setCompareResult(null);
      return;
    }
    simulate(compareScenario.pins, compareScenario.events, horizon, 0, compareScenario.anticipation, undefined, activeModel, dataset)
      .then(setCompareResult)
      .catch((e) => message.error(String(e)));
  }, [state, compareScenario, horizon, activeModel, dataset]);

  const nObserved = state?.dates.length ?? 0;
  const timelineDates = result?.dates ?? state?.dates ?? [];
  const cursorDate = timelineDates[Math.min(cursorIdx, timelineDates.length - 1)] ?? '';

  const addEventAtCursor = (t: EventTemplate) => {
    const date = timelineDates[Math.min(cursorIdx, timelineDates.length - 1)];
    setEvents((prev) => [
      ...prev,
      {
        id: `${t.name}-${Date.now()}`,
        template: t.name,
        name: t.name,
        date,
        intensity: 1.0,
        formation: t.formation,
        tau: t.tau,
      },
    ]);
  };

  const savePin = () => {
    if (!pinEdit || !result) return;
    const { channel, idx, value, ramp } = pinEdit;
    const ch = result.channels.find((c) => c.name === channel);
    const newPins: Pin[] = [];
    if (ramp > 1 && ch) {
      // Ramp assist: pin the whole approach path, not a single-step jump
      const startIdx = Math.max(1, idx - ramp);
      const startVal = ch.levels[startIdx];
      for (let k = startIdx + 1; k <= idx; k += 1) {
        const f = (k - startIdx) / (idx - startIdx);
        newPins.push({
          channel,
          date: result.dates[k],
          value: Number((startVal + (value - startVal) * f).toFixed(4)),
        });
      }
    } else {
      newPins.push({ channel, date: pinEdit.date, value });
    }
    setPins((prev) => [
      ...prev.filter((p) => !(p.channel === channel && newPins.some((np) => np.date === p.date))),
      ...newPins,
    ]);
    setPinEdit(null);
  };

  const handleSaveScenario = async (name: string) => {
    try {
      setScenarios(await saveScenario({ name, pins, events, horizon, anticipation }));
      message.success(`Scenario "${name}" saved`);
    } catch (e) {
      message.error(String(e));
    }
  };

  const handleLoadScenario = (s: Scenario) => {
    setPins(s.pins);
    setEvents(s.events);
    setHorizon(s.horizon);
    setAnticipation(s.anticipation ?? 0);
  };

  const handleDeleteScenario = async (name: string) => {
    try {
      setScenarios(await deleteScenario(name));
      if (compareScenario?.name === name) setCompareScenario(null);
    } catch (e) {
      message.error(String(e));
    }
  };

  const scenarioActive = pins.length > 0 || events.length > 0;
  const screens = Grid.useBreakpoint();
  const compact = !screens.md;
  const mobile = !screens.sm;

  const charts = useMemo(() => {
    if (!result || !state) return null;
    return (
      <Row gutter={[8, 8]}>
        {result.channels.map((c) => {
          const cmp = compareResult?.channels.find((x) => x.name === c.name);
          const compareData = cmp
            ? cmp.levels.map((v, i) => (i >= compareResult!.sim_start - 1 ? v : null))
            : undefined;
          return (
            <Col key={c.name} xs={24} lg={12} xxl={8}>
              <ChannelChart
                channel={c}
                dates={result.dates}
                simStart={result.sim_start}
                actual={state.observed[c.name]}
                nObserved={nObserved}
                cursorIdx={cursorIdx}
                compare={compareData}
                compareName={compareScenario?.name}
                onPointClick={(idx, value) =>
                  setPinEdit({
                    channel: c.name,
                    date: result.dates[idx],
                    value: Number(value.toFixed(2)),
                    idx,
                    ramp: 1,
                  })
                }
              />
            </Col>
          );
        })}
      </Row>
    );
  }, [result, state, cursorIdx, nObserved, compareResult, compareScenario]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header className="qntum-header">
        <div className="qntum-header-meta">
          <Typography.Title level={4} className="qntum-header-title">
            {mobile ? 'QNTUM' : 'QNTUM Simulator'}
          </Typography.Title>
          <Tag color="geekblue" style={{ margin: 0 }}>
            {state ? `${state.channels.length} ch · ${nObserved}` : '…'}
          </Tag>
          {loading && <Spin size="small" />}
        </div>

        <Tooltip title="v1: relative-scale + per-step clamp · v2: spectral-radius cap on β">
          <div className="qntum-header-tabs">
            <Tabs
              activeKey={activeModel}
              onChange={(k) => setActiveModel(k as ModelVersion)}
              size="small"
              items={[
                { key: 'v1', label: compact ? 'v1' : 'v1 — bounded' },
                { key: 'v2', label: compact ? 'v2' : 'v2 — spectral' },
              ]}
            />
          </div>
        </Tooltip>

        <Tooltip title={DATASET_TOOLTIPS[dataset]}>
          <div className="qntum-header-tabs">
            <Tabs
              activeKey={dataset}
              onChange={(k) => setDataset(k as Dataset)}
              size="small"
              items={[
                { key: 'monthly', label: compact ? 'Fin' : 'Finance' },
                { key: 'medical', label: compact ? 'Med' : 'Medical' },
                { key: 'ecosystem', label: compact ? 'Eco' : 'Ecosystem' },
              ]}
            />
          </div>
        </Tooltip>

        <div className="qntum-header-actions">
          <Tooltip title="Forecast horizon (months ahead)">
            <InputNumber
              size="small"
              min={6} max={60} value={horizon}
              onChange={(v) => v != null && setHorizon(v)}
              addonBefore="H"
              addonAfter="mo"
              controls={false}
              style={{ width: 118 }}
            />
          </Tooltip>
          <Tooltip title="Anticipation: months of lead before pins (markets front-running announced policy)">
            <InputNumber
              size="small"
              min={0} max={12} value={anticipation}
              onChange={(v) => v != null && setAnticipation(v)}
              addonBefore="A"
              addonAfter="mo"
              controls={false}
              style={{ width: 110 }}
            />
          </Tooltip>
          <Tooltip title={dataset !== 'monthly' ? 'Matrix editing only applies to the live finance panel' : 'Influence matrix'}>
            <Button
              size="small"
              icon={<ApartmentOutlined />}
              disabled={dataset !== 'monthly'}
              onClick={() => setMatrixOpen(true)}
            >
              {compact ? null : 'Matrix'}
            </Button>
          </Tooltip>
          <Tooltip title={dataset !== 'monthly' ? 'Adding channels only applies to the live finance panel' : 'Add channel'}>
            <Button
              size="small"
              icon={<LineChartOutlined />}
              disabled={dataset !== 'monthly'}
              onClick={() => setChannelOpen(true)}
            >
              {compact ? null : 'Add channel'}
            </Button>
          </Tooltip>
          <Tooltip title="New event template">
            <Button
              size="small"
              icon={<ExperimentOutlined />}
              type="primary"
              onClick={() => setWizardOpen(true)}
            >
              {compact ? null : 'New event'}
            </Button>
          </Tooltip>
          {scenarioActive && (
            <Tooltip title="Clear pins and events">
              <Button
                size="small"
                icon={<ReloadOutlined />}
                danger
                onClick={() => { setPins([]); setEvents([]); }}
              >
                {compact ? null : 'Reset'}
              </Button>
            </Tooltip>
          )}
        </div>
      </Layout.Header>

      <Layout className="qntum-layout-body">
        <Layout.Content style={{ padding: 8, minWidth: 0 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <TimelineBar
              dates={timelineDates}
              nObserved={nObserved}
              cursorIdx={cursorIdx}
              onCursorChange={setCursorIdx}
              events={events}
            />
            {charts ?? <Spin style={{ margin: 48 }} size="large" />}
          </Space>
        </Layout.Content>

        <Layout.Sider
          className="qntum-sider"
          width={compact ? '100%' : 340}
          theme="light"
          style={{ padding: 8, overflow: 'auto' }}
        >
          <ScenarioPanel
            library={library}
            events={events}
            pins={pins}
            cursorDate={cursorDate}
            scenarios={scenarios}
            compareName={compareScenario?.name ?? null}
            onAddEvent={addEventAtCursor}
            onUpdateEvent={(id, patch) =>
              setEvents((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)))
            }
            onRemoveEvent={(id) => setEvents((prev) => prev.filter((e) => e.id !== id))}
            onRemovePin={(pin) =>
              setPins((prev) => prev.filter((p) => !(p.channel === pin.channel && p.date === pin.date)))
            }
            onSaveScenario={handleSaveScenario}
            onLoadScenario={handleLoadScenario}
            onCompareToggle={setCompareScenario}
            onDeleteScenario={handleDeleteScenario}
          />
        </Layout.Sider>
      </Layout>

      <Modal
        title={pinEdit ? `Pin ${pinEdit.channel.replace(/_/g, ' ')} @ ${pinEdit.date.slice(0, 7)}` : ''}
        open={!!pinEdit}
        onCancel={() => setPinEdit(null)}
        onOk={savePin}
        okText={pinEdit && pinEdit.ramp > 1 ? `Pin ramp (${pinEdit.ramp} mo)` : 'Pin value'}
        width={380}
      >
        {pinEdit && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {pinEdit.date < (state?.dates[nObserved - 1] ?? '')
                ? 'Editing the past creates a counterfactual: the model re-simulates from here.'
                : 'Pinning a future value creates a conditional forecast: other channels react.'}
            </Typography.Text>
            <InputNumber
              style={{ width: '100%' }}
              value={pinEdit.value}
              onChange={(v) => v != null && setPinEdit({ ...pinEdit, value: v })}
              step={0.1}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Reach over {pinEdit.ramp === 1 ? '1 month (instant)' : `${pinEdit.ramp} months`} —
              gradual paths propagate more realistically than one-step jumps
            </Typography.Text>
            <Slider
              min={1} max={Math.min(12, Math.max(1, pinEdit.idx - 1))} step={1}
              value={pinEdit.ramp}
              onChange={(v) => setPinEdit({ ...pinEdit, ramp: v })}
              marks={{ 1: 'instant', 6: '6mo', 12: '12mo' }}
            />
          </Space>
        )}
      </Modal>

      <NewEventWizard
        open={wizardOpen}
        channelNames={state?.channels.map((c) => c.name) ?? []}
        dataset={dataset}
        onClose={() => setWizardOpen(false)}
        onCreated={() => fetchLibrary(dataset).then(setLibrary)}
      />
      <AddChannelModal
        open={channelOpen}
        onClose={() => setChannelOpen(false)}
        onAdded={() => loadState(dataset)}
      />
      <MatrixDrawer
        open={matrixOpen}
        state={state}
        onClose={() => setMatrixOpen(false)}
        onStateChange={setState}
      />
    </Layout>
  );
}
