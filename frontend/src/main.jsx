import React, { useEffect, useMemo, useState, useCallback } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import {
  listTrains,
  getJourney,
  simulateDelayEvent,
  getHistoricalMeta,
  predictHistorical,
} from "./api";

const SIMULATED_DELAY_MINUTES = 15;

function App() {
  const [view, setView] = useState("live"); // "live" | "historical"
  const [deskOpen, setDeskOpen] = useState(false);

  return (
    <div className="app">
      <TopBar view={view} setView={setView} deskOpen={deskOpen} setDeskOpen={setDeskOpen} />
      {view === "live" ? <LiveOperations /> : <HistoricalTest />}
    </div>
  );
}

function TopBar({ view, setView, deskOpen, setDeskOpen }) {
  return (
    <header className="topbar">
      <div className="brandGroup">
        <div className="brandIcon">◎</div>
        <div>
          <div className="brand">RailPulse</div>
          <div className="subtitle">Operations Intelligence</div>
        </div>
        <div className="divider" />
        <button
          className={`viewTab ${view === "live" ? "active" : ""}`}
          onClick={() => setView("live")}
        >
          LIVE OPERATIONS
        </button>
        <button
          className={`viewTab ${view === "historical" ? "active" : ""}`}
          onClick={() => setView("historical")}
        >
          HISTORICAL DATASET TEST
        </button>
      </div>

      <div className="topRight">
        <span>Mode: <b>{view === "live" ? "Live simulation" : "Historical model"}</b></span>
        <i />
        <span>System status: <em>Operational</em></span>
        <div className="desk">
          <button onClick={() => setDeskOpen(v => !v)}>
            <small>PH</small> Control Desk <span className="chevron">⌄</span>
          </button>
          {deskOpen && (
            <div className="menu">
              <div>Control Desk</div>
              <div>Operations View</div>
              <div>Supervisor View</div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

/* ============================== LIVE VIEW ============================== */

function LiveOperations() {
  const [trains, setTrains] = useState([]);
  const [loadingTrains, setLoadingTrains] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTrainNo, setSelectedTrainNo] = useState(null);
  const [query, setQuery] = useState("");

  const [journey, setJourney] = useState(null);
  const [journeyLoading, setJourneyLoading] = useState(false);
  const [selectedStationCode, setSelectedStationCode] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    listTrains()
      .then(data => {
        setTrains(data);
        if (data.length > 0) setSelectedTrainNo(data[0].train_no);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoadingTrains(false));
  }, []);

  const selectedTrain = useMemo(
    () => trains.find(t => t.train_no === selectedTrainNo) || null,
    [trains, selectedTrainNo]
  );

  const loadJourney = useCallback((trainNo, currentStationCode) => {
    if (!trainNo || !currentStationCode) return;
    setJourneyLoading(true);
    getJourney(trainNo, currentStationCode)
      .then(data => {
        setJourney(data);
        setLastUpdated(new Date());
        if (data.stations.length > 0) setSelectedStationCode(data.stations[0].station.code);
      })
      .catch(err => setError(err.message))
      .finally(() => setJourneyLoading(false));
  }, []);

  useEffect(() => {
    if (selectedTrain) {
      setJourney(null);
      loadJourney(selectedTrain.train_no, selectedTrain.current_station_code);
    }
  }, [selectedTrain, loadJourney]);

  const visibleTrains = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return trains;
    return trains.filter(t =>
      [t.train_no, t.route_id, t.current_station_code].some(v => String(v).toLowerCase().includes(q))
    );
  }, [trains, query]);

  const handleSimulate = () => {
    if (!selectedTrain) return;
    setSimulating(true);
    simulateDelayEvent(selectedTrain.train_no, selectedTrain.current_station_code, SIMULATED_DELAY_MINUTES)
      .then(() => loadJourney(selectedTrain.train_no, selectedTrain.current_station_code))
      .catch(err => setError(err.message))
      .finally(() => setSimulating(false));
  };

  const routeStations = useMemo(() => {
    if (!selectedTrain) return [];
    return selectedTrain.stations.map(s => {
      let state = "future";
      if (s.station_seq < selectedTrain.current_station_seq) state = "passed";
      else if (s.station_seq === selectedTrain.current_station_seq) state = "current";

      const prediction = journey?.stations.find(js => js.station.code === s.code) || null;
      return { ...s, state, prediction };
    });
  }, [selectedTrain, journey]);

  const upcoming = journey?.stations || [];
  const delaySummary = useMemo(() => {
    const onTime = upcoming.filter(s => s.predicted_delay_minutes < 5).length;
    const delayed = upcoming.filter(s => s.predicted_delay_minutes >= 5 && s.predicted_delay_minutes < 20).length;
    const critical = upcoming.filter(s => s.predicted_delay_minutes >= 20).length;
    const avg = upcoming.length
      ? upcoming.reduce((sum, s) => sum + s.predicted_delay_minutes, 0) / upcoming.length
      : 0;
    return { onTime, delayed, critical, avg };
  }, [upcoming]);

  const selectedPrediction = upcoming.find(s => s.station.code === selectedStationCode) || null;

  return (
    <>
      {error && <div className="errorBanner">{error}</div>}

      <div className="metrics">
        <Metric label="ACTIVE TRAINS" value={String(trains.length)} />
        <Metric label="ON TIME (ROUTE)" value={String(delaySummary.onTime)} cls="green" />
        <Metric label="DELAYED (ROUTE)" value={String(delaySummary.delayed)} cls="orange" />
        <Metric label="CRITICAL (ROUTE)" value={String(delaySummary.critical)} cls="red" />
        <Metric label="AVG PREDICTED DELAY" value={`${delaySummary.avg.toFixed(1)} min`} cls="green" />
      </div>

      <div className="body">
        <aside className="left">
          <div className="panelHead"><b>ACTIVE TRAINS</b><span>{trains.length}</span></div>
          <div className="search">
            <span>⌕</span>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search train number or station"
            />
          </div>

          <div className="trainList">
            {loadingTrains && <div className="hint">Loading trains…</div>}
            {!loadingTrains && visibleTrains.map(t => (
              <button
                key={t.train_no}
                className={`train ${selectedTrainNo === t.train_no ? "selected" : ""}`}
                onClick={() => setSelectedTrainNo(t.train_no)}
              >
                <div className="trainTop">
                  <strong>{t.train_no}</strong>
                </div>
                <div className="trainName">{t.route_id}</div>
                <div className="current">Current: {t.current_station_code}</div>
              </button>
            ))}
          </div>

          <div className="simulateArea">
            <button className="simulate" onClick={handleSimulate} disabled={!selectedTrain || simulating}>
              <span>ϟ</span> {simulating ? "Simulating…" : "Simulate delay event"}
            </button>
          </div>
        </aside>

        <section className="center">
          <div className="routeHeader">
            <div className="routeLeft">
              <div className="routeTab">ROUTE MONITOR</div>
              {selectedTrain && (
                <>
                  <b>Train {selectedTrain.train_no}</b>
                  <span>
                    {selectedTrain.stations[0]?.code}&nbsp; → &nbsp;
                    {selectedTrain.stations[selectedTrain.stations.length - 1]?.code}
                  </span>
                </>
              )}
            </div>
            <span>{selectedTrain?.route_id}{lastUpdated ? ` · updated ${lastUpdated.toLocaleTimeString()}` : ""}</span>
          </div>

          <div className="map">
            <div className="atStation">AT STATION</div>
            <div className="railLine"><span /></div>
            <div className="stations" style={{ gridTemplateColumns: `repeat(${Math.max(routeStations.length, 1)}, 1fr)` }}>
              {routeStations.map(s => (
                <Station
                  key={s.code}
                  station={s}
                  selected={selectedStationCode === s.code}
                  onSelect={() => s.prediction && setSelectedStationCode(s.code)}
                />
              ))}
            </div>
          </div>

          <div className="downstream">
            <div className="downHead">
              <b>DOWNSTREAM PREDICTIONS</b>
              <span>{journeyLoading ? "Recalculating…" : "Live model prediction · click a row to inspect"}</span>
            </div>

            <div className="tableScroll">
              <table>
                <thead>
                  <tr>
                    <th>STATION</th><th>DISTANCE</th><th>SCHEDULED</th>
                    <th>PREDICTED ETA</th><th>DELAY</th><th>WEATHER</th>
                    <th>CONGESTION</th><th>DWELL</th>
                  </tr>
                </thead>
                <tbody>
                  {upcoming.map(s => (
                    <tr
                      key={s.station.code}
                      className={selectedStationCode === s.station.code ? "rowSelected" : ""}
                      onClick={() => setSelectedStationCode(s.station.code)}
                    >
                      <td><b>{s.station.code}</b> <span>{s.station.name}</span></td>
                      <td>{s.station.distance_km} km</td>
                      <td>{formatTime(s.scheduled_time)}</td>
                      <td className="eta">{formatTime(s.predicted_eta)}</td>
                      <td className={s.predicted_delay_minutes > 12 ? "red" : "orange"}>
                        +{s.predicted_delay_minutes.toFixed(1)}
                      </td>
                      <td>{weatherLabel(s.contributions)}</td>
                      <td>{congestionLabel(s.contributions)}</td>
                      <td>{dwellLabel(s.contributions)}</td>
                    </tr>
                  ))}
                  {!journeyLoading && upcoming.length === 0 && (
                    <tr><td colSpan={8} className="hint">No remaining stations for this train.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <aside className="right">
          {selectedPrediction ? (
            <PredictionPanel prediction={selectedPrediction} />
          ) : (
            <div className="hint" style={{ padding: 16 }}>Select a station to see the prediction breakdown.</div>
          )}
        </aside>
      </div>
    </>
  );
}

function PredictionPanel({ prediction }) {
  const lowerMin = minutesFromScheduled(prediction.scheduled_time, prediction.confidence_lower);
  const upperMin = minutesFromScheduled(prediction.scheduled_time, prediction.confidence_upper);
  const spread = ((upperMin - lowerMin) / 2).toFixed(1);

  const barFactors = prediction.contributions.filter(c => c.factor !== "carried_over_delay" || c.minutes !== 0);
  const maxAbs = Math.max(1, ...barFactors.map(c => Math.abs(c.minutes)));
  const barColor = {
    carried_over_delay: "blue",
    weather: "orangeBar",
    congestion: "gray",
    station_dwell: "greenBar",
    unscheduled_events: "gray",
  };

  return (
    <>
      <div className="rightHead">PREDICTION INTELLIGENCE</div>
      <div className="prediction">
        <b>{prediction.station.code}</b>
        <span>{prediction.station.name}</span>
        <small>{prediction.station.distance_km} km from origin</small>
      </div>

      <div className="arrival">
        <div>
          <span>PREDICTED ARRIVAL</span>
          <b>{formatTime(prediction.predicted_eta)}</b>
        </div>
        <div>
          <span>PREDICTED DELAY</span>
          <b className={prediction.predicted_delay_minutes > 12 ? "red" : "orange"}>
            +{prediction.predicted_delay_minutes.toFixed(1)} min
          </b>
        </div>
      </div>

      <div className="uncertainty">
        <span>◷ &nbsp;Prediction uncertainty (10–90%)</span><b>±{spread} min</b>
      </div>

      {prediction.eta_change && (
        <div className="rightSection changeBanner">
          <b className="sectionLabel">ETA CHANGED SINCE LAST CHECK</b>
          <div className="hint">
            {prediction.eta_change.previous_predicted_delay_minutes.toFixed(1)} min → {prediction.eta_change.new_predicted_delay_minutes.toFixed(1)} min
            ({prediction.eta_change.change_minutes > 0 ? "+" : ""}{prediction.eta_change.change_minutes.toFixed(1)} min)
          </div>
        </div>
      )}

      <div className="rightSection">
        <b className="sectionLabel">DELAY CONTRIBUTORS</b>
        {barFactors.map(c => (
          <Bar
            key={c.factor}
            label={factorLabel(c.factor)}
            width={`${Math.min(100, (Math.abs(c.minutes) / maxAbs) * 100)}%`}
            type={barColor[c.factor] || "gray"}
          />
        ))}
      </div>

      <div className="rightSection factors">
        <b className="sectionLabel">OPERATIONAL FACTORS</b>
        <Factor label="Weather" value={weatherLabel(prediction.contributions)} />
        <Factor label="Congestion" value={congestionLabel(prediction.contributions)} />
        <Factor label="Station dwell" value={dwellLabel(prediction.contributions)} />
      </div>

      {prediction.shap_contributions?.length > 0 && (
        <div className="rightSection factors">
          <b className="sectionLabel">TOP MODEL FACTORS (SHAP)</b>
          {prediction.shap_contributions.slice(0, 4).map(c => (
            <Factor
              key={c.feature}
              label={c.feature.replace(/_/g, " ")}
              value={`${c.shap_minutes > 0 ? "+" : ""}${c.shap_minutes.toFixed(1)} min`}
            />
          ))}
        </div>
      )}

      {prediction.recommendations?.length > 0 && (
        <div className="rightSection factors">
          <b className="sectionLabel">RECOMMENDATIONS</b>
          {prediction.recommendations.map((r, i) => (
            <div key={i} className={`recRow prio-${r.priority}`}>
              <span className="recAudience">{r.audience.replace(/_/g, " ")}</span>
              <span>{r.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Metric({ label, value, cls = "" }) {
  return <div className="metric"><span>{label}</span><b className={cls}>{value}</b></div>;
}

function Station({ station, selected, onSelect }) {
  const type = station.state || "future";
  const delay = station.prediction?.predicted_delay_minutes;
  return (
    <button
      type="button"
      className={`station ${type} ${selected ? "focus" : ""}`}
      onClick={onSelect}
      aria-label={`Select station ${station.code} ${station.name}`}
    >
      <div className={`marker ${type}`}>{type === "current" ? "◎" : ""}</div>
      <b>{station.code}</b>
      <small className="state">
        {type === "passed" ? "passed" : type === "current" ? "current" : ""}
      </small>
      <small>{station.name}</small>
      {delay != null && (
        <strong className={delay > 12 ? "red" : "orange"}>+{delay.toFixed(1)}m</strong>
      )}
      <small>{station.distance_km} km</small>
    </button>
  );
}

function Bar({ label, width, type }) {
  return (
    <div className="barRow">
      <span>{label}</span>
      <div className="barTrack"><i className={type} style={{ width }} /></div>
    </div>
  );
}

function Factor({ label, value }) {
  return <div className="factor"><span>{label}</span><b>{value}</b></div>;
}

function factorLabel(factor) {
  return {
    carried_over_delay: "Carried-over delay",
    weather: "Weather",
    congestion: "Congestion",
    station_dwell: "Station dwell",
    unscheduled_events: "Unscheduled events",
  }[factor] || factor;
}

function findContrib(contributions, factor) {
  return contributions?.find(c => c.factor === factor)?.minutes ?? 0;
}

function weatherLabel(contributions) {
  const m = findContrib(contributions, "weather");
  return m >= 4 ? "Adverse" : m >= 1.5 ? "Moderate" : "Normal";
}

function congestionLabel(contributions) {
  const m = findContrib(contributions, "congestion");
  return m >= 4 ? "High" : m >= 1.5 ? "Moderate" : "Normal";
}

function dwellLabel(contributions) {
  const m = findContrib(contributions, "station_dwell");
  return `${m.toFixed(1)}m`;
}

function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function minutesFromScheduled(scheduledIso, targetIso) {
  const scheduled = new Date(scheduledIso).getTime();
  const target = new Date(targetIso).getTime();
  return (target - scheduled) / 60000;
}

/* =========================== HISTORICAL VIEW =========================== */

function HistoricalTest() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    distance_km: 150,
    weather_conditions: "",
    day_of_week: "",
    time_of_day: "",
    train_type: "",
    route_congestion: "",
  });
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getHistoricalMeta()
      .then(data => {
        setMeta(data);
        setForm(f => ({
          ...f,
          weather_conditions: data.weather_conditions[0],
          day_of_week: data.day_of_week[0],
          time_of_day: data.time_of_day[0],
          train_type: data.train_type[0],
          route_congestion: data.route_congestion[0],
        }));
      })
      .catch(err => setError(err.message));
  }, []);

  const handleSubmit = e => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    predictHistorical(form)
      .then(setResult)
      .catch(err => setError(err.message))
      .finally(() => setSubmitting(false));
  };

  const maxAbs = result ? Math.max(1, ...result.factors.map(f => Math.abs(f.impact_minutes))) : 1;

  return (
    <div className="body histBody">
      <section className="center histCenter">
        <div className="routeHeader">
          <div className="routeLeft">
            <div className="routeTab">HISTORICAL DATASET TEST</div>
            <b>Trained on data/train_delay_data.csv</b>
          </div>
          <span>{meta ? `Model MAE: ±${meta.model_mae_minutes} min` : ""}</span>
        </div>

        <div className="histContent">
          <p className="hint histIntro">
            This is a separate model trained directly on the uploaded historical dataset
            (distance, weather, day of week, time of day, train type, route congestion →
            historical delay). It is independent of the live simulation model shown in the
            Live Operations tab — use this panel to test it against real historical records.
          </p>

          {error && <div className="errorBanner">{error}</div>}

          {!meta ? (
            <div className="hint">Loading model metadata…</div>
          ) : (
            <form className="histForm" onSubmit={handleSubmit}>
              <label>
                Distance between stations (km)
                <input
                  type="number"
                  min="1"
                  value={form.distance_km}
                  onChange={e => setForm(f => ({ ...f, distance_km: Number(e.target.value) }))}
                  required
                />
              </label>

              <SelectField
                label="Weather conditions"
                value={form.weather_conditions}
                options={meta.weather_conditions}
                onChange={v => setForm(f => ({ ...f, weather_conditions: v }))}
              />
              <SelectField
                label="Day of the week"
                value={form.day_of_week}
                options={meta.day_of_week}
                onChange={v => setForm(f => ({ ...f, day_of_week: v }))}
              />
              <SelectField
                label="Time of day"
                value={form.time_of_day}
                options={meta.time_of_day}
                onChange={v => setForm(f => ({ ...f, time_of_day: v }))}
              />
              <SelectField
                label="Train type"
                value={form.train_type}
                options={meta.train_type}
                onChange={v => setForm(f => ({ ...f, train_type: v }))}
              />
              <SelectField
                label="Route congestion"
                value={form.route_congestion}
                options={meta.route_congestion}
                onChange={v => setForm(f => ({ ...f, route_congestion: v }))}
              />

              <button type="submit" className="simulate histSubmit" disabled={submitting}>
                {submitting ? "Predicting…" : "Predict historical delay"}
              </button>
            </form>
          )}
        </div>
      </section>

      <aside className="right">
        <div className="rightHead">PREDICTION RESULT</div>
        {!result ? (
          <div className="hint" style={{ padding: 16 }}>Submit the form to see a prediction.</div>
        ) : (
          <>
            <div className="arrival singleArrival">
              <div>
                <span>PREDICTED DELAY</span>
                <b className={result.predicted_delay_minutes > 30 ? "red" : "orange"}>
                  {result.predicted_delay_minutes.toFixed(1)} min
                </b>
              </div>
            </div>
            <div className="uncertainty">
              <span>◷ &nbsp;Model mean absolute error</span><b>±{result.model_mae_minutes} min</b>
            </div>
            <div className="rightSection">
              <b className="sectionLabel">FACTOR IMPACT (SHAP)</b>
              {result.factors.map(f => (
                <Bar
                  key={f.feature}
                  label={f.feature}
                  width={`${Math.min(100, (Math.abs(f.impact_minutes) / maxAbs) * 100)}%`}
                  type={f.impact_minutes >= 0 ? "orangeBar" : "greenBar"}
                />
              ))}
            </div>
            <div className="rightSection factors">
              <b className="sectionLabel">INPUT VALUES</b>
              {result.factors.map(f => (
                <Factor key={f.feature} label={f.feature} value={f.value} />
              ))}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function SelectField({ label, value, options, onChange }) {
  return (
    <label>
      {label}
      <select value={value} onChange={e => onChange(e.target.value)}>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

createRoot(document.getElementById("root")).render(<App />);
