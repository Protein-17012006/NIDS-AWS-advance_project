export interface DatasetInfo {
  key: string;
  display: string;
  total_samples: number;
  num_features: number;
  classes: string[];
  class_distribution: Record<string, number>;
}

export interface ModelInfo {
  key: string;
  display: string;
  needs_scaler: boolean;
}

export interface PerClassMetrics {
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
}

export interface PredictResponse {
  dataset: string;
  model: string;
  accuracy: number;
  train_accuracy?: number;
  per_class: Record<string, PerClassMetrics>;
  confusion_matrix: number[][];
  confusion_matrix_pct: number[][];
  class_names: string[];
  predictions: number[];
  true_labels: number[];
  probabilities?: number[][];
  macro_avg: PerClassMetrics;
  weighted_avg: PerClassMetrics;
  sample_count: number;
}

export interface CompareResponse {
  dataset: string;
  results: PredictResponse[];
}

export const CLASS_COLORS: Record<string, string> = {
  'BENIGN': '#10b981',
  'BruteForce': '#f59e0b',
  'DDoS': '#ef4444',
  'DoS': '#f97316',
  'Infiltration': '#8b5cf6',
};

export const MODEL_COLORS: Record<string, string> = {
  'knn': '#3b82f6',
  'logistic_regression': '#10b981',
  'svm': '#f59e0b',
  'decision_tree': '#ef4444',
  'random_forest': '#8b5cf6',
};
