import React from 'react';
import { createRoot } from 'react-dom/client';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom';

import { AuthProvider, useAuth } from './auth';
import { Layout } from './components';
import {
  About,
  Datasets,
  ExperimentDetail,
  Experiments,
  Login,
  NewExperiment,
  Overview,
  Resources,
} from './pages';
import {
  I18nProvider,
  LanguageSwitcher,
  translate,
  useI18n,
} from './i18n';
import './styles.css';

function App() {
  const { user, loading } = useAuth();
  const { t } = useI18n();

  if (loading) return <div className="center">{t('common.loadingGenLab')}</div>;
  if (!user) return <Login />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/datasets" element={<Datasets />} />
        <Route path="/experiments" element={<Experiments />} />
        <Route path="/experiments/new" element={<NewExperiment />} />
        <Route path="/experiments/:id" element={<ExperimentDetail />} />
        <Route path="/resources" element={<Resources />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  );
}

type ErrorBoundaryState = {
  error: Error | null;
};

class StartupErrorBoundary extends React.Component<
  React.PropsWithChildren,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('GenLab frontend render error', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="startup-error">
        <section>
          <h1>{translate('startup.title')}</h1>
          <p>{translate('startup.description')}</p>
          <pre>{this.state.error.message}</pre>
          <button
            className="primary"
            onClick={() => window.location.reload()}
          >
            {translate('startup.reload')}
          </button>
        </section>
      </main>
    );
  }
}

const rootElement = document.getElementById('root');

if (!rootElement) {
  document.body.innerHTML = `<main class="startup-error"><section><h1>${translate(
    'startup.configTitle',
  )}</h1><p>${translate('startup.rootMissing')}</p></section></main>`;
} else {
  createRoot(rootElement).render(
    <React.StrictMode>
      <I18nProvider>
        <LanguageSwitcher />
        <StartupErrorBoundary>
          <BrowserRouter>
            <AuthProvider>
              <App />
            </AuthProvider>
          </BrowserRouter>
        </StartupErrorBoundary>
      </I18nProvider>
    </React.StrictMode>,
  );
}
