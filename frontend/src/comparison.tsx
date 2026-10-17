import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, download } from './api';
import { BenchmarkMetricChart } from './benchmark';
import {
  DistributionBoxPlot,
  ParameterImpactChart,
  ScalingChart,
  TradeoffChart,
  WilcoxonMatrix,
} from './comparison-charts';
import type {
  ComparisonAnalysis,
  ComparisonReport,
  ComparisonReportSummary,
  ExperimentGroup,
} from './lab-types';
import { useI18n } from './i18n';

function format(value: number | null | undefined, digits = 4) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  if (Math.abs(value) >= 10000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) return value.toExponential(2);
  return value.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

function Header({ title, subtitle, children }: React.PropsWithChildren<{ title: string; subtitle?: string }>) {
  return (
    <header className="page-header">
      <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
      {children && <div className="actions">{children}</div>}
    </header>
  );
}

function Panel({ title, children }: React.PropsWithChildren<{ title: string }>) {
  return <section className="panel"><h3>{title}</h3>{children}</section>;
}

const REGRESSION_METRICS: Array<[string, string]> = [
  ['r2_test', 'R² Test'],
  ['rmse_test', 'RMSE Test'],
  ['mae_test', 'MAE Test'],
  ['model_size', 'Model Size'],
  ['training_time', 'Training Time'],
];

const CLASSIFICATION_METRICS: Array<[string, string]> = [
  ['accuracy_test', 'Accuracy Test'],
  ['f1_macro_test', 'F1 macro Test'],
  ['precision_macro_test', 'Precision macro Test'],
  ['recall_macro_test', 'Recall macro Test'],
  ['model_size', 'Model Size'],
  ['training_time', 'Training Time'],
];

function metricOptions(taskType: 'regression' | 'classification') {
  return taskType === 'regression' ? REGRESSION_METRICS : CLASSIFICATION_METRICS;
}

function ExperimentSelector({
  groups,
  selected,
  onChange,
}: {
  groups: ExperimentGroup[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter(item => item !== id) : [...selected, id]);
  }
  return (
    <div className="comparison-experiment-selector">
      {groups.length === 0 && <p>No hay experimentos de este tipo disponibles.</p>}
      {groups.map(group => (
        <label className="comparison-experiment-option" key={group.id}>
          <input type="checkbox" checked={selected.includes(group.id)} onChange={() => toggle(group.id)} />
          <span>
            <b>{group.name}</b>
            <small>{group.preset_name || 'Sin perfil'} · {group.summary.completed_runs}/{group.summary.total_runs} corridas completadas</small>
            <small>Gen={String(group.parameters?.generations ?? '—')} · Pop={String(group.parameters?.Individuals ?? '—')} · Genes={String(group.parameters?.GenesIndividuals ?? '—')}</small>
          </span>
        </label>
      ))}
    </div>
  );
}

