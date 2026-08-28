import { useState } from 'react';
import {
  Button, Card, Collapse, Empty, Input, InputNumber, List, Popover, Slider, Space, Tag, Typography,
} from 'antd';
import {
  DeleteOutlined, DiffOutlined, FolderOpenOutlined, PlusOutlined, SaveOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import type { EventInstance, EventTemplate, Pin, Scenario } from '../types';

interface Props {
  library: EventTemplate[];
  events: EventInstance[];
  pins: Pin[];
  cursorDate: string;
  scenarios: Scenario[];
  compareName: string | null;
  onAddEvent: (template: EventTemplate) => void;
  onUpdateEvent: (id: string, patch: Partial<EventInstance>) => void;
  onRemoveEvent: (id: string) => void;
  onRemovePin: (pin: Pin) => void;
  onSaveScenario: (name: string) => void;
  onLoadScenario: (s: Scenario) => void;
  onCompareToggle: (s: Scenario | null) => void;
  onDeleteScenario: (name: string) => void;
}

export default function ScenarioPanel({
  library, events, pins, cursorDate, scenarios, compareName,
  onAddEvent, onUpdateEvent, onRemoveEvent, onRemovePin,
  onSaveScenario, onLoadScenario, onCompareToggle, onDeleteScenario,
}: Props) {
  const [scenarioName, setScenarioName] = useState('');
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Card size="small" title={<><ThunderboltOutlined /> Event library</>}>
        <List
          size="small"
          dataSource={library}
          renderItem={(t) => (
            <List.Item
              actions={[
                <Button
                  key="add"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={() => onAddEvent(t)}
                >
                  at {cursorDate?.slice(0, 7)}
                </Button>,
              ]}
            >
              <Popover
                title={t.name}
                content={
                  <div style={{ maxWidth: 320 }}>
                    <p>{t.description}</p>
                    <p style={{ marginBottom: 4 }}><b>First-hop (z-units, peak displacement):</b></p>
                    {Object.entries(t.first_hop).map(([ch, w]) => (
                      <Tag key={ch} color={w > 0 ? 'green' : 'red'}>
                        {ch} {w > 0 ? '+' : ''}{w}
                      </Tag>
                    ))}
                    <p style={{ marginTop: 8, marginBottom: 0 }}>
                      <b>Analogues:</b> {t.analogues.join(', ')}
                    </p>
                  </div>
                }
              >
                <Typography.Text>{t.name}</Typography.Text>
              </Popover>
            </List.Item>
          )}
        />
      </Card>

      <Card size="small" title={`Active events (${events.length})`}>
        {events.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Drop an event on the timeline" />}
        <Collapse
          size="small"
          items={events.map((e) => ({
            key: e.id,
            label: (
              <Space size={4} wrap style={{ maxWidth: '100%' }}>
                <Tag color="volcano" style={{ margin: 0 }}>{e.date.slice(0, 7)}</Tag>
                <Typography.Text ellipsis style={{ maxWidth: 160 }}>{e.name}</Typography.Text>
              </Space>
            ),
            extra: (
              <Button
                type="text" size="small" danger icon={<DeleteOutlined />}
                onClick={(ev) => { ev.stopPropagation(); onRemoveEvent(e.id); }}
              />
            ),
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                <Typography.Text type="secondary">Intensity: {e.intensity.toFixed(2)}</Typography.Text>
                <Slider
                  min={0.05} max={1.5} step={0.05} value={e.intensity}
                  onChange={(v) => onUpdateEvent(e.id, { intensity: v })}
                />
                <div className="qntum-event-params">
                  <label>
                    <span>Formation</span>
                    <InputNumber
                      size="small" min={1} max={24} value={e.formation}
                      onChange={(v) => v != null && onUpdateEvent(e.id, { formation: v })}
                      addonAfter="mo"
                      controls={false}
                      style={{ width: 96 }}
                    />
                  </label>
                  <label>
                    <span>τ decay</span>
                    <InputNumber
                      size="small" min={1} max={36} value={e.tau}
                      onChange={(v) => v != null && onUpdateEvent(e.id, { tau: v })}
                      addonAfter="mo"
                      controls={false}
                      style={{ width: 96 }}
                    />
                  </label>
                </div>
              </Space>
            ),
          }))}
        />
      </Card>

      <Card size="small" title={`Pinned values (${pins.length})`}>
        {pins.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Click any chart point" />}
        <List
          size="small"
          dataSource={pins}
          renderItem={(p) => (
            <List.Item
              actions={[
                <Button
                  key="del" type="text" size="small" danger icon={<DeleteOutlined />}
                  onClick={() => onRemovePin(p)}
                />,
              ]}
            >
              <Tag color="red">{p.date.slice(0, 7)}</Tag>
              {p.channel.replace(/_/g, ' ')} = {p.value}
            </List.Item>
          )}
        />
      </Card>

      <Card size="small" title={<><FolderOpenOutlined /> Saved scenarios</>}>
        <Space.Compact style={{ width: '100%', marginBottom: 8 }}>
          <Input
            size="small" placeholder="Scenario name" value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
            onPressEnter={() => {
              if (scenarioName.trim()) { onSaveScenario(scenarioName.trim()); setScenarioName(''); }
            }}
          />
          <Button
            size="small" icon={<SaveOutlined />}
            disabled={!scenarioName.trim() || (pins.length === 0 && events.length === 0)}
            onClick={() => { onSaveScenario(scenarioName.trim()); setScenarioName(''); }}
          >
            Save
          </Button>
        </Space.Compact>
        {scenarios.length === 0 && (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Save the current pins + events" />
        )}
        <List
          size="small"
          dataSource={scenarios}
          renderItem={(s) => (
            <List.Item
              actions={[
                <Button
                  key="load" type="text" size="small" icon={<FolderOpenOutlined />}
                  title="Load into editor" onClick={() => onLoadScenario(s)}
                />,
                <Button
                  key="cmp" type={compareName === s.name ? 'primary' : 'text'} size="small"
                  icon={<DiffOutlined />} title="Overlay on charts"
                  onClick={() => onCompareToggle(compareName === s.name ? null : s)}
                />,
                <Button
                  key="del" type="text" size="small" danger icon={<DeleteOutlined />}
                  onClick={() => onDeleteScenario(s.name)}
                />,
              ]}
            >
              <Typography.Text style={{ fontSize: 12 }}>
                {s.name}
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  {' '}· {s.pins.length} pins, {s.events.length} events
                </Typography.Text>
              </Typography.Text>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  );
}
