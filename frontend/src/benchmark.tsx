import React from 'react';

export type BenchmarkRow = {
  label: string;
  values: number[];
};

function finiteValues(values: number[], logScale: boolean): number[] {
  return values
    .map(Number)
    .filter(value => Number.isFinite(value) && (!logScale || value > 0));
}

function mean(values: number[]): number {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function formatValue(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 10000 || (absolute > 0 && absolute < 0.001)) return value.toExponential(1);
  if (absolute >= 100) return value.toFixed(0);
  if (absolute >= 10) return value.toFixed(1);
  return value.toFixed(2).replace(/\.00$/, '');
}

export function BenchmarkMetricChart({
  title,
  rows,
  descending = false,
  logScale = false,
  includeZero = false,
  fixedMax,
  emptyMessage,
  legend = 'media · línea = mínimo–máximo · puntos pequeños = corridas individuales',
}: {
  title: string;
  rows: BenchmarkRow[];
  descending?: boolean;
  logScale?: boolean;
  includeZero?: boolean;
  fixedMax?: number;
  emptyMessage: string;
  legend?: string;
}) {
  const normalized = rows
    .map(row => {
      const values = finiteValues(row.values, logScale);
      return values.length
        ? {
            label: row.label,
            values,
            mean: mean(values),
            min: Math.min(...values),
            max: Math.max(...values),
          }
        : null;
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
    .sort((a, b) => descending ? b.mean - a.mean : a.mean - b.mean);

  if (normalized.length === 0) {
    return <div className="benchmark-empty"><b>{title}</b><p>{emptyMessage}</p></div>;
  }

  const width = 780;
  const left = 190;
  const right = 34;
  const top = 54;
  const bottom = 44;
  const rowHeight = 34;
  const height = top + bottom + normalized.length * rowHeight;
  const allValues = normalized.flatMap(row => row.values);

  let domainMin = Math.min(...allValues);
  let domainMax = Math.max(...allValues);
  if (!logScale && includeZero) domainMin = Math.min(0, domainMin);
  if (!logScale && fixedMax !== undefined) domainMax = Math.max(fixedMax, domainMax);
  if (domainMin === domainMax) {
    if (logScale) {
      domainMin = domainMin / 10;
      domainMax = domainMax * 10;
    } else {
      const delta = Math.abs(domainMin || 1) * 0.1;
      domainMin -= delta;
      domainMax += delta;
    }
  }

  const transform = (value: number) => logScale ? Math.log10(value) : value;
  const transformedMin = transform(domainMin);
  const transformedMax = transform(domainMax);
  const plotWidth = width - left - right;
  const x = (value: number) => {
    const normalizedValue = (transform(value) - transformedMin) / (transformedMax - transformedMin);
    return left + normalizedValue * plotWidth;
  };
  const y = (index: number) => top + index * rowHeight + rowHeight / 2;
  const tickCount = 5;
  const ticks = Array.from({ length: tickCount }, (_, index) => {
    const ratio = index / (tickCount - 1);
    const transformed = transformedMin + ratio * (transformedMax - transformedMin);
    return logScale ? 10 ** transformed : transformed;
  });
  const polyline = normalized.map((row, index) => `${x(row.mean)},${y(index)}`).join(' ');

  return (
    <figure className="benchmark-chart">
      <svg
        role="img"
        aria-label={title}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMinYMin meet"
      >
        <text className="benchmark-title" x={left + plotWidth / 2} y={28} textAnchor="middle">{title}</text>

        {ticks.map((tick, index) => {
          const tickX = x(tick);
          return (
            <g key={`${tick}-${index}`}>
              <line className="benchmark-grid-v" x1={tickX} x2={tickX} y1={top - 7} y2={height - bottom + 4} />
              <text className="benchmark-axis-label" x={tickX} y={height - 13} textAnchor="middle">{formatValue(tick)}</text>
            </g>
          );
        })}

        {normalized.map((row, index) => (
          <g key={row.label}>
            <line className="benchmark-grid-h" x1={left} x2={width - right} y1={y(index)} y2={y(index)} />
            <text className="benchmark-row-label" x={left - 12} y={y(index) + 6} textAnchor="end">{row.label}</text>
          </g>
        ))}

        {normalized.length > 1 && <polyline className="benchmark-mean-line" points={polyline} />}

        {normalized.map((row, index) => (
          <g key={`${row.label}-values`}>
            <line className="benchmark-range" x1={x(row.min)} x2={x(row.max)} y1={y(index)} y2={y(index)} />
            {row.values.map((value, valueIndex) => (
              <circle className="benchmark-run-dot" key={`${value}-${valueIndex}`} cx={x(value)} cy={y(index)} r={3}>
                <title>{`${row.label} · corrida ${valueIndex + 1}: ${formatValue(value)}`}</title>
              </circle>
            ))}
            <circle className="benchmark-mean-dot" cx={x(row.mean)} cy={y(index)} r={7}>
              <title>{`${row.label} · media: ${formatValue(row.mean)} · mín: ${formatValue(row.min)} · máx: ${formatValue(row.max)} · n=${row.values.length}`}</title>
            </circle>
          </g>
        ))}
      </svg>
      <figcaption>
        <span className="benchmark-legend-dot" /> {legend}
      </figcaption>
    </figure>
  );
}
