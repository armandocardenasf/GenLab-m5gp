import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Code2, Download, ExternalLink, Eye, EyeOff, Scale } from 'lucide-react';

import { api, download, downloadJson } from './api';
import { useAuth } from './auth';
import { Metric, Status } from './components';
import { LineChart } from './charts';
import {
  parameterLabel,
  taskLabel,
  translateProgressMessage,
  useI18n,
} from './i18n';
import type { AboutInfo, Dataset, DatasetPreview, Experiment, ExperimentVisualization, GenerationPoint, GPU, LocalizedText } from './types';

const ACTIVE_STATUSES = ['reserved', 'running', 'cancelling'];
const SUPPORTED_DATASET_EXTENSIONS = ['.csv', '.tsv'];

function isActive(experiment: Experiment): boolean {
  return ACTIVE_STATUSES.includes(experiment.status);
}

function isSupportedDataset(file: File): boolean {
  const filename = file.name.toLowerCase();
  return SUPPORTED_DATASET_EXTENSIONS.some(extension =>
    filename.endsWith(extension),
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function Login() {
  const { login, register } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    try {
      if (mode === 'login') await login(email, password);
      else await register(name, email, password);
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  return (
    <div className="auth">
      <section className="hero">
        <div className="hero-mark">M5GP</div>
        <h1>{t('login.heroTitle')}</h1>
        <p>{t('login.heroDescription')}</p>
      </section>
      <form className="auth-card" onSubmit={submit}>
        <h2>{mode === 'login' ? t('login.signIn') : t('login.createAccount')}</h2>
        {mode === 'register' && (
          <label>
            {t('common.name')}
            <input
              value={name}
              onChange={event => setName(event.target.value)}
              required
            />
          </label>
        )}
        <label>
          {t('common.email')}
          <input
            type="email"
            value={email}
            onChange={event => setEmail(event.target.value)}
            required
          />
        </label>
        <label>
          {t('common.password')}
          <span className="password-field">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={event => setPassword(event.target.value)}
              minLength={10}
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(value => !value)}
              title={showPassword ? t('common.hidePassword') : t('common.showPassword')}
              aria-label={showPassword ? t('common.hidePassword') : t('common.showPassword')}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeOff /> : <Eye />}
            </button>
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary">
          {mode === 'login' ? t('login.enter') : t('login.register')}
        </button>
        <button
          type="button"
          className="link"
          onClick={() =>
            setMode(mode === 'login' ? 'register' : 'login')
          }
        >
          {mode === 'login' ? t('login.createAccountLink') : t('login.haveAccount')}
        </button>
      </form>
    </div>
  );
}

function useData() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [gpus, setGpus] = useState<GPU[]>([]);

  const load = () =>
    Promise.all([
      api<Dataset[]>('/datasets').then(setDatasets),
      api<Experiment[]>('/experiments').then(setExperiments),
      api<GPU[]>('/gpus').then(setGpus),
    ]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, []);

  return { datasets, experiments, gpus, load };
}

export function Overview() {
  const { datasets, experiments, gpus } = useData();
  const { t } = useI18n();
  return (
    <>
      <Header title={t('overview.title')} subtitle={t('overview.subtitle')} />
      <div className="metrics">
        <Metric label={t('overview.datasets')} value={datasets.length} />
        <Metric label={t('overview.experiments')} value={experiments.length} />
        <Metric
          label={t('overview.availableGpus')}
          value={`${gpus.filter(gpu => !gpu.busy).length}/${gpus.length}`}
        />
        <Metric
          label={t('overview.activeRuns')}
          value={experiments.filter(isActive).length}
        />
      </div>
      <Panel title={t('overview.recentRuns')}>
        <ExperimentTable rows={experiments.slice(0, 8)} />
      </Panel>
    </>
  );
}

