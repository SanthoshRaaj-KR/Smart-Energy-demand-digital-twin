import React, { useEffect, useState } from 'react';
import { fetchDispatchLog } from '../api';
import { Card, SectionHeader, Skeleton, Badge } from '../components/Primitives';
import './DispatchLog.css';

function DispatchRow({ record, index }) {
  const [expanded, setExpanded] = useState(false);
  const surplus = record.buyer_bid - record.cleared_price_mw;

  const typeColors = { SYNDICATE: 'blue', NEGOTIATED: 'amber', STANDARD: 'neutral' };
  const typeLabel = record.type;

  return (
    <div className={`dispatch-row ${expanded ? 'dispatch-row--open' : ''}`}>
      <div className="dispatch-row__main" onClick={() => setExpanded(!expanded)}>
        <div className="dispatch-row__index mono dim">#{String(index + 1).padStart(2, '0')}</div>

        <div className="dispatch-row__type">
          <Badge label={typeLabel} variant={typeColors[typeLabel] || 'neutral'} />
        </div>

        <div className="dispatch-row__route">
          {record.type === 'SYNDICATE' ? (
            <span className="mono">Syndicate({record.syndicate_sellers?.join(', ')}) <span className="dim">→</span> {record.buyer_city_id}</span>
          ) : (
            <span className="mono">{record.seller_city_id} <span className="dim">→</span> {record.buyer_city_id}</span>
          )}
        </div>

        <div className="dispatch-row__mw mono">
          <span className="dispatch-row__mw-val">{record.transfer_mw.toLocaleString()}</span>
          <span className="dim"> MW</span>
        </div>

        <div className="dispatch-row__price mono">
          ₹{record.cleared_price_mw.toFixed(2)}/MW
        </div>

        <div className="dispatch-row__surplus mono" style={{ color: surplus >= 0 ? 'var(--green)' : 'var(--red)' }}>
          {surplus >= 0 ? '+' : ''}₹{surplus.toFixed(2)} surplus
        </div>

        <div className="dispatch-row__badges">
          {record.dlr_applied && <Badge label="DLR" variant="amber" />}
          {record.type === 'NEGOTIATED' && <Badge label="Negotiated" variant="amber" />}
          <Badge label={record.llm_safety_status || 'APPROVED'} variant="green" />
        </div>

        <div className="dispatch-row__chevron">{expanded ? '▴' : '▾'}</div>
      </div>

      {expanded && (
        <div className="dispatch-row__detail">
          {record.type === 'SYNDICATE' ? (
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">Sellers</span>
                <span className="detail-val mono">{record.syndicate_sellers?.join(', ')}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Blended Price</span>
                <span className="detail-val mono">₹{record.cleared_price_mw.toFixed(2)}/MW</span>
              </div>
              <div className="detail-item full-width">
                <span className="detail-label">Breakdown</span>
                <span className="detail-val mono">{record.breakdown_log}</span>
              </div>
            </div>
          ) : (
            <div className="detail-grid">
              <div className="detail-item">
                <span className="detail-label">Path</span>
                <span className="detail-val mono">{record.path_description}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Seller Ask</span>
                <span className="detail-val mono">₹{record.seller_ask?.toFixed(2)}/MW</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Path Cost</span>
                <span className="detail-val mono">₹{record.path_cost?.toFixed(2)}/MW</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Carbon Tax</span>
                <span className="detail-val mono">₹{record.carbon_tax?.toFixed(2)}/MW</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Buyer Bid</span>
                <span className="detail-val mono">₹{record.buyer_bid?.toFixed(2)}/MW</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">DLR Capacity</span>
                <span className="detail-val mono">{record.effective_capacity?.toFixed(0)} MW</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DispatchLog() {
  const [records, setRecords] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDispatchLog().then((d) => { setRecords(d); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="page">
        <div className="page__header"><div className="page__title">Dispatch Log</div></div>
        <Card><div style={{ padding: 16 }}><Skeleton h={300} /></div></Card>
      </div>
    );
  }

  const totalMW = records.reduce((s, r) => s + r.transfer_mw, 0);
  const totalVal = records.reduce((s, r) => s + r.transfer_mw * r.cleared_price_mw, 0);
  const syndicateCount = records.filter(r => r.type === 'SYNDICATE').length;
  const negotiatedCount = records.filter(r => r.type === 'NEGOTIATED').length;

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <div className="page__title">Dispatch Log</div>
          <div className="page__sub">All executed inter-city power transfers from the last clearing round</div>
        </div>
      </div>

      {/* Summary strip */}
      <div className="summary-strip" style={{ marginBottom: 16 }}>
        <div className="stat" style={{ background: 'var(--bg-card)', padding: '14px 16px' }}>
          <div className="stat__label">Total Dispatches</div>
          <div className="stat__value mono">{records.length}</div>
        </div>
        <div className="stat" style={{ background: 'var(--bg-card)', padding: '14px 16px' }}>
          <div className="stat__label">Total MW Transferred</div>
          <div className="stat__value mono">{totalMW.toLocaleString()} <span className="stat__unit">MW</span></div>
        </div>
        <div className="stat" style={{ background: 'var(--bg-card)', padding: '14px 16px' }}>
          <div className="stat__label">Market Value</div>
          <div className="stat__value mono">₹{totalVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="stat" style={{ background: 'var(--bg-card)', padding: '14px 16px' }}>
          <div className="stat__label">Syndicate / Negotiated</div>
          <div className="stat__value mono">{syndicateCount} / {negotiatedCount}</div>
        </div>
      </div>

      <Card>
        <SectionHeader
          title="Dispatch Records"
          subtitle="Click a row to expand details"
          right={<span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)' }}>{records.length} records</span>}
        />
        <div className="dispatch-list">
          {records.map((r, i) => <DispatchRow key={i} record={r} index={i} />)}
        </div>
      </Card>
    </div>
  );
}
