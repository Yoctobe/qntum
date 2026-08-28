import { useState } from 'react';
import {
  Button, Form, Input, InputNumber, Modal, Select, Space, Typography, message,
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { addTemplate } from '../api';
import type { Dataset } from '../types';

interface Props {
  open: boolean;
  channelNames: string[];
  dataset: Dataset;
  onClose: () => void;
  onCreated: () => void;
}

interface HopRow {
  channel?: string;
  weight?: number;
}

export default function NewEventWizard({ open, channelNames, dataset, onClose, onCreated }: Props) {
  const [form] = Form.useForm();
  const [hops, setHops] = useState<HopRow[]>([{}]);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const values = await form.validateFields();
    const firstHop: Record<string, number> = {};
    for (const h of hops) {
      if (h.channel && h.weight != null) firstHop[h.channel] = h.weight;
    }
    if (Object.keys(firstHop).length === 0) {
      message.error('Define at least one first-hop coupling');
      return;
    }
    setSaving(true);
    try {
      await addTemplate({
        name: values.name,
        description: values.description ?? '',
        formation: values.formation,
        tau: values.tau,
        first_hop: firstHop,
      }, dataset);
      message.success(`Template "${values.name}" saved to library`);
      form.resetFields();
      setHops([{}]);
      onCreated();
      onClose();
    } catch (e) {
      message.error(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="Define a new event"
      open={open}
      onCancel={onClose}
      onOk={submit}
      confirmLoading={saving}
      okText="Save to library"
      width={560}
    >
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        A latent event forces its <b>first-hop</b> channels directly; everything
        else reacts through the fitted influence matrix. Weights are peak level
        displacements in z-units (robust SDs of the channel's monthly change) at
        intensity 1.0 — e.g. Oil_WTI +8 ≈ +60% at the peak, unwinding as the
        event decays.
      </Typography.Paragraph>
      <Form form={form} layout="vertical" initialValues={{ formation: 1, tau: 4 }}>
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="e.g. Trade embargo on X" />
        </Form.Item>
        <Form.Item name="description" label="Description / analogues used for calibration">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Space>
          <Form.Item name="formation" label="Formation (months)" rules={[{ required: true }]}>
            <InputNumber min={1} max={24} />
          </Form.Item>
          <Form.Item name="tau" label="Decay τ (months)" rules={[{ required: true }]}>
            <InputNumber min={1} max={36} />
          </Form.Item>
        </Space>
      </Form>

      <Typography.Text strong>First-hop couplings</Typography.Text>
      {hops.map((h, i) => (
        <Space key={i} style={{ display: 'flex', marginTop: 8 }}>
          <Select
            style={{ width: 220 }}
            placeholder="channel"
            value={h.channel}
            options={channelNames.map((c) => ({ value: c, label: c.replace(/_/g, ' ') }))}
            onChange={(v) => setHops(hops.map((x, j) => (j === i ? { ...x, channel: v } : x)))}
          />
          <InputNumber
            placeholder="weight (z)"
            value={h.weight}
            step={0.5}
            onChange={(v) => setHops(hops.map((x, j) => (j === i ? { ...x, weight: v ?? undefined } : x)))}
          />
          <Button
            type="text" danger icon={<DeleteOutlined />}
            onClick={() => setHops(hops.filter((_, j) => j !== i))}
          />
        </Space>
      ))}
      <Button
        style={{ marginTop: 8 }}
        icon={<PlusOutlined />}
        size="small"
        onClick={() => setHops([...hops, {}])}
      >
        Add coupling
      </Button>
    </Modal>
  );
}
