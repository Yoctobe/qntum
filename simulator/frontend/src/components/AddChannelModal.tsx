import { useState } from 'react';
import { Input, Modal, Radio, Space, Typography, message } from 'antd';
import { addChannel } from '../api';
import type { Dataset } from '../types';

interface Props {
  open: boolean;
  dataset: Dataset;
  onClose: () => void;
  onAdded: () => void;
}

export default function AddChannelModal({ open, dataset, onClose, onAdded }: Props) {
  const [name, setName] = useState('');
  const [transform, setTransform] = useState('diff');
  const [csv, setCsv] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const rows = csv
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line && !/^date/i.test(line))
      .map((line) => {
        const [date, value] = line.split(/[,;\t]/);
        return { date: date?.trim(), value: parseFloat(value) };
      })
      .filter((r) => r.date && Number.isFinite(r.value));

    if (!name || rows.length < 12) {
      message.error('Need a name and at least 12 rows (date,value)');
      return;
    }
    setSaving(true);
    try {
      await addChannel(name, transform, rows as { date: string; value: number }[], dataset);
      message.success(`${name} added — couplings auto-fitted, system refit`);
      setName(''); setCsv('');
      onAdded();
      onClose();
    } catch (e) {
      message.error(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="Add observable channel"
      open={open}
      onCancel={onClose}
      onOk={submit}
      confirmLoading={saving}
      okText="Add and refit"
      width={520}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
          Paste history for this dataset as <code>date,value</code> lines
          (daily or monthly, matching this dataset's cadence). Couplings to
          existing channels are auto-discovered where statistically significant;
          the whole system is refitted on the overlapping date range.
        </Typography.Paragraph>
        <Input
          placeholder="Channel name (e.g. Copper)"
          value={name}
          onChange={(e) => setName(e.target.value.replace(/\s+/g, '_'))}
        />
        <Radio.Group value={transform} onChange={(e) => setTransform(e.target.value)}>
          <Radio.Button value="diff">diff (rates, zero-crossing)</Radio.Button>
          <Radio.Button value="log_diff">log-diff (prices, indices)</Radio.Button>
        </Radio.Group>
        <Input.TextArea
          rows={8}
          placeholder={'2010-01-01,335.2\n2010-02-01,341.8\n...'}
          value={csv}
          onChange={(e) => setCsv(e.target.value)}
        />
      </Space>
    </Modal>
  );
}
