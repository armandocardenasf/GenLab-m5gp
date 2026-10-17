export type RunSummary = {
  id: string;
  name: string;
  dataset_id: string;
  status: string;
  repeat_index: number;
  fold_index: number | null;
  seed: number;
  metrics: Record<string, any> | null;
  progress: Record<string, any>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type DatasetBinding = {
  dataset_id: string;
  dataset_name: string;
  original_name: string;
  target_column: string;
};

export type MetricSummary = {
  mean: number;
  std: number;
  min: number;
  max: number;
  n: number;
};

export type MetricSections = Record<string, Record<string, MetricSummary>>;

export type DatasetRunResult = {
  run_id: string;
  run_name: string;
  dataset_id: string;
  dataset_name: string;
  repeat_index: number | null;
  fold_index: number | null;
  seed: number | null;
  status: string;
  progress_percent: number;
  generation: number | null;
  total_generations: number | null;
  r2_train: number | null;
  r2_test: number | null;
  rmse_train: number | null;
  rmse_test: number | null;
  mae_train: number | null;
  mae_test: number | null;
  accuracy_train: number | null;
  accuracy_test: number | null;
  f1_macro_train: number | null;
  f1_macro_test: number | null;
  model_size: number | null;
  training_time: number | null;
  process_time: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type DatasetAggregate = {
  dataset_id: string;
  dataset_name: string;
  target_column: string;
  total_runs: number;
  completed_runs: number;
  metrics: MetricSections;
  runs: DatasetRunResult[];
};

export type BenchmarkDataset = {
  dataset_id: string;
  dataset_name: string;
  target_column: string;
  values: {
    r2: number[];
    rmse: number[];
    model_size: number[];
    training_time: number[];
  };
  runs: Array<{
    run_id: string;
    repeat_index: number;
    fold_index: number | null;
    r2: number | null;
    rmse: number | null;
    model_size: number | null;
    training_time: number | null;
  }>;
};

export type ExperimentAggregate = {
  experiment_id: string;
  task_type: 'regression' | 'classification';
  total_runs: number;
  completed_runs: number;
  status_counts: Record<string, number>;
  overall: MetricSections;
  by_dataset: DatasetAggregate[];
  benchmark: BenchmarkDataset[];
};

export type ExperimentGroup = {
  id: string;
  name: string;
  task_type: 'regression' | 'classification';
  parameters: Record<string, any>;
  validation: Record<string, any>;
  runs_per_dataset: number;
  preset_name: string | null;
  status: string;
  created_at: string;
  datasets: DatasetBinding[];
  summary: ExperimentAggregate;
  runs?: RunSummary[];
};

export type ExperimentResults = ExperimentAggregate & {
  correlation: number | null;
  scatter: Array<{
    actual: number;
    prediction: number;
    run_id: string;
    dataset_id: string;
    dataset_name: string;
  }>;
};

export type ParameterPreset = {
  id: string;
  name: string;
  description: string;
  task_type: 'both' | 'regression' | 'classification';
  parameters: Record<string, any>;
  is_default: boolean;
  system: boolean;
};

export type Batch = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  experiments: ExperimentGroup[];
};

export type RunContext = {
  run_id: string;
  experiment_id: string | null;
  repeat_index: number | null;
  fold_index: number | null;
  seed: number | null;
};

export type ComparisonMetricSpec = {
  label: string;
  higher_better: boolean;
  log: boolean;
};

export type ComparisonRankingRow = {
  experiment_id: string;
  label: string;
  values: number[];
  mean: number;
  std: number;
  min: number;
  max: number;
  n: number;
  rank: number;
};

export type ComparisonBenchmarkRow = Omit<ComparisonRankingRow, 'rank'>;

export type ComparisonBenchmark = {
  metric: string;
  title: string;
  higher_better: boolean;
  log_scale: boolean;
  rows: ComparisonBenchmarkRow[];
};

export type ComparisonAnalysis = {
  task_type: 'regression' | 'classification';
  generated_at: string;
  primary_metric: string;
  alpha: number;
  metric_specs: Record<string, ComparisonMetricSpec>;
  experiments: Array<{
    id: string;
    name: string;
    task_type: 'regression' | 'classification';
    preset_name: string | null;
    parameters: Record<string, any>;
    validation: Record<string, any>;
    scalar_parameters: Record<string, string | number | boolean>;
    runs_per_dataset: number;
    total_runs: number;
    completed_runs: number;
    status: string;
    created_at: string;
  }>;
  datasets: Array<{
    dataset_id: string;
    dataset_name: string;
    rows: number;
    features: number;
    points: number;
    experiments: Record<string, {
      target_column: string;
      completed_runs: number;
      metrics: Record<string, MetricSummary>;
    }>;
  }>;
  benchmarks: ComparisonBenchmark[];
  rankings: Record<string, ComparisonRankingRow[]>;
  wilcoxon: {
    metric: string;
    metric_label: string;
    alpha: number;
    correction: string;
    pairing: string;
    minimum_pairs_for_inference: number;
    experiments: Array<{ id: string; name: string }>;
    cells: Array<{
      row_experiment_id: string;
      column_experiment_id: string;
      n_pairs: number;
      dataset_ids: string[];
      statistic: number | null;
      p_value: number | null;
      p_adjusted: number | null;
      category: string;
      significant: boolean;
      exploratory: boolean;
      winner_experiment_id: string | null;
      left_mean: number | null;
      right_mean: number | null;
      rank_biserial: number | null;
      median_oriented_difference: number | null;
    }>;
  };
  computational: Record<'samples' | 'features' | 'points', Array<{
    experiment_id: string;
    experiment_name: string;
    dataset_id: string;
    dataset_name: string;
    x: number;
    training_time_mean: number;
    training_time_std: number;
    training_time_min: number;
    training_time_max: number;
    n: number;
  }>>;
  varying_parameters: Array<{
    parameter: string;
    numeric: boolean;
    values: Array<{
      experiment_id: string;
      experiment_name: string;
      value: string | number | boolean | null;
    }>;
    correlations: Record<string, { rho: number | null; p_value: number | null; n: number }>;
  }>;
  parameter_points: Array<{
    parameter: string;
    experiment_id: string;
    experiment_name: string;
    x: number;
    metrics: Record<string, number>;
  }>;
  tradeoff: Array<{
    experiment_id: string;
    experiment_name: string;
    metric: string;
    score: number;
    training_time: number;
    model_size: number | null;
  }>;
  coverage: {
    common_dataset_ids: string[];
    all_dataset_ids: string[];
    benchmark_scope: 'common_datasets' | 'all_available_datasets';
    comparable_on_common_datasets: boolean;
  };
  notes: string[];
};

export type ComparisonReportSummary = {
  id: string;
  name: string;
  description: string;
  task_type: 'regression' | 'classification';
  experiment_ids: string[];
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
  summary: {
    primary_metric: string | null;
    generated_at: string | null;
    experiment_count: number;
    dataset_count: number;
  };
};

export type ComparisonReport = Omit<ComparisonReportSummary, 'summary'> & {
  analysis: ComparisonAnalysis;
};
