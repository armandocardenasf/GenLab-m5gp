import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { api, download, downloadJson } from './api';
import { BenchmarkMetricChart } from './benchmark';
import { LineChart } from './charts';
import { Metric, Status } from './components';
import { useI18n } from './i18n';
import { ScatterPlot } from './scatter';
import type {
  Batch,
  BenchmarkDataset,
  DatasetAggregate,
  DatasetRunResult,
  ExperimentGroup,
  ExperimentResults,
  MetricSections,
  ParameterPreset,
  RunContext,
} from './lab-types';
import type {
  Dataset,
  Experiment,
  ExperimentVisualization,
  GenerationPoint,
  GPU,
} from './types';

const ACTIVE_STATUSES = ['reserved', 'running', 'cancelling'];

function tr(language: 'es' | 'en', es: string, en: string): string {
  return language === 'es' ? es : en;
}

function Header({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children?: React.ReactNode;
}) {
  return (
    <header>
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {children}
    </header>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function formatNumber(value: unknown, digits = 4): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return value.toFixed(digits);
}

function sectionLabel(section: string, language: 'es' | 'en'): string {
  if (section === 'train') return 'Train';
  if (section === 'test') return 'Test';
  if (section === 'execution') return tr(language, 'Ejecución', 'Execution');
  return section;
}

function metricLabel(metric: string): string {
  const labels: Record<string, string> = {
    r2: 'R²',
    rmse: 'RMSE',
    mse: 'MSE',
    mae: 'MAE',
    accuracy: 'Accuracy',
    f1_macro: 'F1 macro',
    precision_macro: 'Precision macro',
    recall_macro: 'Recall macro',
    model_size: 'Model Size',
    training_time: 'Training Time (s)',
  };
  return labels[metric] || metric;
}

function safeDownloadName(value: string): string {
  const cleaned = value.trim().replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[_\.]+|[_\.]+$/g, '');
  return cleaned || 'genlab_results';
}

function ProgressCell({
  progress,
  status,
  language,
}: {
  progress: Record<string, any> | undefined;
  status: string;
  language: 'es' | 'en';
}) {
  const percent = Math.min(100, Math.max(0, Number(progress?.percent || (status === 'completed' ? 100 : 0))));
  const generation = Number(progress?.generation);
  const total = Number(progress?.total_generations);
  const generationText = Number.isFinite(generation) && Number.isFinite(total) && total > 0
    ? ` · G ${generation}/${total}`
    : '';
  return (
    <div className="run-progress-cell" title={String(progress?.message || '')}>
      <div className="progress-track compact" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <small>{percent}%{generationText || (status === 'queued' ? ` · ${tr(language, 'en cola', 'queued')}` : '')}</small>
    </div>
  );
}

function statusIsActive(status: string): boolean {
  return ACTIVE_STATUSES.includes(status);
}

function usePolling<T>(path: string, interval = 4000) {
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    const load = () =>
      api<T>(path)
        .then(result => {
          if (mounted) {
            setValue(result);
            setError('');
          }
        })
        .catch(reason => {
          if (mounted) setError(reason.message);
        });
    load();
    const timer = window.setInterval(load, interval);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [path, interval]);

  return { value, error, setValue };
}

