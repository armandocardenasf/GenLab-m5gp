import React from 'react';

export type ScatterPoint = {
  x: number;
  y: number;
  label?: string;
};

function finite(points: ScatterPoint[]): ScatterPoint[] {
  return points.filter(point => Number.isFinite(point.x) && Number.isFinite(point.y));
}

function tick(value: number): string {
  const absolute = Math.abs(value);
  if ((absolute > 0 && absolute < 0.001) || absolute >= 10000) {
    return value.toExponential(2);
  }
  return Number(value.toFixed(4)).toString();
}

export function ScatterPlot({
  points,
  xLabel,
  yLabel,
  emptyMessage,
}: {
  points: ScatterPoint[];
  xLabel: string;
  yLabel: string;
  emptyMessage: string;
}) {
  const values = finite(points);
  if (values.length === 0) return <p>{emptyMessage}</p>;

  const width = 840;
  const height = 420;
  const margin = { left: 76, right: 28, top: 28, bottom: 64 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const all = values.flatMap(point => [point.x, point.y]);
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (min === max) {
    min -= 1;
    max += 1;
  } else {
    const padding = (max - min) * 0.06;
    min -= padding;
    max += padding;
  }
  const scaleX = (value: number) =>
    margin.left + ((value - min) / (max - min)) * plotWidth;
  const scaleY = (value: number) =>
    margin.top + plotHeight - ((value - min) / (max - min)) * plotHeight;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="chart-wrapper">
      <svg
        className="chart scatter-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${yLabel} vs ${xLabel}`}
      >
        {ticks.map(position => {
          const value = min + (max - min) * position;
          const x = margin.left + plotWidth * position;
          const y = margin.top + plotHeight * (1 - position);
          return (
            <React.Fragment key={position}>
              <line className="chart-grid" x1={margin.left} y1={y} x2={margin.left + plotWidth} y2={y} />
              <line className="chart-grid vertical" x1={x} y1={margin.top} x2={x} y2={margin.top + plotHeight} />
              <text className="chart-tick" x={margin.left - 12} y={y + 4} textAnchor="end">{tick(value)}</text>
              <text className="chart-tick" x={x} y={height - 34} textAnchor="middle">{tick(value)}</text>
            </React.Fragment>
          );
        })}
        <line className="chart-axis" x1={margin.left} y1={margin.top + plotHeight} x2={margin.left + plotWidth} y2={margin.top + plotHeight} />
        <line className="chart-axis" x1={margin.left} y1={margin.top} x2={margin.left} y2={margin.top + plotHeight} />
        <line
          className="scatter-reference"
          x1={scaleX(min)}
          y1={scaleY(min)}
          x2={scaleX(max)}
          y2={scaleY(max)}
        />
        {values.map((point, index) => (
          <circle
            key={`${point.x}-${point.y}-${index}`}
            className="scatter-point"
            cx={scaleX(point.x)}
            cy={scaleY(point.y)}
            r="3.2"
          >
            {point.label && <title>{point.label}</title>}
          </circle>
        ))}
        <text className="chart-label" x={margin.left + plotWidth / 2} y={height - 5} textAnchor="middle">{xLabel}</text>
        <text className="chart-label" transform={`translate(18 ${margin.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">{yLabel}</text>
      </svg>
      <div className="scatter-legend">
        <span><i className="scatter-dot" />Predicción</span>
        <span><i className="scatter-line" />y = x</span>
      </div>
    </div>
  );
}
