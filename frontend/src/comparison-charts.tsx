import React from 'react';

import type { ComparisonAnalysis, ComparisonRankingRow } from './lab-types';

function finite(values: number[]) {
  return values.filter(value => Number.isFinite(value));
}

function format(value: number | null | undefined, digits = 3) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  if (Math.abs(value) >= 10000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) return value.toExponential(2);
  return value.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

function quantile(values: number[], q: number) {
  const sorted = finite(values).sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const index = (sorted.length - 1) * q;
  const lo = Math.floor(index);
  const hi = Math.ceil(index);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (index - lo);
}

export function DistributionBoxPlot({
  title,
  rows,
  logScale = false,
}: {
  title: string;
  rows: ComparisonRankingRow[];
  logScale?: boolean;
}) {
  const usable = rows.filter(row => finite(row.values).length > 0);
  if (!usable.length) return <div className="comparison-empty">Sin datos para {title}.</div>;
  const width = 760;
  const left = 190;
  const right = 30;
  const top = 46;
  const rowHeight = 38;
  const bottom = 44;
  const height = top + usable.length * rowHeight + bottom;
  const all = usable.flatMap(row => finite(row.values)).filter(value => !logScale || value > 0);
  const transform = (value: number) => logScale ? Math.log10(Math.max(value, Number.MIN_VALUE)) : value;
  const min = Math.min(...all.map(transform));
  const max = Math.max(...all.map(transform));
  const span = max - min || 1;
  const x = (value: number) => left + ((transform(value) - min) / span) * (width - left - right);

  return (
    <figure className="comparison-chart comparison-boxplot">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        <text x={left} y={27} className="comparison-chart-title">{title}</text>
        {usable.map((row, index) => {
          const values = finite(row.values).filter(value => !logScale || value > 0);
          const y = top + index * rowHeight + rowHeight / 2;
          const q1 = quantile(values, 0.25);
          const median = quantile(values, 0.5);
          const q3 = quantile(values, 0.75);
          const vmin = Math.min(...values);
          const vmax = Math.max(...values);
          return (
            <g key={row.experiment_id}>
              <line className="comparison-grid" x1={left} x2={width - right} y1={y} y2={y} />
              <text className="comparison-row-label" x={left - 12} y={y + 5} textAnchor="end">{row.label}</text>
              <line className="comparison-whisker" x1={x(vmin)} x2={x(vmax)} y1={y} y2={y} />
              <rect className="comparison-box" x={x(q1)} y={y - 9} width={Math.max(2, x(q3) - x(q1))} height={18} />
              <line className="comparison-median" x1={x(median)} x2={x(median)} y1={y - 10} y2={y + 10} />
              <circle className="comparison-mean" cx={x(row.mean)} cy={y} r={4}>
                <title>{`${row.label}: mean=${format(row.mean)}, median=${format(median)}, n=${row.n}`}</title>
              </circle>
            </g>
          );
        })}
        <text className="comparison-axis-caption" x={(left + width - right) / 2} y={height - 10} textAnchor="middle">
          {logScale ? 'Escala log10' : title}
        </text>
      </svg>
      <figcaption>Caja = Q1–Q3 · línea = mediana · punto = media · bigotes = mínimo–máximo</figcaption>
    </figure>
  );
}