function ParameterMatrix({ analysis }: { analysis: ComparisonAnalysis }) {
  const parameters = analysis.varying_parameters;
  if (!parameters.length) return <p>No se detectaron parámetros diferentes entre los experimentos seleccionados.</p>;
  return (
    <div className="table-scroll">
      <table className="comparison-table">
        <thead><tr><th>Experimento</th>{parameters.map(item => <th key={item.parameter}>{item.parameter}</th>)}</tr></thead>
        <tbody>
          {analysis.experiments.map(experiment => (
            <tr key={experiment.id}>
              <th>{experiment.name}</th>
              {parameters.map(parameter => {
                const item = parameter.values.find(value => value.experiment_id === experiment.id);
                return <td key={parameter.parameter}>{String(item?.value ?? '—')}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DatasetMatrix({ analysis }: { analysis: ComparisonAnalysis }) {
  const metric = analysis.primary_metric;
  return (
    <div className="table-scroll">
      <table className="comparison-table">
        <thead>
          <tr>
            <th>Dataset</th><th>Filas</th><th>Features</th><th>Points</th>
            {analysis.experiments.map(experiment => <th key={experiment.id}>{experiment.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {analysis.datasets.map(dataset => (
            <tr key={dataset.dataset_id}>
              <th>{dataset.dataset_name}</th>
              <td>{dataset.rows}</td><td>{dataset.features}</td><td>{dataset.points}</td>
              {analysis.experiments.map(experiment => {
                const summary = dataset.experiments?.[experiment.id]?.metrics?.[metric];
                return <td key={experiment.id}>{summary ? `${format(summary.mean)} ± ${format(summary.std)}` : '—'}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankingTable({ analysis }: { analysis: ComparisonAnalysis }) {
  const rows = analysis.rankings[analysis.primary_metric] || [];
  return (
    <div className="table-scroll">
      <table className="comparison-table">
        <thead><tr><th>Rank</th><th>Experimento</th><th>Media</th><th>Std</th><th>Mín.</th><th>Máx.</th><th>n</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.experiment_id}><td>{row.rank}</td><th>{row.label}</th><td>{format(row.mean)}</td><td>{format(row.std)}</td><td>{format(row.min)}</td><td>{format(row.max)}</td><td>{row.n}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function ParameterImpactSection({ analysis }: { analysis: ComparisonAnalysis }) {
  const numeric = analysis.varying_parameters.filter(item => item.numeric);
  const [parameter, setParameter] = useState(numeric[0]?.parameter || '');
  const [metric, setMetric] = useState(analysis.primary_metric);
  useEffect(() => {
    if (!numeric.some(item => item.parameter === parameter)) setParameter(numeric[0]?.parameter || '');
  }, [analysis.generated_at, numeric.length]);
  useEffect(() => setMetric(analysis.primary_metric), [analysis.primary_metric]);
  if (!numeric.length) return <p>No existen parámetros numéricos variables entre los experimentos seleccionados.</p>;
  return (
    <>
      <div className="comparison-controls compact-controls">
        <label>Parámetro<select value={parameter} onChange={event => setParameter(event.target.value)}>{numeric.map(item => <option key={item.parameter} value={item.parameter}>{item.parameter}</option>)}</select></label>
        <label>Métrica<select value={metric} onChange={event => setMetric(event.target.value)}>{Object.entries(analysis.metric_specs).map(([key, spec]) => <option key={key} value={key}>{spec.label}</option>)}</select></label>
      </div>
      <ParameterImpactChart analysis={analysis} parameter={parameter} metric={metric} />
      <p className="comparison-note">La correlación de Spearman resume asociación monotónica; no implica causalidad. Con pocos experimentos debe interpretarse únicamente como evidencia exploratoria.</p>
    </>
  );
}

export function ComparisonAnalysisView({ analysis }: { analysis: ComparisonAnalysis }) {
  const primaryRows = analysis.rankings[analysis.primary_metric] || [];
  const benchmarkOrder = analysis.task_type === 'regression'
    ? ['r2_test', 'rmse_test', 'model_size', 'training_time']
    : ['accuracy_test', 'f1_macro_test', 'model_size', 'training_time'];
  const benchmarks = benchmarkOrder.map(metric => analysis.benchmarks.find(item => item.metric === metric)).filter(Boolean) as ComparisonAnalysis['benchmarks'];
  return (
    <div className="comparison-analysis">
      <div className="metric-strip comparison-summary-strip">
        <div className="metric"><small>Experimentos</small><strong>{analysis.experiments.length}</strong></div>
        <div className="metric"><small>Datasets</small><strong>{analysis.datasets.length}</strong></div>
        <div className="metric"><small>Datasets comunes</small><strong>{analysis.coverage?.common_dataset_ids?.length ?? 0}</strong></div>
        <div className="metric"><small>Métrica principal</small><strong>{analysis.metric_specs[analysis.primary_metric]?.label}</strong></div>
        <div className="metric"><small>α</small><strong>{analysis.alpha}</strong></div>
      </div>

      {!analysis.coverage?.comparable_on_common_datasets && <div className="warning comparison-warning">Los experimentos no comparten ningún dataset. Los análisis de desempeño global se muestran con los datos disponibles, pero no constituyen una comparación pareada equivalente. Wilcoxon no estará disponible hasta que existan datasets comunes.</div>}
      <Panel title="Configuraciones comparadas"><ParameterMatrix analysis={analysis} /></Panel>
      <Panel title={`Ranking · ${analysis.metric_specs[analysis.primary_metric]?.label || analysis.primary_metric}`}><RankingTable analysis={analysis} /></Panel>
      <Panel title="Resultados por dataset"><DatasetMatrix analysis={analysis} /></Panel>

      <Panel title="Gráficas comparativas tipo SRBench">
        <p className="comparison-note">Cada fila representa un experimento/configuración; el punto grande es la media, la línea horizontal es mínimo–máximo y los puntos pequeños son corridas individuales.</p>
        <div className="benchmark-grid">
          {benchmarks.map(item => <BenchmarkMetricChart
            key={item.metric}
            title={item.title}
            rows={item.rows.map(row => ({ label: row.label, values: row.values }))}
            descending={item.higher_better}
            logScale={item.log_scale}
            includeZero={!item.log_scale}
            fixedMax={item.metric === 'r2_test' || item.metric === 'accuracy_test' || item.metric === 'f1_macro_test' ? 1 : undefined}
            emptyMessage={`Sin datos para ${item.title}.`}
          />)}
        </div>
      </Panel>

      <Panel title={`Distribución de corridas · ${analysis.metric_specs[analysis.primary_metric]?.label}`}>
        <DistributionBoxPlot title={analysis.metric_specs[analysis.primary_metric]?.label || analysis.primary_metric} rows={primaryRows} logScale={analysis.metric_specs[analysis.primary_metric]?.log} />
      </Panel>

      <Panel title="Matriz Wilcoxon entre experimentos">
        <WilcoxonMatrix analysis={analysis} />
      </Panel>

      <Panel title="Impacto de parámetros">
        <ParameterImpactSection analysis={analysis} />
      </Panel>

      <Panel title="Costo computacional vs desempeño">
        <TradeoffChart analysis={analysis} />
      </Panel>

      <Panel title="Escalamiento computacional">
        <div className="comparison-scaling-grid">
          <ScalingChart title="Training Time vs Dataset Nsamples" xLabel="Dataset Nsamples" points={analysis.computational.samples} />
          <ScalingChart title="Training Time vs Dataset Nfeatures" xLabel="Dataset Nfeatures" points={analysis.computational.features} />
          <ScalingChart title="Training Time vs Dataset Npoints" xLabel="Dataset Npoints = rows × features" points={analysis.computational.points} />
        </div>
      </Panel>

      {analysis.notes?.length > 0 && <Panel title="Notas de interpretación"><ul className="comparison-notes">{analysis.notes.map(note => <li key={note}>{note}</li>)}</ul></Panel>}
    </div>
  );
}

export function ComparisonReports() {
  const { language } = useI18n();
  const tr = (es: string, en: string) => language === 'es' ? es : en;
  const navigate = useNavigate();
  const [groups, setGroups] = useState<ExperimentGroup[]>([]);
  const [reports, setReports] = useState<ComparisonReportSummary[]>([]);
  const [taskType, setTaskType] = useState<'regression' | 'classification'>('regression');
  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [metric, setMetric] = useState('r2_test');
  const [alpha, setAlpha] = useState(0.05);
  const [preview, setPreview] = useState<ComparisonAnalysis | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  function load() {
    Promise.all([
      api<ExperimentGroup[]>('/experiment-groups'),
      api<ComparisonReportSummary[]>('/comparison-reports'),
    ]).then(([experimentGroups, saved]) => {
      setGroups(experimentGroups);
      setReports(saved);
    }).catch(reason => setError(reason.message));
  }
  useEffect(load, []);
  useEffect(() => {
    setSelected([]);
    setPreview(null);
    setMetric(taskType === 'regression' ? 'r2_test' : 'f1_macro_test');
  }, [taskType]);
  const available = useMemo(() => groups.filter(group => group.task_type === taskType && group.summary.completed_runs > 0), [groups, taskType]);

  async function generatePreview() {
    if (selected.length < 2) return setError(tr('Seleccione al menos dos experimentos.', 'Select at least two experiments.'));
    setBusy(true); setError('');
    try {
      const result = await api<ComparisonAnalysis>('/comparison-reports/preview', {
        method: 'POST',
        body: JSON.stringify({ task_type: taskType, experiment_ids: selected, primary_metric: metric, alpha }),
      });
      setPreview(result);
    } catch (reason: any) { setError(reason.message); }
    finally { setBusy(false); }
  }

  async function saveReport() {
    if (!name.trim()) return setError(tr('Capture un nombre para guardar el reporte.', 'Enter a report name.'));
    if (selected.length < 2) return setError(tr('Seleccione al menos dos experimentos.', 'Select at least two experiments.'));
    setBusy(true); setError('');
    try {
      const result = await api<ComparisonReport>('/comparison-reports', {
        method: 'POST',
        body: JSON.stringify({ name, description, task_type: taskType, experiment_ids: selected, primary_metric: metric, alpha }),
      });
      navigate(`/comparisons/${result.id}`);
    } catch (reason: any) { setError(reason.message); }
    finally { setBusy(false); }
  }

  async function remove(report: ComparisonReportSummary) {
    if (!window.confirm(tr(`¿Eliminar el comparativo “${report.name}”?`, `Delete comparison “${report.name}”?`))) return;
    try { await api(`/comparison-reports/${report.id}`, { method: 'DELETE' }); load(); }
    catch (reason: any) { setError(reason.message); }
  }

  return (
    <>
      <Header title={tr('Comparativos y reportes', 'Comparisons and reports')} subtitle={tr('Integre experimentos del mismo tipo para estudiar desempeño, variabilidad, parámetros y costo computacional.', 'Combine experiments of the same type to study performance, variability, parameters and computational cost.')} />
      {error && <div className="error">{error}</div>}
      <Panel title={tr('Nuevo comparativo', 'New comparison')}>
        <div className="comparison-controls">
          <label>{tr('Tipo', 'Type')}<select value={taskType} onChange={event => setTaskType(event.target.value as any)}><option value="regression">Regresión</option><option value="classification">Clasificación</option></select></label>
          <label>{tr('Métrica principal', 'Primary metric')}<select value={metric} onChange={event => setMetric(event.target.value)}>{metricOptions(taskType).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label>α<input type="number" min="0.001" max="0.49" step="0.01" value={alpha} onChange={event => setAlpha(Number(event.target.value))} /></label>
          <label>{tr('Nombre del reporte', 'Report name')}<input value={name} onChange={event => setName(event.target.value)} placeholder="M5GP perfiles 15-40-128 generaciones" /></label>
        </div>
        <label>{tr('Descripción', 'Description')}<textarea value={description} onChange={event => setDescription(event.target.value)} rows={2} /></label>
        <h4>{tr('Seleccione experimentos', 'Select experiments')}</h4>
        <ExperimentSelector groups={available} selected={selected} onChange={setSelected} />
        <div className="actions comparison-actions">
          <button className="secondary button" disabled={busy} onClick={generatePreview}>{busy ? tr('Procesando…', 'Processing…') : tr('Generar vista previa', 'Generate preview')}</button>
          <button className="primary button" disabled={busy} onClick={saveReport}>{tr('Guardar reporte', 'Save report')}</button>
        </div>
      </Panel>
      {preview && <><Header title={tr('Vista previa', 'Preview')} subtitle={tr('El análisis aún no ha sido guardado.', 'This analysis has not been saved yet.')} /><ComparisonAnalysisView analysis={preview} /></>}
      <Panel title={tr('Reportes guardados', 'Saved reports')}>
        <div className="comparison-report-grid">
          {reports.map(report => <article className="comparison-report-card" key={report.id}>
            <div><h4>{report.name}</h4><p>{report.description || '—'}</p><small>{report.task_type} · {report.summary.experiment_count} experimentos · {report.summary.dataset_count} datasets</small></div>
            <div className="actions"><Link className="primary button compact" to={`/comparisons/${report.id}`}>{tr('Abrir', 'Open')}</Link><button className="danger button compact" onClick={() => remove(report)}>{tr('Eliminar', 'Delete')}</button></div>
          </article>)}
          {reports.length === 0 && <p>{tr('Todavía no hay reportes comparativos guardados.', 'There are no saved comparison reports yet.')}</p>}
        </div>
      </Panel>
    </>
  );
}

export function ComparisonReportDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { language } = useI18n();
  const tr = (es: string, en: string) => language === 'es' ? es : en;
  const [report, setReport] = useState<ComparisonReport | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = () => id && api<ComparisonReport>(`/comparison-reports/${id}`).then(setReport).catch(reason => setError(reason.message));
  useEffect(() => { load(); }, [id]);
  async function refresh() {
    if (!id) return;
    setBusy(true); setError('');
    try { setReport(await api<ComparisonReport>(`/comparison-reports/${id}/refresh`, { method: 'POST' })); }
    catch (reason: any) { setError(reason.message); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!id || !report || !window.confirm(tr(`¿Eliminar “${report.name}”?`, `Delete “${report.name}”?`))) return;
    try { await api(`/comparison-reports/${id}`, { method: 'DELETE' }); navigate('/comparisons'); }
    catch (reason: any) { setError(reason.message); }
  }
  if (!report) return <>{error ? <div className="error">{error}</div> : <div className="center">Cargando comparativo…</div>}</>;
  return (
    <>
      <Header title={report.name} subtitle={report.description || tr('Reporte comparativo guardado.', 'Saved comparison report.')}>
        <Link className="secondary button" to="/comparisons">{tr('Volver', 'Back')}</Link>
        <button className="secondary button" disabled={busy} onClick={refresh}>{tr('Actualizar análisis', 'Refresh analysis')}</button>
        <button className="secondary button" onClick={() => download(`/comparison-reports/${report.id}/export/json`, `${report.name}_comparativo.json`)}>JSON</button>
        <button className="secondary button" onClick={() => download(`/comparison-reports/${report.id}/export/xlsx`, `${report.name}_comparativo.xlsx`)}>Excel</button>
        <button className="danger button" onClick={remove}>{tr('Eliminar', 'Delete')}</button>
      </Header>
      {error && <div className="error">{error}</div>}
      <p className="comparison-note">Generado: {new Date(report.analysis.generated_at).toLocaleString()} · Guardado: {new Date(report.updated_at).toLocaleString()}</p>
      <ComparisonAnalysisView analysis={report.analysis} />
    </>
  );
}