function MetricsTable({
  sections,
  language,
}: {
  sections: MetricSections | undefined;
  language: 'es' | 'en';
}) {
  if (!sections || Object.keys(sections).length === 0) {
    return <p>{tr(language, 'Todavía no hay métricas agregadas.', 'No aggregate metrics are available yet.')}</p>;
  }
  const rows = Object.entries(sections).flatMap(([section, metrics]) =>
    Object.entries(metrics).map(([metric, values]) => ({
      section,
      metric,
      values,
    })),
  );
  if (rows.length === 0) {
    return <p>{tr(language, 'Todavía no hay métricas agregadas.', 'No aggregate metrics are available yet.')}</p>;
  }
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{tr(language, 'Conjunto', 'Split')}</th>
            <th>{tr(language, 'Métrica', 'Metric')}</th>
            <th>{tr(language, 'Media', 'Mean')}</th>
            <th>{tr(language, 'Desv. est.', 'Std. dev.')}</th>
            <th>Mín.</th>
            <th>Máx.</th>
            <th>n</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={`${row.section}-${row.metric}`}>
              <td>{sectionLabel(row.section, language)}</td>
              <td>{metricLabel(row.metric)}</td>
              <td>{formatNumber(row.values.mean)}</td>
              <td>{formatNumber(row.values.std)}</td>
              <td>{formatNumber(row.values.min)}</td>
              <td>{formatNumber(row.values.max)}</td>
              <td>{row.values.n}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DashboardV2() {
  const { language, locale } = useI18n();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [groups, setGroups] = useState<ExperimentGroup[]>([]);
  const [runs, setRuns] = useState<Experiment[]>([]);
  const [gpus, setGpus] = useState<GPU[]>([]);

  useEffect(() => {
    const load = () =>
      Promise.all([
        api<Dataset[]>('/datasets').then(setDatasets),
        api<ExperimentGroup[]>('/experiment-groups').then(setGroups),
        api<Experiment[]>('/runs').then(setRuns),
        api<GPU[]>('/gpus').then(setGpus),
      ]).catch(() => undefined);
    load();
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, []);

  const activeRuns = runs.filter(run => statusIsActive(run.status) || run.status === 'queued').length;
  return (
    <>
      <Header
        title={tr(language, 'Resumen', 'Overview')}
        subtitle={tr(
          language,
          'Estado general de experimentos, corridas, datasets y recursos GPU.',
          'General status of experiments, runs, datasets and GPU resources.',
        )}
      />
      <div className="metrics">
        <Metric label={tr(language, 'Datasets', 'Datasets')} value={datasets.length} />
        <Metric label={tr(language, 'Experimentos', 'Experiments')} value={groups.length} />
        <Metric label={tr(language, 'Corridas activas/en cola', 'Active/queued runs')} value={activeRuns} />
        <Metric
          label={tr(language, 'GPUs disponibles', 'Available GPUs')}
          value={`${gpus.filter(gpu => !gpu.busy).length}/${gpus.length}`}
        />
      </div>
      <Panel title={tr(language, 'Experimentos recientes', 'Recent experiments')}>
        {groups.length === 0 ? (
          <p>{tr(language, 'Aún no se han definido experimentos.', 'No experiments have been defined yet.')}</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{tr(language, 'Nombre', 'Name')}</th>
                  <th>Datasets</th>
                  <th>{tr(language, 'Corridas', 'Runs')}</th>
                  <th>{tr(language, 'Estado', 'Status')}</th>
                  <th>{tr(language, 'Fecha', 'Date')}</th>
                </tr>
              </thead>
              <tbody>
                {groups.slice(0, 8).map(group => (
                  <tr key={group.id}>
                    <td><Link to={`/experiments/${group.id}`}>{group.name}</Link></td>
                    <td>{group.datasets.length}</td>
                    <td>{group.summary.completed_runs}/{group.summary.total_runs}</td>
                    <td><Status value={group.status} /></td>
                    <td>{new Date(group.created_at).toLocaleString(locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

export function ExperimentGroups() {
  const { language, locale } = useI18n();
  const { value: groups, error } = usePolling<ExperimentGroup[]>('/experiment-groups');
  return (
    <>
      <Header
        title={tr(language, 'Experimentos', 'Experiments')}
        subtitle={tr(
          language,
          'Cada experimento agrupa datasets y múltiples corridas M5GP para análisis conjunto.',
          'Each experiment groups datasets and multiple M5GP runs for joint analysis.',
        )}
      >
        <Link className="primary button" to="/experiments/new">
          {tr(language, 'Nuevo experimento', 'New experiment')}
        </Link>
      </Header>
      {error && <p className="error">{error}</p>}
      <Panel title={tr(language, 'Historial', 'History')}>
        {!groups ? (
          <p>{tr(language, 'Cargando…', 'Loading…')}</p>
        ) : groups.length === 0 ? (
          <p>{tr(language, 'Todavía no hay experimentos.', 'There are no experiments yet.')}</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{tr(language, 'Nombre', 'Name')}</th>
                  <th>{tr(language, 'Tarea', 'Task')}</th>
                  <th>Datasets</th>
                  <th>{tr(language, 'Corridas', 'Runs')}</th>
                  <th>{tr(language, 'Estado', 'Status')}</th>
                  <th>{tr(language, 'Fecha', 'Date')}</th>
                </tr>
              </thead>
              <tbody>
                {groups.map(group => (
                  <tr key={group.id}>
                    <td><Link to={`/experiments/${group.id}`}>{group.name}</Link></td>
                    <td>{group.task_type}</td>
                    <td>{group.datasets.length}</td>
                    <td>{group.summary.completed_runs}/{group.summary.total_runs}</td>
                    <td><Status value={group.status} /></td>
                    <td>{new Date(group.created_at).toLocaleString(locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

export function NewExperimentGroup() {
  const { language } = useI18n();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [presets, setPresets] = useState<ParameterPreset[]>([]);
  const [name, setName] = useState('');
  const [task, setTask] = useState<'regression' | 'classification'>('regression');
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [presetId, setPresetId] = useState(searchParams.get('preset') || '');
  const [runsPerDataset, setRunsPerDataset] = useState(5);
  const [strategy, setStrategy] = useState<'holdout' | 'kfold'>('holdout');
  const [trainSize, setTrainSize] = useState(0.75);
  const [testSize, setTestSize] = useState(0.25);
  const [folds, setFolds] = useState(5);
  const [randomState, setRandomState] = useState(42);
  const [shuffle, setShuffle] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api<Dataset[]>('/datasets').then(setDatasets),
      api<ParameterPreset[]>('/parameter-presets').then(items => {
        setPresets(items);
        if (!presetId) {
          setPresetId(items.find(item => item.is_default)?.id || 'system-standard');
        }
      }),
    ]).catch(reason => setError(reason.message));
  }, []);

  const availablePresets = useMemo(
    () => presets.filter(preset => preset.task_type === 'both' || preset.task_type === task),
    [presets, task],
  );
  const selectedPreset = presets.find(preset => preset.id === presetId);
  const datasetCount = Object.keys(selected).length;
  const totalRuns = datasetCount * runsPerDataset * (strategy === 'kfold' ? folds : 1);

  useEffect(() => {
    if (availablePresets.length === 0) {
      setPresetId('');
      return;
    }
    if (!availablePresets.some(preset => preset.id === presetId)) {
      const next = availablePresets.find(preset => preset.is_default)
        || availablePresets.find(preset => preset.id === 'system-standard')
        || availablePresets[0];
      setPresetId(next?.id || '');
    }
  }, [task, presets.length]);

  function toggleDataset(dataset: Dataset, checked: boolean) {
    setSelected(current => {
      const next = { ...current };
      if (checked) {
        next[dataset.id] = next[dataset.id] || dataset.column_names[dataset.column_names.length - 1] || '';
      } else {
        delete next[dataset.id];
      }
      return next;
    });
  }

  async function save(execute: boolean) {
    setError('');
    if (!name.trim()) {
      setError(tr(language, 'Capture el nombre del experimento.', 'Enter an experiment name.'));
      return;
    }
    if (datasetCount === 0) {
      setError(tr(language, 'Seleccione al menos un dataset.', 'Select at least one dataset.'));
      return;
    }
    if (strategy === 'holdout' && Math.abs(trainSize + testSize - 1) > 1e-6) {
      setError(tr(language, 'Train + Test debe ser igual a 1.0.', 'Train + Test must equal 1.0.'));
      return;
    }
    setBusy(true);
    try {
      const created = await api<ExperimentGroup>('/experiment-groups', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          task_type: task,
          datasets: Object.entries(selected).map(([dataset_id, target_column]) => ({
            dataset_id,
            target_column,
          })),
          runs_per_dataset: runsPerDataset,
          preset_name: selectedPreset?.name || null,
          parameters: selectedPreset?.parameters || {},
          validation: {
            strategy,
            train_size: trainSize,
            test_size: testSize,
            random_state: randomState,
            folds,
            shuffle,
          },
        }),
      });
      if (execute) {
        await api(`/experiment-groups/${created.id}/run`, { method: 'POST' });
      }
      navigate(`/experiments/${created.id}`);
    } catch (reason: any) {
      setError(reason.message);
      setBusy(false);
    }
  }

  return (
    <>
      <Header
        title={tr(language, 'Nuevo experimento', 'New experiment')}
        subtitle={tr(
          language,
          'Configure uno o varios datasets, repeticiones, partición Train/Test y perfil de ejecución.',
          'Configure one or more datasets, repetitions, Train/Test split and execution profile.',
        )}
      />
      <Panel title={tr(language, 'Configuración general', 'General configuration')}>
        <form className="grid-form" onSubmit={event => event.preventDefault()}>
          <label>
            {tr(language, 'Nombre', 'Name')}
            <input value={name} onChange={event => setName(event.target.value)} minLength={2} />
          </label>
          <label>
            {tr(language, 'Tipo de tarea', 'Task type')}
            <select value={task} onChange={event => setTask(event.target.value as 'regression' | 'classification')}>
              <option value="regression">{tr(language, 'Regresión simbólica', 'Symbolic regression')}</option>
              <option value="classification">{tr(language, 'Clasificación', 'Classification')}</option>
            </select>
          </label>
          <label>
            {tr(language, 'Perfil de ejecución', 'Execution profile')}
            <select value={presetId} onChange={event => setPresetId(event.target.value)}>
              {availablePresets.map(preset => (
                <option value={preset.id} key={preset.id}>
                  {preset.name}{preset.system ? ' · GenLab' : ''}{preset.is_default ? ' · default' : ''}
                </option>
              ))}
            </select>
            {selectedPreset && <small>{selectedPreset.description}</small>}
          </label>
          <label>
            {tr(language, 'Corridas por dataset', 'Runs per dataset')}
            <input type="number" min={1} max={100} value={runsPerDataset} onChange={event => setRunsPerDataset(Number(event.target.value))} />
          </label>
          <label>
            {tr(language, 'Estrategia de validación', 'Validation strategy')}
            <select value={strategy} onChange={event => setStrategy(event.target.value as 'holdout' | 'kfold')}>
              <option value="holdout">{tr(language, 'Partición aleatoria Train/Test', 'Random Train/Test split')}</option>
              <option value="kfold">K-fold</option>
            </select>
          </label>
          <label>
            {tr(language, 'Semilla base', 'Base random seed')}
            <input type="number" value={randomState} onChange={event => setRandomState(Number(event.target.value))} />
          </label>
          {strategy === 'holdout' ? (
            <>
              <label>
                Train
                <input type="number" min={0.05} max={0.95} step={0.05} value={trainSize} onChange={event => setTrainSize(Number(event.target.value))} />
              </label>
              <label>
                Test
                <input type="number" min={0.05} max={0.95} step={0.05} value={testSize} onChange={event => setTestSize(Number(event.target.value))} />
              </label>
            </>
          ) : (
            <>
              <label>
                {tr(language, 'Número de folds', 'Number of folds')}
                <input type="number" min={2} max={20} value={folds} onChange={event => setFolds(Number(event.target.value))} />
                <small>Train ≈ {((folds - 1) / folds).toFixed(3)} · Test ≈ {(1 / folds).toFixed(3)}</small>
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={shuffle} onChange={event => setShuffle(event.target.checked)} />
                {tr(language, 'Barajar antes de generar folds', 'Shuffle before creating folds')}
              </label>
            </>
          )}
          <div className="form-wide actions">
            <Link className="secondary button" to={`/parameters?preset=${encodeURIComponent(presetId)}`}>
              {tr(language, 'Parámetros avanzados', 'Advanced parameters')}
            </Link>
            <span className="execution-estimate">
              {tr(language, 'Corridas que se crearán:', 'Runs to be created:')} <b>{totalRuns}</b>
            </span>
          </div>
        </form>
      </Panel>

      <Panel title={tr(language, 'Datasets y variables objetivo', 'Datasets and target variables')}>
        {datasets.length === 0 ? (
          <p>{tr(language, 'Primero cargue al menos un dataset.', 'Upload at least one dataset first.')}</p>
        ) : (
          <div className="dataset-choice-list">
            {datasets.map(dataset => (
              <div className="dataset-choice" key={dataset.id}>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={dataset.id in selected}
                    onChange={event => toggleDataset(dataset, event.target.checked)}
                  />
                  <span><b>{dataset.name}</b><small>{dataset.original_name}</small></span>
                </label>
                {dataset.id in selected && (
                  <label>
                    {tr(language, 'Variable objetivo', 'Target variable')}
                    <select
                      value={selected[dataset.id]}
                      onChange={event => setSelected(current => ({ ...current, [dataset.id]: event.target.value }))}
                    >
                      {dataset.column_names.map(column => <option key={column}>{column}</option>)}
                    </select>
                  </label>
                )}
              </div>
            ))}
          </div>
        )}
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button className="secondary button" type="button" onClick={() => save(false)} disabled={busy}>
            {tr(language, 'Guardar experimento', 'Save experiment')}
          </button>
          <button className="primary button" type="button" onClick={() => save(true)} disabled={busy}>
            {busy ? tr(language, 'Procesando…', 'Processing…') : tr(language, 'Crear y ejecutar', 'Create and run')}
          </button>
        </div>
      </Panel>
    </>
  );
}

export function ExperimentGroupDetail() {
  const { language, locale } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const { value: group, error, setValue: setGroup } = usePolling<ExperimentGroup>(`/experiment-groups/${id}`, 3000);
  const [results, setResults] = useState<ExperimentResults | null>(null);
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (group && group.summary.completed_runs > 0) {
      api<ExperimentResults>(`/experiment-groups/${group.id}/results?max_points=1200`)
        .then(setResults)
        .catch(() => setResults(null));
    }
  }, [group?.summary.completed_runs, group?.id]);

  if (!group) return <p className={error ? 'error' : ''}>{error || tr(language, 'Cargando…', 'Loading…')}</p>;
  const currentGroup = group;

  async function execute() {
    setBusy(true);
    setActionError('');
    try {
      const updated = await api<ExperimentGroup>(`/experiment-groups/${currentGroup.id}/run`, { method: 'POST' });
      setGroup(updated);
    } catch (reason: any) {
      setActionError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(tr(language, `¿Eliminar el experimento “${currentGroup.name}” y sus corridas?`, `Delete experiment “${currentGroup.name}” and its runs?`))) return;
    setBusy(true);
    try {
      await api(`/experiment-groups/${currentGroup.id}`, { method: 'DELETE' });
      navigate('/experiments');
    } catch (reason: any) {
      setActionError(reason.message);
      setBusy(false);
    }
  }

  async function exportResults(format: 'json' | 'xlsx', datasetId?: string) {
    setActionError('');
    const query = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
    const dataset = datasetId ? currentGroup.datasets.find(item => item.dataset_id === datasetId) : null;
    const base = safeDownloadName(`${currentGroup.name}${dataset ? `_${dataset.dataset_name}` : ''}_resultados`);
    try {
      await download(
        `/experiment-groups/${currentGroup.id}/export/${format}${query}`,
        `${base}.${format === 'json' ? 'json' : 'xlsx'}`,
      );
    } catch (reason: any) {
      setActionError(reason.message);
    }
  }

  const validation = currentGroup.validation || {};
  const currentRuns = currentGroup.runs || [];
  const overallProgress = currentRuns.length > 0
    ? Math.round(currentRuns.reduce((total, run) => {
        const value = run.status === 'completed' ? 100 : Number(run.progress?.percent || 0);
        return total + Math.min(100, Math.max(0, value));
      }, 0) / currentRuns.length)
    : 0;
  const datasetAggregates = results?.by_dataset || currentGroup.summary.by_dataset || [];
  const benchmark: BenchmarkDataset[] = results?.benchmark || currentGroup.summary.benchmark || [];
  const benchmarkRows = (metric: keyof BenchmarkDataset['values']) => benchmark.map(dataset => ({
    label: dataset.dataset_name,
    values: dataset.values?.[metric] || [],
  }));

  return (
    <>
      <Header title={currentGroup.name} subtitle={currentGroup.id}>
        <div className="header-actions">
          <Status value={currentGroup.status} />
          {currentGroup.summary.total_runs === 0 && (
            <button className="primary button" onClick={execute} disabled={busy}>
              {tr(language, 'Ejecutar', 'Run')}
            </button>
          )}
          <button className="danger button" onClick={remove} disabled={busy || currentGroup.status === 'running'}>
            {tr(language, 'Eliminar', 'Delete')}
          </button>
        </div>
      </Header>
      {(error || actionError) && <p className="error">{error || actionError}</p>}
      <div className="metrics">
        <Metric label="Datasets" value={currentGroup.datasets.length} />
        <Metric label={tr(language, 'Corridas', 'Runs')} value={currentGroup.summary.total_runs} />
        <Metric label={tr(language, 'Finalizadas', 'Completed')} value={currentGroup.summary.completed_runs} />
        <Metric label={tr(language, 'Avance total', 'Overall progress')} value={`${overallProgress}%`} />
        <Metric label={tr(language, 'Perfil', 'Profile')} value={currentGroup.preset_name || '—'} />
      </div>

      {currentRuns.length > 0 && currentGroup.summary.completed_runs < currentGroup.summary.total_runs && (
        <Panel title={tr(language, 'Avance de las corridas', 'Run progress')}>
          <p className="panel-description">
            {tr(language, 'La vista se actualiza automáticamente cada tres segundos. El avance se calcula a partir de las generaciones reportadas por M5GP.', 'This view refreshes automatically every three seconds. Progress is derived from the generations reported by M5GP.')}
          </p>
          <div className="experiment-progress-summary">
            <div className="progress-track" role="progressbar" aria-valuenow={overallProgress} aria-valuemin={0} aria-valuemax={100}>
              <div className="progress-fill" style={{ width: `${overallProgress}%` }} />
            </div>
            <b>{overallProgress}%</b>
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>{tr(language, 'Corrida', 'Run')}</th><th>Dataset</th><th>{tr(language, 'Estado', 'Status')}</th><th>{tr(language, 'Avance', 'Progress')}</th></tr></thead>
              <tbody>
                {currentRuns.map(run => {
                  const dataset = currentGroup.datasets.find(item => item.dataset_id === run.dataset_id);
                  return (
                    <tr key={`progress-${run.id}`}>
                      <td><Link to={`/runs/${run.id}`}>{run.name}</Link></td>
                      <td>{dataset?.dataset_name || run.dataset_id}</td>
                      <td><Status value={run.status} /></td>
                      <td><ProgressCell progress={run.progress} status={run.status} language={language} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <Panel title={tr(language, 'Diseño experimental', 'Experimental design')}>
        <div className="configuration-summary lab-summary">
          <div><small>{tr(language, 'Tarea', 'Task')}</small><b>{currentGroup.task_type}</b></div>
          <div><small>{tr(language, 'Validación', 'Validation')}</small><b>{validation.strategy || 'holdout'}</b></div>
          <div><small>Train / Test</small><b>{formatNumber(validation.train_size, 3)} / {formatNumber(validation.test_size, 3)}</b></div>
          <div><small>{tr(language, 'Semilla', 'Seed')}</small><b>{validation.random_state ?? '—'}</b></div>
          <div><small>{tr(language, 'Corridas por dataset', 'Runs per dataset')}</small><b>{currentGroup.runs_per_dataset}</b></div>
          {validation.strategy === 'kfold' && <div><small>Folds</small><b>{validation.folds}</b></div>}
        </div>
        <div className="dataset-tags">
          {currentGroup.datasets.map(dataset => (
            <span key={dataset.dataset_id}>{dataset.dataset_name} → <b>{dataset.target_column}</b></span>
          ))}
        </div>
        <details>
          <summary>{tr(language, 'Parámetros M5GP del experimento', 'Experiment M5GP parameters')}</summary>
          <pre>{JSON.stringify(currentGroup.parameters, null, 2)}</pre>
        </details>
      </Panel>

      <Panel title={tr(language, 'Resultados agregados', 'Aggregate results')}>
        <div className="panel-toolbar">
          <span>{tr(language, 'Integración de todas las corridas finalizadas.', 'Integration of all completed runs.')}</span>
          <div className="actions">
            <button className="secondary button compact" onClick={() => exportResults('json')}>{tr(language, 'Exportar JSON', 'Export JSON')}</button>
            <button className="secondary button compact" onClick={() => exportResults('xlsx')}>{tr(language, 'Exportar Excel', 'Export Excel')}</button>
          </div>
        </div>
        <MetricsTable sections={results?.overall || currentGroup.summary.overall} language={language} />
      </Panel>

      {datasetAggregates.length > 0 && (
        <Panel title={tr(language, 'Resultados por dataset', 'Results by dataset')}>
          <div className="dataset-aggregate-grid">
            {datasetAggregates.map((dataset: DatasetAggregate) => {
              const runs = dataset.runs || [];
              return (
                <article className="aggregate-card" key={dataset.dataset_id}>
                  <div className="aggregate-card-heading">
                    <div>
                      <h4>{dataset.dataset_name}</h4>
                      <p>{tr(language, 'Objetivo', 'Target')}: <b>{dataset.target_column}</b> · {dataset.completed_runs}/{dataset.total_runs} {tr(language, 'corridas', 'runs')}</p>
                    </div>
                    <div className="actions">
                      <button className="secondary button compact" onClick={() => exportResults('json', dataset.dataset_id)}>JSON</button>
                      <button className="secondary button compact" onClick={() => exportResults('xlsx', dataset.dataset_id)}>Excel</button>
                    </div>
                  </div>
                  <MetricsTable sections={dataset.metrics} language={language} />
                  <details className="dataset-run-details">
                    <summary>{tr(language, 'Consultar corridas individuales', 'View individual runs')} ({runs.length})</summary>
                    {runs.length === 0 ? (
                      <p>{tr(language, 'Todavía no existen resultados individuales para este dataset.', 'There are no individual results for this dataset yet.')}</p>
                    ) : (
                      <div className="table-scroll">
                        <table className="compact-results-table">
                          <thead>
                            <tr>
                              <th>{tr(language, 'Corrida', 'Run')}</th>
                              <th>{tr(language, 'Estado', 'Status')}</th>
                              <th>{tr(language, 'Avance', 'Progress')}</th>
                              {currentGroup.task_type === 'regression' && <><th>R² Test</th><th>RMSE Test</th></>}
                              <th>Model Size</th>
                              <th>Training Time (s)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {runs.map((run: DatasetRunResult) => (
                              <tr key={run.run_id}>
                                <td><Link to={`/runs/${run.run_id}`}>R{(run.repeat_index ?? 0) + 1}{run.fold_index === null || run.fold_index === undefined ? '' : ` · F${run.fold_index + 1}`}</Link></td>
                                <td><Status value={run.status} /></td>
                                <td><ProgressCell progress={{ percent: run.progress_percent, generation: run.generation, total_generations: run.total_generations }} status={run.status} language={language} /></td>
                                {currentGroup.task_type === 'regression' && <><td>{formatNumber(run.r2_test)}</td><td>{formatNumber(run.rmse_test)}</td></>}
                                <td>{formatNumber(run.model_size, 2)}</td>
                                <td>{formatNumber(run.training_time, 2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </details>
                </article>
              );
            })}
          </div>
        </Panel>
      )}

      {currentGroup.task_type === 'regression' && benchmark.some(dataset => Object.values(dataset.values || {}).some(values => values.length > 0)) && (
        <Panel title={tr(language, 'Gráficas comparativas tipo SRBench', 'SRBench-style comparison charts')}>
          <p className="panel-description">
            {tr(language, 'Cada fila corresponde a un dataset. El punto grande representa la media, la línea horizontal el intervalo mínimo–máximo y los puntos pequeños muestran cada corrida individual.', 'Each row represents a dataset. The large point is the mean, the horizontal line is the min–max range, and the small points show the individual runs.')}
          </p>
          <div className="benchmark-grid">
            <BenchmarkMetricChart title="R² Test" rows={benchmarkRows('r2')} descending includeZero fixedMax={1} legend={tr(language, 'media · línea = mínimo–máximo · puntos pequeños = corridas individuales', 'mean · line = min–max · small points = individual runs')} emptyMessage={tr(language, 'Sin valores R².', 'No R² values.')} />
            <BenchmarkMetricChart title="RMSE Test" rows={benchmarkRows('rmse')} includeZero legend={tr(language, 'media · línea = mínimo–máximo · puntos pequeños = corridas individuales', 'mean · line = min–max · small points = individual runs')} emptyMessage={tr(language, 'Sin valores RMSE.', 'No RMSE values.')} />
            <BenchmarkMetricChart title="Model Size" rows={benchmarkRows('model_size')} logScale legend={tr(language, 'media · línea = mínimo–máximo · puntos pequeños = corridas individuales', 'mean · line = min–max · small points = individual runs')} emptyMessage={tr(language, 'Sin valores de tamaño de modelo.', 'No model-size values.')} />
            <BenchmarkMetricChart title="Training Time (s)" rows={benchmarkRows('training_time')} logScale legend={tr(language, 'media · línea = mínimo–máximo · puntos pequeños = corridas individuales', 'mean · line = min–max · small points = individual runs')} emptyMessage={tr(language, 'Sin tiempos de entrenamiento.', 'No training-time values.')} />
          </div>
        </Panel>
      )}

      {currentGroup.task_type === 'regression' && results && results.scatter.length > 0 && (
        <Panel title={tr(language, 'Valores observados vs. predichos', 'Observed vs. predicted values')}>
          <p className="panel-description">
            {tr(language, 'Nube de puntos agregada de las corridas finalizadas. Correlación de Pearson:', 'Aggregate point cloud from completed runs. Pearson correlation:')} <b>{formatNumber(results.correlation, 5)}</b>
          </p>
          <ScatterPlot
            points={results.scatter.map(point => ({
              x: point.actual,
              y: point.prediction,
              label: `${point.dataset_name} · ${point.run_id}`,
            }))}
            xLabel={tr(language, 'Valor observado', 'Observed value')}
            yLabel={tr(language, 'Predicción', 'Prediction')}
            emptyMessage={tr(language, 'No hay puntos disponibles.', 'No points are available.')}
          />
        </Panel>
      )}

      <Panel title={tr(language, 'Corridas individuales', 'Individual runs')}>
        {!currentRuns.length ? (
          <p>{tr(language, 'El experimento todavía no tiene corridas.', 'This experiment has no runs yet.')}</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{tr(language, 'Corrida', 'Run')}</th>
                  <th>{tr(language, 'Repetición', 'Repeat')}</th>
                  <th>Fold</th>
                  <th>Seed</th>
                  <th>{tr(language, 'Estado', 'Status')}</th>
                  <th>{tr(language, 'Avance', 'Progress')}</th>
                  {currentGroup.task_type === 'regression' && <><th>R² Test</th><th>RMSE Test</th></>}
                  <th>Model Size</th>
                  <th>Training Time (s)</th>
                  <th>{tr(language, 'Finalización', 'Finished')}</th>
                </tr>
              </thead>
              <tbody>
                {currentRuns.map(run => {
                  const metrics = run.metrics || {};
                  const test = (metrics as any).test || {};
                  return (
                    <tr key={run.id}>
                      <td><Link to={`/runs/${run.id}`}>{run.name}</Link></td>
                      <td>{run.repeat_index + 1}</td>
                      <td>{run.fold_index === null ? '—' : run.fold_index + 1}</td>
                      <td>{run.seed}</td>
                      <td><Status value={run.status} /></td>
                      <td><ProgressCell progress={run.progress} status={run.status} language={language} /></td>
                      {currentGroup.task_type === 'regression' && <><td>{formatNumber(test.r2)}</td><td>{formatNumber(test.rmse)}</td></>}
                      <td>{formatNumber((metrics as any).model_size, 2)}</td>
                      <td>{formatNumber((metrics as any).training_time, 2)}</td>
                      <td>{run.finished_at ? new Date(run.finished_at).toLocaleString(locale) : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

export function Runs() {
  const { language, locale } = useI18n();
  const { value: runs, error } = usePolling<Experiment[]>('/runs');
  return (
    <>
      <Header
        title={tr(language, 'Corridas', 'Runs')}
        subtitle={tr(
          language,
          'Ejecuciones individuales M5GP, incluidas las históricas creadas por versiones anteriores.',
          'Individual M5GP executions, including historical runs created by earlier versions.',
        )}
      />
      {error && <p className="error">{error}</p>}
      <Panel title={tr(language, 'Historial de corridas', 'Run history')}>
        {!runs ? <p>{tr(language, 'Cargando…', 'Loading…')}</p> : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>{tr(language, 'Nombre', 'Name')}</th><th>{tr(language, 'Tarea', 'Task')}</th><th>{tr(language, 'Estado', 'Status')}</th><th>{tr(language, 'Fecha', 'Date')}</th></tr></thead>
              <tbody>
                {runs.map(run => (
                  <tr key={run.id}>
                    <td><Link to={`/runs/${run.id}`}>{run.name}</Link></td>
                    <td>{run.task_type}</td>
                    <td><Status value={run.status} /></td>
                    <td>{new Date(run.created_at).toLocaleString(locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

export function RunDetail() {
  const { language, locale } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<Experiment | null>(null);
  const [context, setContext] = useState<RunContext | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [history, setHistory] = useState<GenerationPoint[]>([]);
  const [testResults, setTestResults] = useState<ExperimentVisualization['test_results'] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const current = await api<Experiment>(`/runs/${id}`);
      setRun(current);
      const requests: Promise<any>[] = [
        api<RunContext>(`/runs/${id}/context`).then(setContext).catch(() => setContext(null)),
        api<Dataset>(`/datasets/${current.dataset_id}`).then(setDataset).catch(() => setDataset(null)),
      ];
      if (current.status === 'completed') {
        requests.push(
          api<{ history: GenerationPoint[] }>(`/runs/${id}/generation-history`).then(value => setHistory(value.history || [])).catch(() => setHistory([])),
          api<ExperimentVisualization['test_results']>(`/runs/${id}/test-results?max_points=500`).then(setTestResults).catch(() => setTestResults(null)),
        );
      }
      await Promise.all(requests);
      setError('');
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [id]);

  if (!run) return <p className={error ? 'error' : ''}>{error || tr(language, 'Cargando…', 'Loading…')}</p>;
  const currentRun = run;
  const active = statusIsActive(currentRun.status);
  const progress = Math.min(100, Math.max(0, Number(currentRun.progress?.percent || 0)));

  async function action(path: string) {
    setBusy(true);
    setError('');
    try {
      setRun(await api<Experiment>(path, { method: 'POST' }));
    } catch (reason: any) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(tr(language, '¿Eliminar esta corrida y sus artefactos?', 'Delete this run and its artifacts?'))) return;
    setBusy(true);
    try {
      await api(`/runs/${currentRun.id}`, { method: 'DELETE' });
      navigate(context?.experiment_id ? `/experiments/${context.experiment_id}` : '/runs');
    } catch (reason: any) {
      setError(reason.message);
      setBusy(false);
    }
  }

  const validation = (currentRun.metrics as any)?.validation || (currentRun.parameters as any)?._genlab_split;
  const scatter = testResults?.actual.map((actual, index) => ({
    x: Number(actual),
    y: Number(testResults.prediction[index]),
    label: `#${testResults.sample[index]}`,
  })) || [];

  return (
    <>
      <Header title={currentRun.name} subtitle={currentRun.id}>
        <div className="header-actions">
          <Status value={currentRun.status} />
          {context?.experiment_id && <Link className="secondary button" to={`/experiments/${context.experiment_id}`}>{tr(language, 'Experimento', 'Experiment')}</Link>}
          {!active && currentRun.status !== 'queued' && <button className="secondary button" disabled={busy} onClick={() => action(`/runs/${currentRun.id}/rerun`)}>{tr(language, 'Volver a ejecutar', 'Rerun')}</button>}
          {active && <button className="danger button" disabled={busy} onClick={() => action(`/runs/${currentRun.id}/cancel`)}>{tr(language, 'Cancelar', 'Cancel')}</button>}
          {!active && currentRun.status !== 'queued' && <button className="danger button" disabled={busy} onClick={remove}>{tr(language, 'Eliminar', 'Delete')}</button>}
        </div>
      </Header>
      {error && <p className="error">{error}</p>}
      <div className="metrics">
        <Metric label="GPU" value={currentRun.gpu_id ?? '—'} />
        <Metric label={tr(language, 'Progreso', 'Progress')} value={`${progress}%`} />
        <Metric label={tr(language, 'Complejidad', 'Complexity')} value={currentRun.complexity || '—'} />
        <Metric label={tr(language, 'Tarea', 'Task')} value={currentRun.task_type} />
      </div>
      <Panel title={tr(language, 'Progreso de la corrida', 'Run progress')}>
        <div className="progress-track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-description"><b>{progress}%</b><span>{String(currentRun.progress?.message || tr(language, 'Sin iniciar', 'Not started'))}</span></div>
      </Panel>
      <Panel title={tr(language, 'Configuración de la corrida', 'Run configuration')}>
        <div className="configuration-summary lab-summary">
          <div><small>Dataset</small><b>{dataset?.name || currentRun.dataset_id}</b></div>
          <div><small>{tr(language, 'Objetivo', 'Target')}</small><b>{currentRun.target_column}</b></div>
          <div><small>{tr(language, 'Creada', 'Created')}</small><b>{new Date(currentRun.created_at).toLocaleString(locale)}</b></div>
          <div><small>Seed</small><b>{context?.seed ?? validation?.random_state ?? '—'}</b></div>
          {validation && <div><small>Train / Test</small><b>{formatNumber(validation.actual_train_size ?? validation.train_size, 3)} / {formatNumber(validation.actual_test_size ?? validation.test_size, 3)}</b></div>}
        </div>
        <details><summary>{tr(language, 'Parámetros completos', 'Full parameters')}</summary><pre>{JSON.stringify(currentRun.parameters, null, 2)}</pre></details>
      </Panel>
      {currentRun.metrics && <Panel title={tr(language, 'Métricas Train/Test', 'Train/Test metrics')}><pre>{JSON.stringify(currentRun.metrics, null, 2)}</pre></Panel>}
      <Panel title={tr(language, 'Modelo simbólico', 'Symbolic model')}><code className="model">{currentRun.symbolic_model || tr(language, 'Pendiente', 'Pending')}</code></Panel>
      {currentRun.error && <Panel title={tr(language, 'Error', 'Error')}><pre className="error">{currentRun.error}</pre></Panel>}
      {currentRun.status === 'completed' && (
        <Panel title={tr(language, 'Artefactos', 'Artifacts')}>
          <div className="actions">
            {[
              ['model.joblib', false],
              ['predictions.csv', false],
              ['metrics.json', false],
              ['model.txt', false],
              ['experiment.json', false],
            ].map(([filename]) => (
              <button className="secondary button compact" key={String(filename)} onClick={() => download(`/runs/${currentRun.id}/artifacts/${filename}`, String(filename))}>{String(filename)}</button>
            ))}
            <button className="secondary button compact" onClick={() => downloadJson(`/runs/${currentRun.id}/generation-history`, 'generation_history.json')}>generation_history.json</button>
            <button className="secondary button compact" onClick={() => downloadJson(`/runs/${currentRun.id}/test-results`, 'test_results.json')}>test_results.json</button>
          </div>
        </Panel>
      )}
      {currentRun.task_type === 'regression' && history.length > 0 && (
        <Panel title={tr(language, 'Evolución por generación', 'Generation evolution')}>
          <LineChart series={[{ label: 'Train Fit', className: 'fit-series', points: history.map(point => ({ x: Number(point.generation), y: Number(point.fit) })) }]} xLabel={tr(language, 'Generación', 'Generation')} yLabel="Train Fit" />
        </Panel>
      )}
      {currentRun.task_type === 'regression' && testResults && (
        <>
          <Panel title={tr(language, 'Resultados de prueba', 'Test results')}>
            <LineChart
              series={[
                { label: tr(language, 'Real', 'Actual'), className: 'actual-series', points: testResults.sample.map((sample, index) => ({ x: Number(sample), y: Number(testResults.actual[index]) })) },
                { label: tr(language, 'Predicción', 'Prediction'), className: 'prediction-series', points: testResults.sample.map((sample, index) => ({ x: Number(sample), y: Number(testResults.prediction[index]) })) },
              ]}
              xLabel={tr(language, 'Observación', 'Observation')}
              yLabel={tr(language, 'Valor', 'Value')}
            />
          </Panel>
          <Panel title={tr(language, 'Nube de puntos: observado vs. predicho', 'Scatter plot: observed vs. predicted')}>
            <ScatterPlot points={scatter} xLabel={tr(language, 'Valor observado', 'Observed value')} yLabel={tr(language, 'Predicción', 'Prediction')} emptyMessage={tr(language, 'Sin puntos disponibles.', 'No points available.')} />
          </Panel>
        </>
      )}
    </>
  );
}

const DEFAULT_M5GP_FUNCTIONS = ['+', '-', '*', '/', 'sin', 'cos', 'tan', 'tanh', 'exp', 'log', 'Abs', 'sqrt'];
const ALL_M5GP_FUNCTIONS = [...DEFAULT_M5GP_FUNCTIONS, 'Add', 'Mul', 'avg', 'std', 'if==', 'if>', 'if<'];

const REGRESSION_EVALUATION_METHODS = [
  [0, 'M5GP RMSE'],
  [1, 'M5GP R²'],
  [2, 'cuML Linear Regression'],
  [3, 'cuML Lasso Regression'],
  [4, 'cuML Ridge Regression'],
  [5, 'cuML Kernel Ridge Regression'],
  [6, 'cuML ElasticNet Regression'],
  [7, 'MiniBatch Linear Regression'],
  [8, 'MiniBatch Lasso Regression'],
  [9, 'MiniBatch Ridge Regression'],
  [10, 'MiniBatch ElasticNet Regression'],
] as const;

const CLASSIFICATION_EVALUATION_METHODS = [
  [0, 'Logistic Regression'],
  [1, 'Support Vector Classifier'],
  [2, 'Random Forest Classifier'],
  [3, 'K Neighbors Classifier'],
] as const;

type ParameterBuilderState = {
  evaluationMethod: number;
  scorer: number;
  generations: number;
  Individuals: number;
  GenesIndividuals: number;
  maxRandomConstant: number;
  mutationProb: number;
  mutationDeleteRateProb: number;
  sizeTournament: number;
  genOperatorProb: number;
  genVariableProb: number;
  genConstantProb: number;
  genNoopProb: number;
  useOpIF: number;
  functions_set: string[];
  log: number;
  verbose: number;
  averageMode: string;
};

function numberParameter(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function defaultParameterBuilder(taskType: 'both' | 'regression' | 'classification'): ParameterBuilderState {
  return {
    evaluationMethod: taskType === 'classification' ? 0 : 4,
    scorer: 0,
    generations: 40,
    Individuals: 512,
    GenesIndividuals: 64,
    maxRandomConstant: 1,
    mutationProb: 0.10,
    mutationDeleteRateProb: 0.05,
    sizeTournament: 0.15,
    genOperatorProb: 0.45,
    genVariableProb: 0.40,
    genConstantProb: 0.10,
    genNoopProb: 0.001,
    useOpIF: 0,
    functions_set: [...DEFAULT_M5GP_FUNCTIONS],
    log: 1,
    verbose: 1,
    averageMode: 'macro',
  };
}

function builderFromParameters(
  parameters: Record<string, any>,
  taskType: 'both' | 'regression' | 'classification',
): ParameterBuilderState {
  const defaults = defaultParameterBuilder(taskType);
  return {
    evaluationMethod: numberParameter(parameters.evaluationMethod, defaults.evaluationMethod),
    scorer: numberParameter(parameters.scorer, defaults.scorer),
    generations: numberParameter(parameters.generations, defaults.generations),
    Individuals: numberParameter(parameters.Individuals, defaults.Individuals),
    GenesIndividuals: numberParameter(parameters.GenesIndividuals, defaults.GenesIndividuals),
    maxRandomConstant: numberParameter(parameters.maxRandomConstant, defaults.maxRandomConstant),
    mutationProb: numberParameter(parameters.mutationProb, defaults.mutationProb),
    mutationDeleteRateProb: numberParameter(parameters.mutationDeleteRateProb, defaults.mutationDeleteRateProb),
    sizeTournament: numberParameter(parameters.sizeTournament, defaults.sizeTournament),
    genOperatorProb: numberParameter(parameters.genOperatorProb, defaults.genOperatorProb),
    genVariableProb: numberParameter(parameters.genVariableProb, defaults.genVariableProb),
    genConstantProb: numberParameter(parameters.genConstantProb, defaults.genConstantProb),
    genNoopProb: numberParameter(parameters.genNoopProb, defaults.genNoopProb),
    useOpIF: numberParameter(parameters.useOpIF, defaults.useOpIF),
    functions_set: Array.isArray(parameters.functions_set) && parameters.functions_set.length
      ? parameters.functions_set.map(String)
      : [...defaults.functions_set],
    log: numberParameter(parameters.log, defaults.log),
    verbose: numberParameter(parameters.verbose, defaults.verbose),
    averageMode: String(parameters.averageMode || defaults.averageMode),
  };
}

function parametersFromBuilder(
  builder: ParameterBuilderState,
  taskType: 'both' | 'regression' | 'classification',
): Record<string, unknown> {
  const parameters: Record<string, unknown> = {
    generations: Math.max(1, Math.round(builder.generations)),
    Individuals: Math.max(1, Math.round(builder.Individuals)),
    GenesIndividuals: Math.max(1, Math.round(builder.GenesIndividuals)),
    mutationProb: builder.mutationProb,
    mutationDeleteRateProb: builder.mutationDeleteRateProb,
    sizeTournament: builder.sizeTournament,
    maxRandomConstant: builder.maxRandomConstant,
    genOperatorProb: builder.genOperatorProb,
    genVariableProb: builder.genVariableProb,
    genConstantProb: builder.genConstantProb,
    genNoopProb: builder.genNoopProb,
    useOpIF: builder.useOpIF,
    functions_set: builder.functions_set,
    log: builder.log,
    verbose: builder.verbose,
  };
  if (taskType !== 'both') {
    parameters.evaluationMethod = builder.evaluationMethod;
    parameters.scorer = builder.scorer;
  }
  if (taskType === 'classification') parameters.averageMode = builder.averageMode;
  return parameters;
}

export function ParameterPresets() {
  const { language } = useI18n();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [presets, setPresets] = useState<ParameterPreset[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [taskType, setTaskType] = useState<'both' | 'regression' | 'classification'>('regression');
  const [isDefault, setIsDefault] = useState(false);
  const [json, setJson] = useState('{}');
  const [builderOpen, setBuilderOpen] = useState(false);
  const [builder, setBuilder] = useState<ParameterBuilderState>(defaultParameterBuilder('regression'));
  const [error, setError] = useState('');

  const load = () => api<ParameterPreset[]>('/parameter-presets').then(setPresets).catch(reason => setError(reason.message));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const requested = searchParams.get('preset');
    if (requested && presets.length > 0) {
      const preset = presets.find(item => item.id === requested);
      if (preset) clone(preset);
    }
  }, [presets.length]);

  useEffect(() => {
    if (!builderOpen) return;
    setJson(JSON.stringify(parametersFromBuilder(builder, taskType), null, 2));
  }, [builder, taskType, builderOpen]);

  function clear() {
    setEditingId(null);
    setName('');
    setDescription('');
    setTaskType('regression');
    setIsDefault(false);
    setJson('{}');
    setBuilder(defaultParameterBuilder('regression'));
    setBuilderOpen(false);
    setError('');
  }

  function clone(preset: ParameterPreset) {
    setEditingId(preset.system ? null : preset.id);
    setName(preset.system ? `${preset.name} personalizada` : preset.name);
    setDescription(preset.description);
    setTaskType(preset.task_type);
    setIsDefault(preset.system ? false : preset.is_default);
    setJson(JSON.stringify(preset.parameters, null, 2));
    setBuilder(builderFromParameters(preset.parameters, preset.task_type));
    setBuilderOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function openBuilder() {
    let parameters: Record<string, any> = {};
    try {
      parameters = JSON.parse(json || '{}');
    } catch {
      // El constructor puede recuperar una configuración aunque el JSON manual esté incompleto.
    }
    setBuilder(builderFromParameters(parameters, taskType));
    setBuilderOpen(true);
  }

  function setBuilderNumber(key: keyof ParameterBuilderState, value: string) {
    const numeric = Number(value);
    setBuilder(current => ({ ...current, [key]: Number.isFinite(numeric) ? numeric : 0 }));
  }

  function toggleFunction(functionName: string, checked: boolean) {
    setBuilder(current => {
      const functions = new Set(current.functions_set);
      if (checked) functions.add(functionName); else functions.delete(functionName);
      return { ...current, functions_set: ALL_M5GP_FUNCTIONS.filter(item => functions.has(item)) };
    });
  }

  async function save() {
    setError('');
    if (!name.trim()) {
      setError(tr(language, 'Capture un nombre para la configuración.', 'Enter a name for the configuration.'));
      return;
    }
    let parameters: Record<string, unknown>;
    try {
      parameters = JSON.parse(json);
    } catch {
      setError(tr(language, 'El JSON de parámetros no es válido.', 'Parameter JSON is invalid.'));
      return;
    }
    try {
      const path = editingId ? `/parameter-presets/${editingId}` : '/parameter-presets';
      await api(path, { method: editingId ? 'PUT' : 'POST', body: JSON.stringify({ name, description, task_type: taskType, parameters, is_default: isDefault }) });
      clear();
      await load();
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  async function remove(preset: ParameterPreset) {
    if (preset.system) return;
    if (!window.confirm(tr(language, `¿Eliminar “${preset.name}”?`, `Delete “${preset.name}”?`))) return;
    try {
      await api(`/parameter-presets/${preset.id}`, { method: 'DELETE' });
      await load();
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  const evaluationMethods: ReadonlyArray<readonly [number, string]> = taskType === 'classification'
    ? CLASSIFICATION_EVALUATION_METHODS
    : REGRESSION_EVALUATION_METHODS;

  return (
    <>
      <Header title={tr(language, 'Parámetros avanzados', 'Advanced parameters')} subtitle={tr(language, 'Revise los perfiles de GenLab y cree configuraciones reproducibles para M5GP.', 'Review GenLab profiles and create reproducible M5GP configurations.')}>
        <Link className="secondary button" to="/experiments/new">{tr(language, 'Volver a nuevo experimento', 'Back to new experiment')}</Link>
      </Header>
      <Panel title={editingId ? tr(language, 'Editar predefinido', 'Edit preset') : tr(language, 'Crear predefinido', 'Create preset')}>
        <div className="grid-form">
          <label>{tr(language, 'Nombre', 'Name')}<input value={name} onChange={event => setName(event.target.value)} /></label>
          <label>{tr(language, 'Aplicación', 'Applies to')}
            <select value={taskType} onChange={event => {
              const next = event.target.value as 'both' | 'regression' | 'classification';
              setTaskType(next);
              if (next === 'classification' && builder.evaluationMethod > 3) {
                setBuilder(current => ({ ...current, evaluationMethod: 0 }));
              }
            }}>
              <option value="both">{tr(language, 'Regresión y clasificación', 'Regression and classification')}</option>
              <option value="regression">{tr(language, 'Regresión', 'Regression')}</option>
              <option value="classification">{tr(language, 'Clasificación', 'Classification')}</option>
            </select>
          </label>
          <label className="form-wide">{tr(language, 'Descripción', 'Description')}<input value={description} onChange={event => setDescription(event.target.value)} /></label>

          <div className="form-wide parameter-builder-toggle">
            <button className="secondary button" type="button" onClick={() => builderOpen ? setBuilderOpen(false) : openBuilder()}>
              {builderOpen ? tr(language, 'Ocultar formulario de configuración', 'Hide configuration form') : tr(language, 'Construir configuración con formulario', 'Build configuration with form')}
            </button>
            <small>{tr(language, 'Los cambios del formulario actualizan automáticamente el JSON inferior.', 'Form changes automatically update the JSON below.')}</small>
          </div>

          {builderOpen && (
            <div className="form-wide parameter-builder">
              <h4>{tr(language, 'Constructor de parámetros M5GP', 'M5GP parameter builder')}</h4>
              {taskType === 'both' && <p className="builder-note">{tr(language, 'Para una configuración reutilizable en ambos tipos de tarea no se incluye evaluationMethod ni scorer en el JSON; GenLab aplicará los valores apropiados para cada tarea.', 'For a preset reusable across both task types, evaluationMethod and scorer are omitted from JSON; GenLab applies task-specific defaults.')}</p>}
              <div className="builder-grid">
                {taskType !== 'both' && (
                  <label>{tr(language, 'Método de evaluación', 'Evaluation method')}
                    <select value={builder.evaluationMethod} onChange={event => setBuilder(current => ({ ...current, evaluationMethod: Number(event.target.value) }))}>
                      {evaluationMethods.map(([value, label]) => <option key={value} value={value}>{value} · {label}</option>)}
                    </select>
                  </label>
                )}
                {taskType !== 'both' && (
                  <label>Scorer
                    <select value={builder.scorer} onChange={event => setBuilder(current => ({ ...current, scorer: Number(event.target.value) }))}>
                      {(taskType === 'classification' ? [0, 1, 2, 3] : [0, 1, 2]).map(value => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </label>
                )}
                {taskType === 'classification' && (
                  <label>Average mode
                    <select value={builder.averageMode} onChange={event => setBuilder(current => ({ ...current, averageMode: event.target.value }))}>
                      {['micro', 'macro', 'weighted', 'samples'].map(value => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </label>
                )}
                <label>{tr(language, 'Generaciones', 'Generations')}<input type="number" min="1" value={builder.generations} onChange={event => setBuilderNumber('generations', event.target.value)} /></label>
                <label>Individuals<input type="number" min="1" value={builder.Individuals} onChange={event => setBuilderNumber('Individuals', event.target.value)} /></label>
                <label>GenesIndividuals<input type="number" min="1" value={builder.GenesIndividuals} onChange={event => setBuilderNumber('GenesIndividuals', event.target.value)} /></label>
                <label>maxRandomConstant<input type="number" min="0.000001" step="0.1" value={builder.maxRandomConstant} onChange={event => setBuilderNumber('maxRandomConstant', event.target.value)} /></label>
                <label>mutationProb<input type="number" min="0" max="1" step="0.01" value={builder.mutationProb} onChange={event => setBuilderNumber('mutationProb', event.target.value)} /></label>
                <label>mutationDeleteRateProb<input type="number" min="0" max="1" step="0.01" value={builder.mutationDeleteRateProb} onChange={event => setBuilderNumber('mutationDeleteRateProb', event.target.value)} /></label>
                <label>sizeTournament<input type="number" min="0" max="1" step="0.01" value={builder.sizeTournament} onChange={event => setBuilderNumber('sizeTournament', event.target.value)} /></label>
                <label>genOperatorProb<input type="number" min="0" max="1" step="0.001" value={builder.genOperatorProb} onChange={event => setBuilderNumber('genOperatorProb', event.target.value)} /></label>
                <label>genVariableProb<input type="number" min="0" max="1" step="0.001" value={builder.genVariableProb} onChange={event => setBuilderNumber('genVariableProb', event.target.value)} /></label>
                <label>genConstantProb<input type="number" min="0" max="1" step="0.001" value={builder.genConstantProb} onChange={event => setBuilderNumber('genConstantProb', event.target.value)} /></label>
                <label>genNoopProb<input type="number" min="0" max="1" step="0.001" value={builder.genNoopProb} onChange={event => setBuilderNumber('genNoopProb', event.target.value)} /></label>
              </div>
              <div className="builder-switches">
                <label className="checkbox-label"><input type="checkbox" checked={builder.log === 1} onChange={event => setBuilder(current => ({ ...current, log: event.target.checked ? 1 : 0 }))} />log</label>
                <label className="checkbox-label"><input type="checkbox" checked={builder.verbose === 1} onChange={event => setBuilder(current => ({ ...current, verbose: event.target.checked ? 1 : 0 }))} />verbose</label>
                <label className="checkbox-label"><input type="checkbox" checked={builder.useOpIF === 1} onChange={event => setBuilder(current => ({ ...current, useOpIF: event.target.checked ? 1 : 0 }))} />useOpIF</label>
              </div>
              <fieldset className="function-selector">
                <legend>Functions set</legend>
                <div className="function-grid">
                  {ALL_M5GP_FUNCTIONS.map(functionName => (
                    <label className="checkbox-label" key={functionName}>
                      <input type="checkbox" checked={builder.functions_set.includes(functionName)} onChange={event => toggleFunction(functionName, event.target.checked)} />
                      <code>{functionName}</code>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          )}

          <label className="form-wide">JSON · M5GP<textarea className="parameter-editor" rows={18} value={json} onChange={event => { setJson(event.target.value); if (builderOpen) setBuilderOpen(false); }} spellCheck={false} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={isDefault} onChange={event => setIsDefault(event.target.checked)} />{tr(language, 'Usar como predefinido por defecto', 'Use as default preset')}</label>
          <div className="form-wide actions"><button className="primary button" type="button" onClick={save}>{tr(language, 'Guardar', 'Save')}</button><button className="secondary button" type="button" onClick={clear}>{tr(language, 'Limpiar', 'Clear')}</button></div>
        </div>
        {error && <p className="error">{error}</p>}
      </Panel>
      <Panel title={tr(language, 'Perfiles disponibles', 'Available profiles')}>
        <div className="preset-grid">
          {presets.map(preset => (
            <article className="preset-card" key={preset.id}>
              <div className="preset-title"><h4>{preset.name}</h4>{preset.is_default && <span>default</span>}</div>
              <p>{preset.description}</p>
              <pre>{JSON.stringify(preset.parameters, null, 2)}</pre>
              <div className="actions">
                <button className="secondary button compact" onClick={() => clone(preset)}>{preset.system ? tr(language, 'Copiar y editar', 'Copy and edit') : tr(language, 'Editar', 'Edit')}</button>
                <button className="primary button compact" onClick={() => navigate(`/experiments/new?preset=${encodeURIComponent(preset.id)}`)}>{tr(language, 'Usar', 'Use')}</button>
                {!preset.system && <button className="danger button compact" onClick={() => remove(preset)}>{tr(language, 'Eliminar', 'Delete')}</button>}
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}

export function Batches() {
  const { language, locale } = useI18n();
  const [groups, setGroups] = useState<ExperimentGroup[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');

  const load = () => Promise.all([
    api<ExperimentGroup[]>('/experiment-groups').then(setGroups),
    api<Batch[]>('/batches').then(setBatches),
  ]).catch(reason => setError(reason.message));
  useEffect(() => { load(); const timer = window.setInterval(load, 5000); return () => window.clearInterval(timer); }, []);

  async function createAndRun() {
    if (!name.trim() || selected.size === 0) {
      setError(tr(language, 'Capture un nombre y seleccione al menos un experimento.', 'Enter a name and select at least one experiment.'));
      return;
    }
    try {
      const batch = await api<Batch>('/batches', { method: 'POST', body: JSON.stringify({ name, experiment_ids: Array.from(selected) }) });
      await api(`/batches/${batch.id}/run`, { method: 'POST' });
      setName(''); setSelected(new Set()); await load();
    } catch (reason: any) { setError(reason.message); }
  }

  return (
    <>
      <Header title={tr(language, 'Lotes de experimentos', 'Experiment batches')} subtitle={tr(language, 'Agrupe experimentos guardados y envíe sus corridas a la cola GPU.', 'Group saved experiments and submit their runs to the GPU queue.')} />
      <Panel title={tr(language, 'Nuevo lote', 'New batch')}>
        <label>{tr(language, 'Nombre del lote', 'Batch name')}<input value={name} onChange={event => setName(event.target.value)} /></label>
        <div className="batch-selector">
          {groups.map(group => {
            const alreadyMaterialized = group.summary.total_runs > 0;
            return (
              <label className={`batch-choice ${alreadyMaterialized ? 'disabled' : ''}`} key={group.id}>
                <input
                  type="checkbox"
                  disabled={alreadyMaterialized}
                  checked={selected.has(group.id)}
                  onChange={event => setSelected(current => {
                    const next = new Set(current);
                    if (event.target.checked) next.add(group.id); else next.delete(group.id);
                    return next;
                  })}
                />
                <span><b>{group.name}</b><small>{group.datasets.length} datasets · {group.runs_per_dataset} {tr(language, 'corridas/dataset', 'runs/dataset')}{alreadyMaterialized ? ` · ${tr(language, 'ya ejecutado/creado', 'already materialized')}` : ''}</small></span>
              </label>
            );
          })}
        </div>
        {error && <p className="error">{error}</p>}
        <button className="primary button" onClick={createAndRun}>{tr(language, 'Crear y ejecutar lote', 'Create and run batch')}</button>
      </Panel>
      <Panel title={tr(language, 'Historial de lotes', 'Batch history')}>
        <div className="table-scroll">
          <table>
            <thead><tr><th>{tr(language, 'Nombre', 'Name')}</th><th>{tr(language, 'Experimentos', 'Experiments')}</th><th>{tr(language, 'Estado', 'Status')}</th><th>{tr(language, 'Fecha', 'Date')}</th></tr></thead>
            <tbody>{batches.map(batch => <tr key={batch.id}><td>{batch.name}</td><td>{batch.experiments.length}</td><td><Status value={batch.status} /></td><td>{new Date(batch.created_at).toLocaleString(locale)}</td></tr>)}</tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
