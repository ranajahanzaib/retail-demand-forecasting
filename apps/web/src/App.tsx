import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowUpRight,
  Database,
  Gauge,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatUnits } from './lib/metrics';
type Item = { product_id: string; description: string };
type Forecast = {
  product_id: string;
  product_description: string;
  forecast_origin: string;
  target_week: string;
  horizon: number;
  predicted_units: number;
  baseline_units: number;
  lower_80: number;
  upper_80: number;
  lower_90: number;
  upper_90: number;
};
const featureExplanations: Record<string, string> = {
  product_code: 'Identifies the SKU within the pooled model.',
  horizon: 'How many weeks ahead the prediction is made.',
  lag_1: 'Units sold in the most recent complete week.',
  lag_2: 'Units sold two complete weeks before origin.',
  lag_3: 'Units sold three complete weeks before origin.',
  lag_4: 'Units sold four complete weeks before origin.',
  lag_8: 'Units sold eight complete weeks before origin.',
  mean_2: 'Average units across the last two complete weeks.',
  mean_4: 'Average units across the last four complete weeks.',
  mean_8: 'Average units across the last eight complete weeks.',
  std_4: 'Variation in units across the last four weeks.',
  max_4: 'Highest weekly units in the last four weeks.',
  min_4: 'Lowest weekly units in the last four weeks.',
  zero_weeks_8: 'Number of zero-sales weeks in the last eight weeks.',
  weeks_since_sale: 'Weeks since the latest positive sale.',
  age_weeks: 'Number of observed weeks for this product at origin.',
  target_month: 'Calendar month of the forecast target week.',
  target_quarter: 'Calendar quarter of the forecast target week.',
};
const get = async <T,>(path: string): Promise<T> => {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
};
export default function App() {
  const [selected, setSelected] = useState('');
  const [search, setSearch] = useState('');
  const [adjust, setAdjust] = useState(30);
  const [window, setWindow] = useState(4);
  const [shockType, setShockType] = useState<'sustained' | 'one-time'>('sustained');
  const [section, setSection] = useState('Overview');
  const [interval, setInterval] = useState<'off' | '80' | '90'>('80');
  const [fold, setFold] = useState('all');
  const meta = useQuery({ queryKey: ['meta'], queryFn: () => get<any>('/api/metadata') });
  const metric = useQuery({
    queryKey: ['metrics'],
    queryFn: () => get<any>('/api/models/metrics'),
  });
  const health = useQuery({ queryKey: ['health'], queryFn: () => get<any>('/api/health') });
  const horizonMetrics = useQuery({
    queryKey: ['horizon-metrics'],
    queryFn: () => get<any>('/api/models/metrics/by-horizon'),
  });
  const productMetrics = useQuery({
    queryKey: ['product-metrics'],
    queryFn: () => get<any>('/api/models/metrics/by-product'),
  });
  const prods = useQuery({
    queryKey: ['products', search],
    queryFn: () => get<{ items: Item[] }>('/api/products?q=' + encodeURIComponent(search)),
  });
  const forecasts = useQuery({
    queryKey: ['forecast'],
    queryFn: () => get<{ items: Forecast[] }>('/api/forecasts'),
  });
  const coverage = useQuery({
    queryKey: ['coverage'],
    queryFn: () => get<any>('/api/intervals/coverage'),
  });
  const backtests = useQuery({
    queryKey: ['backtests'],
    queryFn: () => get<any>('/api/backtests'),
  });
  const quality = useQuery({
    queryKey: ['quality'],
    queryFn: () => get<any>('/api/dataset/quality'),
  });
  const manifest = useQuery({
    queryKey: ['manifest'],
    queryFn: () => get<any>('/api/dataset/manifest'),
  });
  const importance = useQuery({
    queryKey: ['importance'],
    queryFn: () => get<any>('/api/features/importance'),
  });
  const history = useQuery({
    queryKey: ['history', selected],
    queryFn: () =>
      get<{ items: { week: string; units: number }[] }>(
        `/api/products/${encodeURIComponent(selected)}/history`,
      ),
    enabled: !!selected,
  });
  const sim = useQuery({
    queryKey: ['sim', selected, adjust, window, shockType],
    queryFn: async () => {
      const r = await fetch('/api/simulations/demand-shift', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          product_id: selected,
          adjustment_pct: adjust,
          window_weeks: window,
          shock_type: shockType,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    enabled: !!selected,
  });
  const products = prods.data?.items ?? [];
  const active = selected || products[0]?.product_id || '';
  useEffect(() => {
    if (!selected && products.length) setSelected(products[0].product_id);
  }, [products, selected]);
  const productForecast = (forecasts.data?.items ?? []).filter((f) => f.product_id === active);
  const chart = useMemo(
    () => [
      ...(history.data?.items ?? [])
        .slice(-16)
        .map((x) => ({ week: x.week.slice(5), actual: x.units })),
      ...productForecast.map((x, i) => ({
        week: x.target_week.slice(5),
        forecast: x.predicted_units,
        simulated: sim.data?.items?.[i]?.simulated_units,
        baseline: x.baseline_units,
        band:
          interval === '80'
            ? [x.lower_80, x.upper_80]
            : interval === '90'
              ? [x.lower_90, x.upper_90]
              : undefined,
      })),
    ],
    [history.data, productForecast, interval, sim.data],
  );
  const all = forecasts.data?.items ?? [];
  const total = all.reduce((s, f) => s + f.predicted_units, 0);
  const lgb = metric.data?.['LightGBM']?.mae;
  const selectedBaseline = meta.data?.selected_baseline;
  const baselineMae = metric.data?.[selectedBaseline]?.mae;
  const maeDelta = lgb != null && baselineMae != null ? lgb - baselineMae : null;
  const error = meta.isError || forecasts.isError || prods.isError;
  const holdoutChartData = Object.entries(metric.data ?? {})
    .filter(([name, v]: any) => name !== 'comparison' && v?.mae != null)
    .map(([name, v]: any) => ({ name: name.replace('4-week ', '4w '), MAE: v.mae }));
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">D</span>
          <div>
            DEMAND<span>SENSE</span>
            <small>FORECAST LAB</small>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        {[
          'Overview',
          'Products',
          'Model comparison',
          'Backtesting',
          'Reliability',
          'Data quality',
        ].map((s, i) => (
          <button
            className={'nav ' + (section === s ? 'active' : '')}
            onClick={() => setSection(s)}
            key={s}
          >
            {
              [
                <Activity />,
                <Search />,
                <Gauge />,
                <ArrowUpRight />,
                <ShieldCheck />,
                <Database />,
              ][i]
            }
            {s}
          </button>
        ))}
        <div className="side-foot">
          <i />
          LOCAL ENGINE
          <br />
          <b>
            {health.data?.status === 'ok'
              ? 'API connected'
              : health.isLoading
                ? 'Connecting…'
                : 'API unavailable'}
          </b>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <div className="eyebrow">RETAIL FORECASTING / {section.toUpperCase()}</div>
            <h1>{section === 'Overview' ? 'Forecast overview' : section}</h1>
          </div>
          <div className="header-right">
            <span className="local">
              <i />{' '}
              {meta.data?.data_mode?.startsWith('synthetic')
                ? 'SYNTHETIC DEMO'
                : (meta.data?.data_mode ?? 'LOCAL DATA')}
            </span>
            <div className="avatar">DS</div>
          </div>
        </header>
        {(error || !meta.data?.model_id) && (
          <div className="notice">
            Forecast artifacts are not available yet. Build the offline synthetic fixture with{' '}
            <code>uv run demandsense build-demo</code> or prepare the UCI workbook and run{' '}
            <code>uv run demandsense pipeline --input ../../data/raw/Online-Retail.xlsx</code> from{' '}
            <code>apps/api</code>.
          </div>
        )}
        {meta.isLoading && (
          <div className="loading-state" role="status">
            Loading local dataset and model artifacts…
          </div>
        )}
        <div className="intro">
          <div>
            <h2>
              Forecast demand.
              <br />
              <em>Measure uncertainty.</em>
            </h2>
            <p>
              Four-week product forecasts with historical backtests and an honest view of model
              reliability.
            </p>
          </div>
          <div className="period">
            <span>DATA WINDOW</span>
            <b>
              {meta.data?.weeks?.complete_week_start ?? '—'} <span>→</span>{' '}
              {meta.data?.weeks?.complete_week_end ?? '—'}
            </b>
            <small>Monday–Sunday complete weeks · observed gross positive units</small>
          </div>
        </div>
        <div className="stats">
          <Stat
            label="FORECAST PRODUCTS"
            value={meta.data?.forecast_products ?? '—'}
            detail={`Of ${meta.data?.products ?? '—'} frozen cohort`}
            icon={<Database />}
          />
          <Stat
            label="FORECAST HORIZON"
            value="4 weeks"
            detail="Direct multi-horizon"
            icon={<Activity />}
          />
          <Stat
            label="FORECAST UNITS"
            value={all.length ? fmt(total) : '—'}
            detail="Across forecastable products"
            icon={<ArrowUpRight />}
          />
          <Stat
            label="MODEL VS BASELINE"
            value={lgb == null ? '—' : `${Number(lgb).toFixed(2)} MAE`}
            detail={
              maeDelta == null
                ? 'Untouched final holdout'
                : `${selectedBaseline}: ${maeDelta > 0 ? '+' : ''}${maeDelta.toFixed(2)} MAE units`
            }
            icon={<Gauge />}
          />
        </div>
        <div className="grid">
          <section className="panel chart-panel">
            <div className="panel-head">
              <div>
                <span className="eyebrow">PRODUCT EXPLORER</span>
                <h3>Observed sales & forecast</h3>
                <p>Historical data ends at the vertical forecast boundary.</p>
              </div>
              <label className="select-wrap">
                <Search size={15} />
                <input
                  aria-label="Search products"
                  placeholder="Search SKU or product"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>
            <div className="chart-controls">
              <select
                value={active}
                onChange={(e) => setSelected(e.target.value)}
                aria-label="Select product"
              >
                {products.map((p) => (
                  <option key={p.product_id} value={p.product_id}>
                    {p.product_id} · {p.description}
                  </option>
                ))}
              </select>
              <div className="segmented" aria-label="Prediction interval">
                {(['off', '80', '90'] as const).map((v) => (
                  <button
                    className={interval === v ? 'chosen' : ''}
                    onClick={() => setInterval(v)}
                    key={v}
                  >
                    {v === 'off' ? 'Point only' : `${v}% band`}
                  </button>
                ))}
              </div>
            </div>
            <div className="chart">
              <ResponsiveContainer>
                <ComposedChart data={chart}>
                  <defs>
                    <linearGradient id="band" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#bf794f" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#bf794f" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 5" vertical={false} />
                  <XAxis dataKey="week" tickLine={false} />
                  <YAxis tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Legend />
                  {interval !== 'off' && (
                    <>
                      <Area
                        dataKey="band"
                        stroke="none"
                        fill="url(#band)"
                        name={`${interval}% prediction interval`}
                      />
                    </>
                  )}
                  <Line
                    dataKey="actual"
                    stroke="#263b35"
                    strokeWidth={2.4}
                    dot={false}
                    name="Observed units"
                  />
                  <Line
                    dataKey="forecast"
                    stroke="#c06d41"
                    strokeWidth={2.5}
                    strokeDasharray="6 4"
                    name="LightGBM forecast"
                  />
                  <Line
                    dataKey="simulated"
                    stroke="#678ea1"
                    strokeWidth={2}
                    strokeDasharray="2 3"
                    name="Scenario forecast"
                  />
                  <Line
                    dataKey="baseline"
                    stroke="#89928a"
                    strokeDasharray="3 4"
                    dot={false}
                    name="4-week mean"
                  />
                  {productForecast[0] && (
                    <ReferenceLine
                      x={productForecast[0].target_week.slice(5)}
                      stroke="#bd7048"
                      strokeDasharray="4 4"
                      label="Forecast"
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="caption">
              <span className="boundary" />
              Forecast origin · {productForecast[0]?.forecast_origin ?? '—'}
              <span className="unit">UNITS / WEEK</span>
            </div>
          </section>
          <section className="panel sim-panel">
            <div className="panel-head">
              <div>
                <span className="eyebrow">SCENARIO LAB</span>
                <h3>Demand shift simulator</h3>
                <p>Recomputes history features with the frozen model.</p>
              </div>
              <SlidersHorizontal size={18} />
            </div>
            <label className="field-title">PRODUCT</label>
            <select
              aria-label="Simulator product"
              value={active}
              onChange={(e) => setSelected(e.target.value)}
            >
              {products.map((p) => (
                <option key={p.product_id} value={p.product_id}>
                  {p.product_id} · {p.description}
                </option>
              ))}
            </select>
            <div className="range-head">
              <label className="field-title">RECENT DEMAND SHIFT</label>
              <b>
                {adjust > 0 ? '+' : ''}
                {adjust}%
              </b>
            </div>
            <input
              aria-label="Recent demand adjustment"
              className="range"
              type="range"
              min="-50"
              max="100"
              step="5"
              value={adjust}
              onChange={(e) => setAdjust(+e.target.value)}
            />
            <div className="range-label">
              <span>−50% slowdown</span>
              <span>+100% increase</span>
            </div>
            <label className="field-title">HISTORY WINDOW</label>
            <div className="segmented">
              {[2, 4, 8].map((n) => (
                <button
                  className={window === n ? 'chosen' : ''}
                  onClick={() => setWindow(n)}
                  key={n}
                >
                  {n} weeks
                </button>
              ))}
            </div>
            <label className="field-title">SHOCK PROFILE</label>
            <div className="segmented">
              <button
                className={shockType === 'sustained' ? 'chosen' : ''}
                onClick={() => setShockType('sustained')}
              >
                Sustained shift
              </button>
              <button
                className={shockType === 'one-time' ? 'chosen' : ''}
                onClick={() => setShockType('one-time')}
              >
                One-week shock
              </button>
            </div>
            <div className="sim-result">
              <div>
                <span>ORIGINAL PREDICTION</span>
                <b>
                  {fmt(sim.data?.items?.reduce((s: number, x: any) => s + x.original_units, 0))}
                  <small> units</small>
                </b>
              </div>
              <div>
                <span>SIMULATED PREDICTION</span>
                <b className="accent">
                  {fmt(sim.data?.items?.reduce((s: number, x: any) => s + x.simulated_units, 0))}
                  <small> units</small>
                </b>
              </div>
            </div>
            <div className="scenario-delta">
              Change: {fmt(sim.data?.items?.reduce((s: number, x: any) => s + x.change_units, 0))}{' '}
              units across four weeks
            </div>
            <div className="caveat">
              {sim.data?.out_of_range_features?.length
                ? `Out-of-range history features: ${sim.data.out_of_range_features.join(', ')}. `
                : ''}
              Scenario sensitivity only; hypothetical output has no known future ground truth and is
              not an accuracy estimate.
            </div>
          </section>
        </div>
        <div className="lower-grid">
          <section className="panel">
            <div className="panel-head">
              <div>
                <span className="eyebrow">HOLDOUT EVALUATION</span>
                <h3>Does ML earn its complexity?</h3>
                <p>
                  Same products and test observations · lower MAE is better. Validation selected{' '}
                  {selectedBaseline ?? 'a baseline'}.
                </p>
              </div>
            </div>
            {holdoutChartData.length ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={holdoutChartData}
                  layout="vertical"
                  margin={{ left: 10, right: 30 }}
                >
                  <CartesianGrid strokeDasharray="3 5" horizontal={false} />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="name" width={155} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="MAE" fill="#668475" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="empty-state">Holdout metrics are not available yet.</p>
            )}
            <p className="small-note">
              Positive MAE difference means LightGBM was worse than the selected baseline. Product
              wins/losses: {metric.data?.comparison?.products_won ?? '—'} /{' '}
              {metric.data?.comparison?.products_lost ?? '—'}.
            </p>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <span className="eyebrow">MODEL RELIABILITY</span>
                <h3>Prediction intervals</h3>
                <p>Pooled absolute-error calibration on pre-test rolling folds.</p>
              </div>
              <ShieldCheck size={19} />
            </div>
            <div className="coverage">
              <div>
                <span>NOMINAL / OBSERVED 80%</span>
                <b>
                  80% /{' '}
                  {coverage.data?.observed_80 == null
                    ? '—'
                    : `${(coverage.data.observed_80 * 100).toFixed(1)}%`}
                </b>
              </div>
              <div>
                <span>NOMINAL / OBSERVED 90%</span>
                <b>
                  90% /{' '}
                  {coverage.data?.observed_90 == null
                    ? '—'
                    : `${(coverage.data.observed_90 * 100).toFixed(1)}%`}
                </b>
              </div>
            </div>
            <p className="small-note">
              Coverage by horizon is available below. Intervals are empirical error ranges, not
              parameter confidence intervals; coverage may shift with demand.
            </p>
          </section>
        </div>
        {section === 'Backtesting' && (
          <section className="panel detail-panel">
            <div className="panel-head">
              <div>
                <span className="eyebrow">CHRONOLOGICAL OUT OF SAMPLE</span>
                <h3>Historical forecast records</h3>
                <p>
                  Predictions precede target observations; validation and final holdout are labeled
                  separately.
                </p>
              </div>
              <select
                aria-label="Backtest fold"
                value={fold}
                onChange={(e) => setFold(e.target.value)}
              >
                <option value="all">All folds</option>
                <option value="validation">Validation</option>
                <option value="final_test">Final holdout</option>
              </select>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>FOLD</th>
                    <th>SKU</th>
                    <th>ORIGIN</th>
                    <th>TARGET WEEK</th>
                    <th>HORIZON</th>
                    <th>ACTUAL</th>
                    <th>LIGHTGBM</th>
                    <th>BASELINE</th>
                  </tr>
                </thead>
                <tbody>
                  {(backtests.data?.items ?? [])
                    .filter((r: any) => fold === 'all' || r.fold === fold)
                    .slice(0, 100)
                    .map((r: any, i: number) => (
                      <tr key={i}>
                        <td>{r.fold}</td>
                        <td>{r.product_id}</td>
                        <td>{r.forecast_origin}</td>
                        <td>{r.target_week}</td>
                        <td>+{r.horizon}</td>
                        <td>{fmt(r.actual_units)}</td>
                        <td>{fmt(r.predicted_units)}</td>
                        <td>{fmt(r.baseline_units)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {section === 'Reliability' && (
          <>
            <section className="panel detail-panel">
              <div className="panel-head">
                <div>
                  <span className="eyebrow">CALIBRATION & MODEL RELIANCE</span>
                  <h3>Feature gain and explanations</h3>
                  <p>Gain describes model reliance. It does not establish causality.</p>
                </div>
              </div>
              <div className="importance-list">
                {(importance.data?.items ?? []).slice(0, 10).map((x: any, i: number) => (
                  <div key={x.name}>
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    <b>{x.name.replace(/_/g, ' ')}</b>
                    <i
                      style={{
                        width: `${Math.max(2, (100 * x.gain) / Math.max(1, importance.data?.items?.[0]?.gain ?? 1))}%`,
                      }}
                    />
                    <small className="importance-description">
                      {featureExplanations[x.name] ?? 'Historical model input.'}
                    </small>
                    <small>
                      {(100 * (x.relative_importance ?? 0)).toFixed(1)}% ·{' '}
                      {Math.round(x.gain).toLocaleString()} gain
                    </small>
                  </div>
                ))}
              </div>
              <p className="small-note">
                Gain percentages are normalized across model features. Prediction intervals are
                historical empirical error ranges; coverage can deteriorate under distribution
                shift.
              </p>
            </section>
            <section className="panel detail-panel">
              <div className="panel-head">
                <div>
                  <span className="eyebrow">FINAL HOLDOUT</span>
                  <h3>Coverage by forecast horizon</h3>
                  <p>Observed coverage compared with 80% and 90% nominal intervals.</p>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>HORIZON</th>
                      <th>COUNT</th>
                      <th>80% NOMINAL</th>
                      <th>80% OBSERVED</th>
                      <th>90% NOMINAL</th>
                      <th>90% OBSERVED</th>
                      <th>MEAN 80% WIDTH</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(coverage.data?.by_horizon ?? []).map((r: any) => (
                      <tr key={r.horizon}>
                        <td>+{r.horizon} week</td>
                        <td>{r.count}</td>
                        <td>80%</td>
                        <td>
                          {r.observed_80 == null ? '—' : `${(r.observed_80 * 100).toFixed(1)}%`}
                        </td>
                        <td>90%</td>
                        <td>
                          {r.observed_90 == null ? '—' : `${(r.observed_90 * 100).toFixed(1)}%`}
                        </td>
                        <td>{r.mean_width_80 == null ? '—' : fmt(r.mean_width_80)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
        {section === 'Data quality' && (
          <section className="panel detail-panel">
            <div className="panel-head">
              <div>
                <span className="eyebrow">INGESTION AUDIT</span>
                <h3>Transaction preparation</h3>
                <p>Excluded and accepted rows remain separately counted.</p>
              </div>
            </div>
            <div className="quality-grid">
              {Object.entries(quality.data ?? {})
                .filter(([, v]) => typeof v === 'number')
                .map(([k, v]) => (
                  <div key={k}>
                    <span>{k.replace(/_/g, ' ')}</span>
                    <b>{typeof v === 'number' ? Number(v).toLocaleString() : String(v)}</b>
                  </div>
                ))}
            </div>
            <div className="manifest-grid">
              <div>
                <span>DATA MODE</span>
                <b>{manifest.data?.data_mode ?? '—'}</b>
              </div>
              <div>
                <span>DATASET DOI</span>
                <b>{manifest.data?.dataset_doi ?? 'Synthetic fixture / no DOI'}</b>
              </div>
              <div>
                <span>SOURCE SHA-256</span>
                <b>{manifest.data?.source_sha256 ?? '—'}</b>
              </div>
              <div>
                <span>INGESTED UTC</span>
                <b>{manifest.data?.ingested_at_utc ?? '—'}</b>
              </div>
            </div>
            <p className="small-note">
              {quality.data?.target_definition ?? 'Run the pipeline to inspect quality metadata.'}
            </p>
          </section>
        )}
        {section === 'Model comparison' && (
          <>
            <section className="panel detail-panel">
              <div className="panel-head">
                <div>
                  <span className="eyebrow">FINAL FOUR-WEEK HOLDOUT</span>
                  <h3>Metrics on identical forecast records</h3>
                  <p>
                    WAPE is total absolute error divided by actual unit volume. Positive bias means
                    overforecasting.
                  </p>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>MODEL</th>
                      <th>MAE (UNITS)</th>
                      <th>WAPE</th>
                      <th>BIAS (UNITS)</th>
                      <th>COUNT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metric.data ?? {})
                      .filter(([name, v]: any) => name !== 'comparison' && v?.mae !== undefined)
                      .map(([name, v]: any) => (
                        <tr key={name}>
                          <td>{name}</td>
                          <td>{v.mae == null ? '—' : Number(v.mae).toFixed(2)}</td>
                          <td>
                            {v.wape_percent == null ? '—' : `${Number(v.wape_percent).toFixed(1)}%`}
                          </td>
                          <td>{v.bias == null ? '—' : Number(v.bias).toFixed(2)}</td>
                          <td>{v.count}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
            <div className="lower-grid">
              <section className="panel detail-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">HORIZON ERROR</span>
                    <h3>MAE by forecast week</h3>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>HORIZON</th>
                        <th>LIGHTGBM MAE</th>
                        <th>{selectedBaseline ?? 'BASELINE'} MAE</th>
                        <th>COUNT</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(horizonMetrics.data?.items ?? []).map((r: any) => (
                        <tr key={r.horizon}>
                          <td>+{r.horizon}</td>
                          <td>
                            {r.LightGBM?.mae == null ? '—' : Number(r.LightGBM.mae).toFixed(2)}
                          </td>
                          <td>
                            {r[selectedBaseline]?.mae == null
                              ? '—'
                              : Number(r[selectedBaseline].mae).toFixed(2)}
                          </td>
                          <td>{r.LightGBM?.count ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="panel detail-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">SKU ERROR</span>
                    <h3>Product-level holdout MAE</h3>
                    <p>Products with equal MAE are neither wins nor losses.</p>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>PRODUCT</th>
                        <th>LIGHTGBM MAE</th>
                        <th>BASELINE MAE</th>
                        <th>N</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(productMetrics.data?.items ?? []).slice(0, 30).map((r: any) => (
                        <tr key={r.product_id}>
                          <td>{r.product_id}</td>
                          <td>
                            {r.LightGBM?.mae == null ? '—' : Number(r.LightGBM.mae).toFixed(2)}
                          </td>
                          <td>
                            {r[selectedBaseline]?.mae == null
                              ? '—'
                              : Number(r[selectedBaseline].mae).toFixed(2)}
                          </td>
                          <td>{r.LightGBM?.count ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </>
        )}
        <footer>
          <span>
            RETAIL DEMAND FORECASTING <small>v0.1 · LOCAL FORECAST LAB</small>
          </span>
          <span>
            Gross positive sales are a proxy for demand; stockouts and missed sales are unobserved.
          </span>
        </footer>
      </main>
    </div>
  );
}
function Stat({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: any;
  detail: string;
  icon: any;
}) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span>{label}</span>
        {icon}
      </div>
      <b>{value}</b>
      <small>{detail}</small>
    </div>
  );
}
function fmt(n: number | undefined | null) {
  return n == null ? '—' : formatUnits(n);
}
