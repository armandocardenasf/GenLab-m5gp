import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity,
  Atom,
  Database,
  FlaskConical,
  Gauge,
  Info,
  LogOut,
} from 'lucide-react';

import { useAuth } from './auth';
import { statusLabel, useI18n } from './i18n';

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Atom /> <span>GenLab <b>M5GP</b></span>
        </div>
        <nav>
          <NavLink to="/"><Activity />{t('nav.overview')}</NavLink>
          <NavLink to="/datasets"><Database />{t('nav.datasets')}</NavLink>
          <NavLink to="/experiments"><FlaskConical />{t('nav.experiments')}</NavLink>
          <NavLink to="/resources"><Gauge />{t('nav.resources')}</NavLink>
          <NavLink to="/about"><Info />{t('nav.about')}</NavLink>
        </nav>
        <div className="account">
          <div>
            <b>{user?.full_name}</b>
            <small>{user?.email}</small>
          </div>
          <button
            className="icon"
            onClick={logout}
            title={t('nav.logout')}
            aria-label={t('nav.logout')}
          >
            <LogOut />
          </button>
        </div>
      </aside>
      <main>{children}</main>
    </div>
  );
}

export const Status = ({ value }: { value: string }) => {
  const { t } = useI18n();
  return <span className={`status ${value}`}>{statusLabel(value, t)}</span>;
};

export function Metric({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="metric">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