export function WilcoxonMatrix({ analysis }: { analysis: ComparisonAnalysis }) {
  const result = analysis.wilcoxon;
  const experiments = result.experiments;
  const cellMap = new Map(result.cells.map(cell => [`${cell.row_experiment_id}|${cell.column_experiment_id}`, cell]));
  const legend = [
    ['sig_1e3', 'p_adj < 10⁻³ · α'],
    ['sig_1e2', 'p_adj < 10⁻² · α'],
    ['sig_1e1', 'p_adj < 10⁻¹ · α'],
    ['sig_alpha', 'p_adj < α'],
    ['ns', 'no significativo'],
  ];
  return (
    <div className="wilcoxon-wrap">
      <div className="wilcoxon-scroll">
        <table className="wilcoxon-table">
          <thead>
            <tr>
              <th />
              {experiments.map(item => <th key={item.id} title={item.name}>{item.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {experiments.map((row, rowIndex) => (
              <tr key={row.id}>
                <th title={row.name}>{row.name}</th>
                {experiments.map((column, columnIndex) => {
                  if (columnIndex >= rowIndex) return <td className="wilcoxon-blank" key={column.id} />;
                  const cell = cellMap.get(`${row.id}|${column.id}`);
                  if (!cell) return <td className="wilcoxon-unavailable" key={column.id}>—</td>;
                  const winner = experiments.find(item => item.id === cell.winner_experiment_id)?.name || '—';
                  return (
                    <td className={`wilcoxon-cell ${cell.category}`} key={column.id}>
                      <span>{cell.p_adjusted === null ? '—' : format(cell.p_adjusted, 4)}</span>
                      <small>{cell.exploratory ? `n=${cell.n_pairs}*` : `n=${cell.n_pairs}`}</small>
                      <title>{`Wilcoxon ${row.name} vs ${column.name}\np=${format(cell.p_value, 5)}\np_adj=${format(cell.p_adjusted, 5)}\nn=${cell.n_pairs}\nr_rb=${format(cell.rank_biserial, 3)}\nΔ mediana orientada=${format(cell.median_oriented_difference, 4)}\nmejor media: ${winner}${cell.exploratory ? '\nExploratorio: menos de 5 datasets comunes' : ''}`}</title>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="wilcoxon-legend">
        {legend.map(([key, label]) => <span key={key}><i className={key} />{label}</span>)}
        <span><b>*</b> menos de 5 datasets comunes: resultado exploratorio</span>
      </div>
      <p className="comparison-note">Wilcoxon de rangos con signo sobre medias por dataset común. Corrección múltiple: {result.correction}. α={result.alpha}.</p>
    </div>
  );
}

export function ScalingChart({
  title,
  xLabel,
  points,
}: {
  title: string;
  xLabel: string;
  points: ComparisonAnalysis['computational']['samples'];
}) {
  const series = Array.from(new Set(points.map(point => point.experiment_id))).map(id => ({
    id,
    name: points.find(point => point.experiment_id === id)?.experiment_name || id,
    points: points.filter(point => point.experiment_id === id && point.x > 0 && point.training_time_mean > 0).sort((a, b) => a.x - b.x),
  })).filter(item => item.points.length);
  if (!series.length) return <div className="comparison-empty">No hay tiempos de entrenamiento para esta gráfica.</div>;
  const width = 760;
  const height = 490;
  const left = 78;
  const right = 34;
  const top = 48;
  const bottom = 64;
  const all = series.flatMap(item => item.points);
  const xValues = all.map(point => Math.log10(point.x));
  const yValues = all.map(point => Math.log10(point.training_time_mean));
  const xMin = Math.min(...xValues), xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues), yMax = Math.max(...yValues);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const x = (value: number) => left + ((Math.log10(value) - xMin) / xSpan) * (width - left - right);
  const y = (value: number) => height - bottom - ((Math.log10(value) - yMin) / ySpan) * (height - top - bottom);
  const ticks = (min: number, max: number) => {
    const from = Math.floor(min);
    const to = Math.ceil(max);
    return Array.from({ length: to - from + 1 }, (_, index) => from + index);
  };
  return (
    <figure className="comparison-chart scaling-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        <text className="comparison-chart-title" x={left} y={27}>{title}</text>
        {ticks(xMin, xMax).map(tick => {
          const px = left + ((tick - xMin) / xSpan) * (width - left - right);
          return <g key={`x-${tick}`}><line className="comparison-grid" x1={px} x2={px} y1={top} y2={height - bottom} /><text className="comparison-axis-label" x={px} y={height - bottom + 23} textAnchor="middle">10^{tick}</text></g>;
        })}
        {ticks(yMin, yMax).map(tick => {
          const py = height - bottom - ((tick - yMin) / ySpan) * (height - top - bottom);
          return <g key={`y-${tick}`}><line className="comparison-grid" x1={left} x2={width - right} y1={py} y2={py} /><text className="comparison-axis-label" x={left - 10} y={py + 4} textAnchor="end">10^{tick}</text></g>;
        })}
        {series.map((item, seriesIndex) => {
          const polyline = item.points.map(point => `${x(point.x)},${y(point.training_time_mean)}`).join(' ');
          return <g className={`comparison-series s${seriesIndex % 8}`} key={item.id}>
            {item.points.length > 1 && <polyline points={polyline} className="comparison-series-line" />}
            {item.points.map(point => {
              const py = y(point.training_time_mean);
              const topError = point.training_time_max > 0 ? y(point.training_time_max) : py;
              const bottomError = point.training_time_min > 0 ? y(point.training_time_min) : py;
              return <g key={`${item.id}-${point.dataset_id}`}>
                <line className="comparison-error" x1={x(point.x)} x2={x(point.x)} y1={topError} y2={bottomError} />
                <circle className="comparison-series-point" cx={x(point.x)} cy={py} r={4}>
                  <title>{`${item.name} · ${point.dataset_name}\n${xLabel}: ${point.x}\nTraining: ${format(point.training_time_mean)} s ± ${format(point.training_time_std)}`}</title>
                </circle>
              </g>;
            })}
          </g>;
        })}
        <text className="comparison-axis-caption" x={(left + width - right) / 2} y={height - 14} textAnchor="middle">{xLabel} (log)</text>
        <text className="comparison-axis-caption" transform={`translate(20 ${(top + height - bottom) / 2}) rotate(-90)`} textAnchor="middle">Training Time (s, log)</text>
      </svg>
      <figcaption className="comparison-series-legend">
        {series.map((item, index) => <span className={`comparison-series s${index % 8}`} key={item.id}><i />{item.name}</span>)}
      </figcaption>
    </figure>
  );
}

export function ParameterImpactChart({
  analysis,
  parameter,
  metric,
}: {
  analysis: ComparisonAnalysis;
  parameter: string;
  metric: string;
}) {
  const points = analysis.parameter_points.filter(item => item.parameter === parameter && Number.isFinite(item.metrics[metric]));
  if (points.length < 2) return <div className="comparison-empty">No hay suficientes experimentos con valores numéricos para este parámetro y métrica.</div>;
  const width = 720, height = 390, left = 72, right = 28, top = 34, bottom = 58;
  const xs = points.map(item => item.x), ys = points.map(item => item.metrics[metric]);
  const xMin = Math.min(...xs), xMax = Math.max(...xs), yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xSpan = xMax - xMin || 1, ySpan = yMax - yMin || 1;
  const x = (value: number) => left + ((value - xMin) / xSpan) * (width - left - right);
  const y = (value: number) => height - bottom - ((value - yMin) / ySpan) * (height - top - bottom);
  const rho = analysis.varying_parameters.find(item => item.parameter === parameter)?.correlations?.[metric];
  return (
    <figure className="comparison-chart parameter-impact-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <line className="comparison-axis" x1={left} x2={left} y1={top} y2={height - bottom} />
        <line className="comparison-axis" x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} />
        {points.map((item, index) => <g className={`comparison-series s${index % 8}`} key={item.experiment_id}>
          <circle className="impact-point" cx={x(item.x)} cy={y(item.metrics[metric])} r={7}>
            <title>{`${item.experiment_name}\n${parameter}=${format(item.x)}\n${metric}=${format(item.metrics[metric])}`}</title>
          </circle>
          <text className="impact-label" x={x(item.x) + 8} y={y(item.metrics[metric]) - 8}>{item.experiment_name}</text>
        </g>)}
        <text className="comparison-axis-caption" x={(left + width - right) / 2} y={height - 13} textAnchor="middle">{parameter}</text>
        <text className="comparison-axis-caption" transform={`translate(18 ${(top + height - bottom) / 2}) rotate(-90)`} textAnchor="middle">{analysis.metric_specs[metric]?.label || metric}</text>
      </svg>
      <figcaption>{rho ? `Spearman ρ=${format(rho.rho)} · p=${format(rho.p_value)} · n=${rho.n}` : 'Correlación Spearman no disponible.'}</figcaption>
    </figure>
  );
}

export function TradeoffChart({ analysis }: { analysis: ComparisonAnalysis }) {
  const points = analysis.tradeoff.filter(item => item.training_time > 0 && Number.isFinite(item.score));
  if (!points.length) return <div className="comparison-empty">Sin datos suficientes para el análisis costo–desempeño.</div>;
  const width = 720, height = 390, left = 72, right = 28, top = 34, bottom = 58;
  const xs = points.map(item => Math.log10(item.training_time)), ys = points.map(item => item.score);
  const xMin = Math.min(...xs), xMax = Math.max(...xs), yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xSpan = xMax - xMin || 1, ySpan = yMax - yMin || 1;
  const x = (value: number) => left + ((Math.log10(value) - xMin) / xSpan) * (width - left - right);
  const y = (value: number) => height - bottom - ((value - yMin) / ySpan) * (height - top - bottom);
  return (
    <figure className="comparison-chart tradeoff-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <line className="comparison-axis" x1={left} x2={left} y1={top} y2={height - bottom} />
        <line className="comparison-axis" x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} />
        {points.map((item, index) => <g className={`comparison-series s${index % 8}`} key={item.experiment_id}>
          <circle className="impact-point" cx={x(item.training_time)} cy={y(item.score)} r={7}>
            <title>{`${item.experiment_name}\nTraining=${format(item.training_time)} s\n${analysis.metric_specs[analysis.primary_metric]?.label}: ${format(item.score)}\nModel Size=${format(item.model_size)}`}</title>
          </circle>
          <text className="impact-label" x={x(item.training_time) + 8} y={y(item.score) - 8}>{item.experiment_name}</text>
        </g>)}
        <text className="comparison-axis-caption" x={(left + width - right) / 2} y={height - 13} textAnchor="middle">Training Time (s, log)</text>
        <text className="comparison-axis-caption" transform={`translate(18 ${(top + height - bottom) / 2}) rotate(-90)`} textAnchor="middle">{analysis.metric_specs[analysis.primary_metric]?.label}</text>
      </svg>
      <figcaption>Relación entre desempeño y costo computacional; Model Size se muestra en el detalle de cada punto.</figcaption>
    </figure>
  );
}