export function Datasets() {
  const { datasets, load } = useData();
  const { t, locale } = useI18n();
  const [name, setName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  function selectFile(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    setError('');
    if (selected && !isSupportedDataset(selected)) {
      setFile(null);
      event.target.value = '';
      setError(t('datasets.invalidExtension'));
      return;
    }
    setFile(selected);
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    if (!file) return;
    if (!isSupportedDataset(file)) {
      setError(t('datasets.invalidExtension'));
      return;
    }
    const form = new FormData();
    form.append('name', name);
    form.append('file', file);
    try {
      const created = await api<Dataset>('/datasets', {
        method: 'POST',
        body: form,
      });
      setName('');
      setFile(null);
      await load();
      await previewDataset(created.id);
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  async function previewDataset(datasetId: string) {
    setSelectedDatasetId(datasetId);
    setPreview(null);
    setPreviewError('');
    setPreviewLoading(true);
    try {
      setPreview(await api<DatasetPreview>(`/datasets/${datasetId}/preview`));
    } catch (reason: any) {
      setPreviewError(reason.message);
    } finally {
      setPreviewLoading(false);
    }
  }

  const selectedDataset = datasets.find(
    dataset => dataset.id === selectedDatasetId,
  );

  return (
    <>
      <Header
        title={t('datasets.title')}
        subtitle={t('datasets.subtitle')}
      />
      <div className="split">
        <Panel title={t('datasets.new')}>
          <form onSubmit={upload}>
            <label>
              {t('common.name')}
              <input
                value={name}
                onChange={event => setName(event.target.value)}
                required
              />
            </label>
            <label>
              {t('datasets.file')}
              <input
                type="file"
                accept=".csv,.tsv,text/csv,text/tab-separated-values"
                onChange={selectFile}
                required
              />
            </label>
            {file && <small>{t('datasets.selectedFile', { name: file.name })}</small>}
            {error && <p className="error">{error}</p>}
            <button className="primary">{t('datasets.upload')}</button>
          </form>
        </Panel>
        <Panel title={t('datasets.uploaded')}>
<p className="panel-description">{t('datasets.description')}</p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('common.name')}</th>
                  <th>{t('datasets.dimension')}</th>
                  <th>{t('common.date')}</th>
                  <th>{t('datasets.preview')}</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map(dataset => (
                  <tr
                    key={dataset.id}
                    className={
                      dataset.id === selectedDatasetId
                        ? 'selected-row selectable-row'
                        : 'selectable-row'
                    }
                    role="button"
                    tabIndex={0}
                    aria-selected={dataset.id === selectedDatasetId}
                    onClick={() => previewDataset(dataset.id)}
                    onKeyDown={event => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        previewDataset(dataset.id);
                      }
                    }}
                  >
                    <td>
                      {dataset.name}
                      <small>{dataset.original_name}</small>
                    </td>
                    <td>
                      {dataset.rows} × {dataset.columns}
                    </td>
                    <td>{new Date(dataset.created_at).toLocaleString(locale)}</td>
                    <td>
                      <button
                        type="button"
                        className="secondary compact"
                        onClick={event => {
                          event.stopPropagation();
                          previewDataset(dataset.id);
                        }}
                        disabled={
                          previewLoading && dataset.id === selectedDatasetId
                        }
                      >
                        {previewLoading && dataset.id === selectedDatasetId
                          ? t('common.loading')
                          : t('datasets.previewButton')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {previewError && <p className="error">{previewError}</p>}

          {selectedDataset && preview && (
            <section className="dataset-preview">
              <div className="dataset-preview-header">
                <div>
                  <h4>{t('datasets.previewTitle', { name: selectedDataset.name })}</h4>
<p>{t('datasets.previewDescription')}</p>
                </div>
                <span>{t('datasets.firstRows', { count: preview.rows.length })}</span>
              </div>

              <div className="column-catalog">
                {preview.columns.map(column => (
                  <span key={column}>
                    <b>{column}</b>
                    <small>{selectedDataset.dtypes[column] || t('datasets.typeUnavailable')}</small>
                  </span>
                ))}
              </div>

              <div className="dataset-preview-table">
                <table>
                  <thead>
                    <tr>
                      {preview.columns.map(column => (
                        <th key={column}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {preview.columns.map(column => (
                          <td key={column}>{formatValue(row[column])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </Panel>
      </div>
    </>
  );
}

export function Experiments() {
  const { experiments, load } = useData();
  const { t } = useI18n();
  const [error, setError] = useState('');

  async function removeExperiment(experiment: Experiment) {
    if (isActive(experiment)) return;
    if (
      !window.confirm(
        t('experiments.confirmDelete', { name: experiment.name }),
      )
    ) {
      return;
    }
    setError('');
    try {
      await api(`/experiments/${experiment.id}`, { method: 'DELETE' });
      await load();
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  return (
    <>
      <Header title={t('experiments.title')} subtitle={t('experiments.subtitle')}>
        <Link className="primary button" to="/experiments/new">
          {t('experiments.new')}
        </Link>
      </Header>
      {error && <p className="error">{error}</p>}
      <Panel title={t('experiments.history')}>
        <ExperimentTable
          rows={experiments}
          onDelete={removeExperiment}
        />
      </Panel>
    </>
  );
}

type ExperimentParameterValue = number | string | boolean;
type ExperimentParameters = Record<string, ExperimentParameterValue>;

const COMMON_PARAMETERS: ExperimentParameters = {
  generations: 40,
  Individuals: 512,
  GenesIndividuals: 64,
  mutationProb: 0.1,
  mutationDeleteRateProb: 0.05,
  sizeTournament: 0.15,
  maxRandomConstant: 1,
  genOperatorProb: 0.45,
  genVariableProb: 0.4,
  genConstantProb: 0.05,
  genNoopProb: 0.1,
  useOpIF: 0,
  log: 1,
  verbose: 1,
};

const REGRESSION_PARAMETERS: ExperimentParameters = {
  ...COMMON_PARAMETERS,
  evaluationMethod: 4,
  scorer: 0,
};


const REGRESSION_METHODS = Array.from({ length: 11 }, (_, value) => ({ value }));

function regressionMethodDescriptionKey(value: ExperimentParameterValue): string {
  return `regressionMethod.${Number(value)}.description`;
}


const CLASSIFICATION_PARAMETERS: ExperimentParameters = {
  ...COMMON_PARAMETERS,
  evaluationMethod: 0,
  scorer: 0,
  crossVal: true,
  k: 3,
  averageMode: 'macro',
  CrossAverage: false,
};

const COMMON_PARAMETER_KEYS = [
  'generations',
  'Individuals',
  'GenesIndividuals',
  'mutationProb',
  'mutationDeleteRateProb',
  'sizeTournament',
  'maxRandomConstant',
  'genOperatorProb',
  'genVariableProb',
  'genConstantProb',
  'genNoopProb',
  'useOpIF',
  'log',
  'verbose',
];

function numberStep(value: ExperimentParameterValue): number {
  return typeof value === 'number' && Math.abs(value) < 1 ? 0.01 : 1;
}

export function NewExperiment() {
  const { t } = useI18n();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState('');
  const [name, setName] = useState(() => t('newExperiment.defaultName'));
  const [target, setTarget] = useState('');
  const [task, setTask] = useState<'regression' | 'classification'>(
    'regression',
  );
  const [params, setParams] = useState<ExperimentParameters>({
    ...REGRESSION_PARAMETERS,
  });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api<Dataset[]>('/datasets').then(setDatasets);
  }, []);

  const selectedDataset = datasets.find(item => item.id === dataset);

  function changeTask(nextTask: 'regression' | 'classification') {
    setTask(nextTask);
    setParams(
      nextTask === 'regression'
        ? { ...REGRESSION_PARAMETERS }
        : { ...CLASSIFICATION_PARAMETERS },
    );
  }

  function setParameter(key: string, value: ExperimentParameterValue) {
    setParams(current => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const experiment = await api<Experiment>('/experiments', {
        method: 'POST',
        body: JSON.stringify({
          name,
          dataset_id: dataset,
          task_type: task,
          target_column: target,
          parameters: params,
        }),
      });
      await api(`/experiments/${experiment.id}/run`, { method: 'POST' });
      navigate(`/experiments/${experiment.id}`);
    } catch (reason: any) {
      setError(reason.message);
    }
  }

  return (
    <>
      <Header
        title={t('newExperiment.title')}
        subtitle={t('newExperiment.subtitle')}
      />
      <Panel title={t('newExperiment.configuration')}>
        <form className="grid-form" onSubmit={submit}>
          <label>
            {t('common.name')}
            <input
              value={name}
              onChange={event => setName(event.target.value)}
              required
            />
          </label>
          <label>
            {t('newExperiment.dataset')}
            <select
              value={dataset}
              onChange={event => {
                setDataset(event.target.value);
                setTarget('');
              }}
              required
            >
              <option value="">{t('common.select')}</option>
              {datasets.map(item => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('newExperiment.target')}
            <select
              value={target}
              onChange={event => setTarget(event.target.value)}
              required
            >
              <option value="">{t('common.select')}</option>
              {selectedDataset?.column_names.map(column => (
                <option key={column}>{column}</option>
              ))}
            </select>
          </label>
          <label>
            {t('newExperiment.type')}
            <select
              value={task}
              onChange={event =>
                changeTask(
                  event.target.value as 'regression' | 'classification',
                )
              }
            >
              <option value="regression">{t('newExperiment.regression')}</option>
              <option value="classification">{t('newExperiment.classification')}</option>
            </select>
          </label>

          {COMMON_PARAMETER_KEYS.map(key => (
            <label key={key}>
              <span>{parameterLabel(key, t)} <small>({key})</small></span>
              <input
                type="number"
                step={numberStep(params[key])}
                value={Number(params[key])}
                onChange={event =>
                  setParameter(key, Number(event.target.value))
                }
              />
            </label>
          ))}

          {task === 'regression' ? (
            <>
              <label>
                {t('newExperiment.regressionMethod')}
                <select
                  value={Number(params.evaluationMethod)}
                  onChange={event =>
                    setParameter('evaluationMethod', Number(event.target.value))
                  }
                >
                  {REGRESSION_METHODS.map(method => (
                    <option key={method.value} value={method.value}>
                      {method.value} — {t(`regressionMethod.${method.value}.label`)}
                    </option>
                  ))}
                </select>
                <small>
                  {t(regressionMethodDescriptionKey(params.evaluationMethod))}
                </small>
              </label>
              <label>
                {t('newExperiment.evaluationMetric')}
                <select
                  value={Number(params.scorer)}
                  onChange={event =>
                    setParameter('scorer', Number(event.target.value))
                  }
                >
                  <option value={0}>RMSE</option>
                  <option value={1}>RMSE</option>
                  <option value={2}>R²</option>
                </select>
              </label>
            </>
          ) : (
            <>
              <label>
                {t('newExperiment.classifier')}
                <select
                  value={Number(params.evaluationMethod)}
                  onChange={event =>
                    setParameter('evaluationMethod', Number(event.target.value))
                  }
                >
                  <option value={0}>Logistic Regression</option>
                  <option value={1}>Support Vector Classifier</option>
                  <option value={2}>Random Forest Classifier</option>
                  <option value={3}>K Neighbors Classifier</option>
                </select>
              </label>
              <label>
                {t('newExperiment.classifierMetric')}
                <select
                  value={Number(params.scorer)}
                  onChange={event =>
                    setParameter('scorer', Number(event.target.value))
                  }
                >
                  <option value={0}>{t('metric.accuracy')}</option>
                  <option value={1}>ROC AUC</option>
                  <option value={2}>F1 Score</option>
                  <option value={3}>{t('metric.averagePrecision')}</option>
                </select>
              </label>
              <label>
                {t('newExperiment.metricAverage')}
                <select
                  value={String(params.averageMode)}
                  onChange={event =>
                    setParameter('averageMode', event.target.value)
                  }
                >
                  <option value="macro">{t('metric.macro')}</option>
                  <option value="micro">{t('metric.micro')}</option>
                  <option value="weighted">{t('newExperiment.weighted')}</option>
                  <option value="samples">{t('newExperiment.samples')}</option>
                </select>
              </label>
              <label>
                {t('newExperiment.crossValidationSplits')}
                <input
                  type="number"
                  min={2}
                  step={1}
                  value={Number(params.k)}
                  onChange={event =>
                    setParameter('k', Number(event.target.value))
                  }
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={Boolean(params.crossVal)}
                  onChange={event =>
                    setParameter('crossVal', event.target.checked)
                  }
                />
                {t('newExperiment.useCrossValidation')}
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={Boolean(params.CrossAverage)}
                  onChange={event =>
                    setParameter('CrossAverage', event.target.checked)
                  }
                />
                {t('newExperiment.averageCrossValidation')}
              </label>
            </>
          )}
          {error && <p className="error form-wide">{error}</p>}
          <div className="form-wide">
            <button className="primary">{t('newExperiment.createAndRun')}</button>
          </div>
        </form>
      </Panel>
    </>
  );
}

export function ExperimentDetail() {
  const { t, locale } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [actionError, setActionError] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [downloadingArtifact, setDownloadingArtifact] = useState<string | null>(null);
  const [visualization, setVisualization] =
    useState<ExperimentVisualization | null>(null);

  async function load() {
    const current = await api<Experiment>(`/experiments/${id}`);
    setExperiment(current);
    try {
      setDataset(await api<Dataset>(`/datasets/${current.dataset_id}`));
    } catch {
      setDataset(null);
    }
    if (current.status === 'completed') {
      try {
        const [history, testResults] = await Promise.all([
          api<{
            task_type: string;
            fit_label: string;
            history: GenerationPoint[];
          }>(`/experiments/${current.id}/generation-history`),
          api<ExperimentVisualization['test_results']>(
            `/experiments/${current.id}/test-results?max_points=300`,
          ),
        ]);
        setVisualization({
          task_type: current.task_type,
          generation_history: history.history || [],
          fit_label: history.fit_label || t('chart.trainFit'),
          test_results: testResults,
        });
      } catch {
        setVisualization(null);
      }
    } else {
      setVisualization(null);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [id]);

  if (!experiment) return <p>{t('common.loading')}</p>;

  const currentExperiment = experiment;
  const active = isActive(currentExperiment);
  const progress = Math.min(
    100,
    Math.max(0, Number(currentExperiment.progress?.percent ?? 0)),
  );
  const generation = currentExperiment.progress?.generation;
  const totalGenerations = currentExperiment.progress?.total_generations;
  const liveHistory = Array.isArray(currentExperiment.progress?.history)
    ? (currentExperiment.progress.history as GenerationPoint[])
    : [];
  const generationHistory =
    visualization?.generation_history?.length
      ? visualization.generation_history
      : liveHistory;

  async function rerun() {
    setActionBusy(true);
    setActionError('');
    try {
      const updated = await api<Experiment>(
        `/experiments/${currentExperiment.id}/rerun`,
        { method: 'POST' },
      );
      setExperiment(updated);
    } catch (reason: any) {
      setActionError(reason.message);
    } finally {
      setActionBusy(false);
    }
  }

  async function downloadArtifact(artifact: {
    filename: string;
    endpoint?: string;
    json?: boolean;
  }) {
    setDownloadingArtifact(artifact.filename);
    setActionError('');
    try {
      const endpoint =
        artifact.endpoint ||
        `/experiments/${currentExperiment.id}/artifacts/${artifact.filename}`;
      if (artifact.json) {
        await downloadJson(endpoint, artifact.filename);
      } else {
        await download(endpoint, artifact.filename);
      }
    } catch (reason: any) {
      setActionError(
        t('experiment.downloadError', { filename: artifact.filename, message: reason.message }),
      );
    } finally {
      setDownloadingArtifact(null);
    }
  }

  async function remove() {
    if (
      !window.confirm(
        t('experiment.confirmDeleteAll', { name: currentExperiment.name }),
      )
    ) {
      return;
    }
    setActionBusy(true);
    setActionError('');
    try {
      await api(`/experiments/${currentExperiment.id}`, { method: 'DELETE' });
      navigate('/experiments');
    } catch (reason: any) {
      setActionError(reason.message);
      setActionBusy(false);
    }
  }

  return (
    <>
      <Header title={experiment.name} subtitle={experiment.id}>
        <div className="header-actions">
          <Status value={experiment.status} />
          <button
            type="button"
            className="secondary button"
            onClick={rerun}
            disabled={active || actionBusy}
          >
            {experiment.status === 'created'
              ? t('experiment.execute')
              : t('experiment.rerun')}
          </button>
          <button
            type="button"
            className="danger button"
            onClick={remove}
            disabled={active || actionBusy}
          >
            {t('common.delete')}
          </button>
        </div>
      </Header>

      {actionError && <p className="error">{actionError}</p>}

      <div className="metrics">
        <Metric label={t('experiment.gpu')} value={experiment.gpu_id ?? '—'} />
        <Metric label={t('experiment.progress')} value={`${progress}%`} />
        <Metric label={t('experiment.complexity')} value={experiment.complexity ?? '—'} />
        <Metric label={t('experiment.task')} value={taskLabel(experiment.task_type, t)} />
      </div>

      <Panel title={t('experiment.progressTitle')}>
        <div
          className="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-description">
          <b>{progress}%</b>
          <span>
            {translateProgressMessage(experiment.progress?.message, t)}
          </span>
          {generation !== undefined && totalGenerations !== undefined && (
            <small>
              {t('experiment.generationOf', { current: generation, total: totalGenerations })}
            </small>
          )}
        </div>
      </Panel>

      <Panel title={t('experiment.initialParameters')}>
        <div className="configuration-summary">
          <div>
            <small>{t('newExperiment.dataset')}</small>
            <b>{dataset?.name || experiment.dataset_id}</b>
            {dataset && <span>{dataset.original_name}</span>}
          </div>
          <div>
            <small>{t('experiment.targetVariable')}</small>
            <b>{experiment.target_column}</b>
          </div>
          <div>
            <small>{t('experiment.taskType')}</small>
            <b>{taskLabel(experiment.task_type, t)}</b>
          </div>
          <div>
            <small>{t('experiment.createdAt')}</small>
            <b>{new Date(experiment.created_at).toLocaleString(locale)}</b>
          </div>
        </div>
        <table className="parameter-table">
          <thead>
            <tr>
              <th>{t('experiment.parameter')}</th>
              <th>{t('experiment.initialValue')}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(experiment.parameters).map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>
                  <code>{formatValue(value)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      {experiment.metrics && (
        <Panel
          title={
            experiment.task_type === 'regression'
              ? t('experiment.regressionMetrics')
              : t('experiment.classificationMetrics')
          }
        >
          <pre>{JSON.stringify(experiment.metrics, null, 2)}</pre>
        </Panel>
      )}

      <Panel title={t('experiment.symbolicModel')}>
        <code className="model">
          {experiment.symbolic_model ||
            t('experiment.modelPending')}
        </code>
      </Panel>

      {experiment.error && (
        <Panel title={t('common.error')}>
          <pre className="error">{experiment.error}</pre>
        </Panel>
      )}

      <Panel title={t('experiment.artifacts')}>
        {experiment.status === 'completed' ? (
          <div className="actions">
            {[
              { filename: 'model.joblib', label: t('artifact.trainedModel') },
              { filename: 'predictions.csv', label: t('artifact.predictionsCsv') },
              { filename: 'metrics.json', label: t('artifact.metricsJson') },
              { filename: 'model.txt', label: t('artifact.symbolicModel') },
              {
                filename: 'generation_history.json',
                label: t('artifact.generationHistory'),
                endpoint: `/experiments/${currentExperiment.id}/generation-history`,
                json: true,
              },
              {
                filename: 'test_results.json',
                label: t('artifact.testResults'),
                endpoint: `/experiments/${currentExperiment.id}/test-results`,
                json: true,
              },
              ...(experiment.task_type === 'classification'
                ? [
                    {
                      filename: 'classification_report.json',
                      label: t('artifact.classificationReport'),
                    },
                    {
                      filename: 'confusion_matrix.json',
                      label: t('artifact.confusionMatrix'),
                    },
                  ]
                : []),
              { filename: 'experiment.json', label: t('artifact.completeResults') },
            ].map(artifact => (
              <button
                type="button"
                className="secondary button"
                onClick={() => downloadArtifact(artifact)}
                disabled={downloadingArtifact !== null}
                key={artifact.filename}
              >
                {downloadingArtifact === artifact.filename
                  ? t('common.downloading')
                  : artifact.label}
              </button>
            ))}
          </div>
        ) : (
          <p>{t('experiment.artifactsPending')}</p>
        )}
      </Panel>

      {currentExperiment.task_type === 'regression' &&
        generationHistory.length > 0 && (
          <Panel title={t('chart.generationTitle')}>
<p className="panel-description">{t('chart.generationDescription')}</p>
            <LineChart
              series={[
                {
                  label: t('chart.trainFit'),
                  className: 'fit-series',
                  points: generationHistory.map(point => ({
                    x: Number(point.generation),
                    y: Number(point.fit),
                  })),
                },
              ]}
              xLabel={t('chart.generation')}
              yLabel={t('chart.trainFit')}
            />
          </Panel>
        )}

      {currentExperiment.task_type === 'regression' &&
        visualization?.test_results && (
          <Panel title={t('chart.testTitle')}>
            <p className="panel-description">
              {t('chart.testDescription', {
                displayed: visualization.test_results.displayed_points,
                total: visualization.test_results.total_points,
              })}
            </p>
            <LineChart
              series={[
                {
                  label: t('chart.actual'),
                  className: 'actual-series',
                  points: visualization.test_results.sample.map(
                    (sample, index) => ({
                      x: Number(sample),
                      y: Number(visualization.test_results.actual[index]),
                    }),
                  ),
                },
                {
                  label: t('chart.prediction'),
                  className: 'prediction-series',
                  points: visualization.test_results.sample.map(
                    (sample, index) => ({
                      x: Number(sample),
                      y: Number(
                        visualization.test_results.prediction[index],
                      ),
                    }),
                  ),
                },
              ]}
              xLabel={t('chart.testObservation')}
              yLabel={t('common.value')}
            />
          </Panel>
        )}

    </>
  );
}

export function About() {
  const { t, language } = useI18n();
  const [information, setInformation] = useState<AboutInfo | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api<AboutInfo>('/about')
      .then(setInformation)
      .catch(reason => setError(reason.message));
  }, []);

  const localized = (value: LocalizedText): string => value[language];

  if (!information && !error) return <p>{t('common.loading')}</p>;

  return (
    <>
      <Header title={t('about.title')} subtitle={t('about.subtitle')} />
      {error && <p className="error">{error}</p>}
      {information && (
        <>
          <section className="about-hero panel">
            <div>
              <span className="about-kicker">{information.product_name}</span>
              <h2>{localized(information.full_name)}</h2>
              <p>{t('about.versionDescription')}</p>
            </div>
            <div className="about-version" aria-label={t('about.version')}>
              <small>{t('about.version')}</small>
              <strong>{information.version}</strong>
              <span>{t(`about.release.${information.release_channel}`) === `about.release.${information.release_channel}` ? information.release_channel : t(`about.release.${information.release_channel}`)}</span>
            </div>
          </section>

          <div className="about-grid">
            <Panel title={t('about.copyrightTitle')}>
              <p className="about-lead"><b>{information.copyright.holder}</b></p>
              <p>{localized(information.copyright.role)}</p>
              <p>{localized(information.copyright.notice)}</p>
            </Panel>

            <Panel title={t('about.acknowledgementsTitle')}>
              <p>{localized(information.acknowledgements)}</p>
              <ul className="about-list">
                {information.supporting_institutions.map(institution => (
                  <li key={institution}>{institution}</li>
                ))}
              </ul>
            </Panel>
          </div>

          <Panel title={t('about.referencesTitle')}>
            <p className="panel-description">{t('about.referencesDescription')}</p>
            <div className="reference-list">
              {information.references.map(reference => (
                <article className="reference-card" key={reference.name}>
                  <h4>{reference.name}</h4>
                  <p>{reference.citation}</p>
                  <div className="actions">
                    <a className="secondary button" href={reference.repository_url} target="_blank" rel="noreferrer">
                      <Code2 aria-hidden="true" /> {t('about.repository')}
                    </a>
                    {reference.doi_url && (
                      <a className="secondary button" href={reference.doi_url} target="_blank" rel="noreferrer">
                        <ExternalLink aria-hidden="true" /> DOI
                      </a>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </Panel>

          <Panel title={t('about.sourceCodeTitle')}>
            <p>{t('about.sourceCodeDescription')}</p>
            <div className="actions">
              <a className="primary button" href={information.source_code.repository_url} target="_blank" rel="noreferrer">
                <Code2 aria-hidden="true" /> {t('about.accessSource')}
              </a>
              <a className="secondary button" href={information.source_code.download_url}>
                <Download aria-hidden="true" /> {t('about.downloadSource')}
              </a>
            </div>
          </Panel>

          <Panel title={t('about.legalTitle')}>
            <div className="legal-heading">
              <Scale aria-hidden="true" />
              <div>
                <b>{localized(information.legal.license_name)}</b>
                <span>{information.legal.public_source ? t('about.publicSource') : t('about.privateSource')}</span>
              </div>
            </div>
            <p>{localized(information.legal.terms)}</p>
            <p className="legal-disclaimer">{localized(information.legal.disclaimer)}</p>
            <a className="secondary button" href={information.legal.license_url} target="_blank" rel="noreferrer">
              <ExternalLink aria-hidden="true" /> {t('about.viewLicense')}
            </a>
          </Panel>
        </>
      )}
    </>
  );
}

export function Resources() {
  const { gpus } = useData();
  const { t } = useI18n();
  return (
    <>
      <Header
        title={t('resources.title')}
        subtitle={t('resources.subtitle')}
      />
      <div className="cards">
        {gpus.map(gpu => (
          <div className="gpu" key={gpu.id}>
            <div>
              <b>GPU {gpu.id}</b>
              <span>{gpu.name}</span>
            </div>
            <Status value={gpu.busy ? 'busy' : 'available'} />
            <small>
              {gpu.memory_total_mb
                ? `${gpu.memory_total_mb} MB`
                : t('common.memoryUnavailable')}
            </small>
          </div>
        ))}
      </div>
      {gpus.length === 0 && (
        <Panel title={t('resources.noDevicesTitle')}>
          <p>{t('resources.noDevices')}</p>
        </Panel>
      )}
    </>
  );
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

function ExperimentTable({
  rows,
  onDelete,
}: {
  rows: Experiment[];
  onDelete?: (experiment: Experiment) => void;
}) {
  const { t, locale } = useI18n();
  return (
    <table>
      <thead>
        <tr>
          <th>{t('table.experiment')}</th>
          <th>{t('table.task')}</th>
          <th>{t('table.status')}</th>
          <th>{t('table.gpu')}</th>
          <th>{t('common.date')}</th>
          {onDelete && <th>{t('common.actions')}</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map(experiment => (
          <tr key={experiment.id}>
            <td>
              <Link to={`/experiments/${experiment.id}`}>
                {experiment.name}
              </Link>
            </td>
            <td>{taskLabel(experiment.task_type, t)}</td>
            <td>
              <Status value={experiment.status} />
            </td>
            <td>{experiment.gpu_id ?? '—'}</td>
            <td>{new Date(experiment.created_at).toLocaleString(locale)}</td>
            {onDelete && (
              <td>
                <button
                  type="button"
                  className="danger compact"
                  disabled={isActive(experiment)}
                  onClick={() => onDelete(experiment)}
                >
                  {t('common.delete')}
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
