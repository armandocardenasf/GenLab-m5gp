import React from 'react';
import { useI18n } from './i18n';

type ChartPoint = { x: number; y: number };
type ChartSeries = {
  label: string;
  points: ChartPoint[];
  className: string;
};

function finiteValues(series: ChartSeries[]): ChartPoint[] {
  return series
    .flatMap(item => item.points)
    .filter(point => Number.isFinite(point.x) && Number.isFinite(point.y));
}

function formatTick(value: number): string {
  const absolute = Math.abs(value);
  if ((absolute > 0 && absolute < 0.001) || absolute >= 10000) {
    return value.toExponential(2);
  }
  return Number(value.toFixed(4)).toString();
}

export function LineChart({
  series,
  xLabel,
  yLabel,
  emptyMessage,
}: {
  series: ChartSeries[];
  xLabel: string;
  yLabel: string;
  emptyMessage?: string;
}) {
  const { t } = useI18n();
  const resolvedEmptyMessage = emptyMessage || t('chart.empty');
  const points = finiteValues(series);
  if (points.length === 0) return <p>{resolvedEmptyMessage}</p>;

  const width = 840;
  const height = 320;
  const margin = { left: 76, right: 24, top: 24, bottom: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  let minX = Math.min(...points.map(point => point.x));
  let maxX = Math.max(...points.map(point => point.x));
  let minY = Math.min(...points.map(point => point.y));
  let maxY = Math.max(...points.map(point => point.y));
  if (minX === maxX) {
    minX -= 1;
    maxX += 1;
  }
  if (minY === maxY) {
    const padding = Math.abs(minY) * 0.05 || 1;
    minY -= padding;
    maxY += padding;
  } else {
    const padding = (maxY - minY) * 0.08;
    minY -= padding;
    maxY += padding;
  }
  const xScale = (value: number) =>
    margin.left + ((value - minX) / (maxX - minX)) * plotWidth;
  const yScale = (value: number) =>
    margin.top + plotHeight - ((value - minY) / (maxY - minY)) * plotHeight;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="chart-wrapper">
      <svg
        className="chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={t('chart.aria', { y: yLabel, x: xLabel })}
      >
        {ticks.map(tick => {
          const y = margin.top + plotHeight * (1 - tick);
          const value = minY + (maxY - minY) * tick;
          return (
            <g key={`y-${tick}`}>
              <line
                className="chart-grid"
                x1={margin.left}
                y1={y}
                x2={margin.left + plotWidth}
                y2={y}
              />
              <text className="chart-tick" x={margin.left - 12} y={y + 4} textAnchor="end">
                {formatTick(value)}
              </text>
            </g>
          );
        })}
        {ticks.map(tick => {
          const x = margin.left + plotWidth * tick;
          const value = minX + (maxX - minX) * tick;
          return (
            <g key={`x-${tick}`}>
              <line
                className="chart-grid vertical"
                x1={x}
                y1={margin.top}
                x2={x}
                y2={margin.top + plotHeight}
              />
              <text className="chart-tick" x={x} y={height - 30} textAnchor="middle">
                {formatTick(value)}
              </text>
            </g>
          );
        })}
        <line
          className="chart-axis"
          x1={margin.left}
          y1={margin.top + plotHeight}
          x2={margin.left + plotWidth}
          y2={margin.top + plotHeight}
        />
        <line
          className="chart-axis"
          x1={margin.left}
          y1={margin.top}
          x2={margin.left}
          y2={margin.top + plotHeight}
        />
        {series.map(item => {
          const path = item.points
            .filter(point => Number.isFinite(point.x) && Number.isFinite(point.y))
            .map((point, index) =>
              `${index === 0 ? 'M' : 'L'} ${xScale(point.x)} ${yScale(point.y)}`,
            )
            .join(' ');
          return (
            <path
              key={item.label}
              className={`chart-line ${item.className}`}
              d={path}
              fill="none"
            />
          );
        })}
        <text className="chart-label" x={margin.left + plotWidth / 2} y={height - 4} textAnchor="middle">
          {xLabel}
        </text>
        <text
          className="chart-label"
          transform={`translate(18 ${margin.top + plotHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          {yLabel}
        </text>
      </svg>
      <div className="chart-legend">
        {series.map(item => (
          <span key={item.label}>
            <i className={item.className} />{item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
