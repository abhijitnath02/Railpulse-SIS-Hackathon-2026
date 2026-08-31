import React, { useState, useEffect, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Train, Zap, CloudRain, Radio, Clock, ChevronRight, Activity, Loader2, AlertTriangle } from "lucide-react";

/**
 * RailPulseDashboard
 *
 * Control-room style live ETA dashboard for the Dynamic ETA Prediction
 * System (SIH 26028). Calls the real FastAPI backend:
 *   GET  /trains
 *   GET  /eta/journey?train_no=...&current_station_code=...
 *   POST /simulate/delay-event
 *
 * Change API_BASE_URL below to point at your running backend
 * (uvicorn backend.main:app --reload, default http://localhost:8000).
 */

const API_BASE_URL = "http://localhost:8000";

const THEME = {
  bg: "#0A0E1A",
  panel: "#111827",
  panelBorder: "#1F2937",
  panelBorderLight: "#2A3444",
  textPrimary: "#E9EDF5",
  textMuted: "#7C879C",
  textFaint: "#4B5568",
  onTime: "#34D399",
  delay: "#F5A623",
  critical: "#F87171",
  brand: "#4C8DFF",
};

const FONT_DISPLAY = "'Space Grotesk', 'Segoe UI', sans-serif";
const FONT_MONO = "'JetBrains Mono', 'Courier New', monospace";
const FONT_BODY = "'Inter', 'Segoe UI', sans-serif";

function statusColor(minutes) {
  if (minutes < 5) return THEME.onTime;
  if (minutes < 15) return THEME.delay;
  return THEME.critical;
}

function formatTime(isoString) {
  return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export default function RailPulseDashboard() {
  const [trains, setTrains] = useState([]);
  const [selectedTrainNo, setSelectedTrainNo] = useState(null);
  const [journey, setJourney] = useState(null);
  const [selectedStationIdx, setSelectedStationIdx] = useState(0);
  const [loadingTrains, setLoadingTrains] = useState(true);
  const [loadingJourney, setLoadingJourney] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState(null);

  const selectedTrain = trains.find((t) => t.train_no === selectedTrainNo);

  const loadJourney = useCallback(async (trainNo, currentStationCode) => {
    setLoadingJourney(true);
    setError(null);
    try {
      const data = await apiGet(
        `/eta/journey?train_no=${encodeURIComponent(trainNo)}&current_station_code=${encodeURIComponent(currentStationCode)}`
      );
      setJourney(data);
      setSelectedStationIdx(0);
    } catch (e) {
      setError(e.message);
      setJourney(null);
    } finally {
      setLoadingJourney(false);
    }
  }, []);

  // Load train list once on mount
  useEffect(() => {
    (async () => {
      setLoadingTrains(true);
      setError(null);
      try {
        const data = await apiGet("/trains");
        setTrains(data);
        if (data.length > 0) {
          setSelectedTrainNo(data[0].train_no);
        }
      } catch (e) {
        setError(`Could not reach backend at ${API_BASE_URL}. Is uvicorn running? (${e.message})`);
      } finally {
        setLoadingTrains(false);
      }
    })();
  }, []);

  // Load journey whenever the selected train changes
  useEffect(() => {
    if (selectedTrain) {
      loadJourney(selectedTrain.train_no, selectedTrain.current_station_code);
    }
  }, [selectedTrain, loadJourney]);

  const triggerDelayEvent = useCallback(async () => {
    if (!selectedTrain) return;
    setSimulating(true);
    setError(null);
    try {
      await apiPost("/simulate/delay-event", {
        train_no: selectedTrain.train_no,
        station_code: selectedTrain.current_station_code,
        extra_minutes: 15,
      });
      // Re-fetch the journey so the UI reflects the real, freshly
      // recomputed prediction (including a real eta_change block).
      await loadJourney(selectedTrain.train_no, selectedTrain.current_station_code);
    } catch (e) {
      setError(e.message);
    } finally {
      setSimulating(false);
    }
  }, [selectedTrain, loadJourney]);

  const activeStation = journey?.stations?.[selectedStationIdx] ?? null;

  return (
    <div
      style={{
        background: THEME.bg,
        color: THEME.textPrimary,
        fontFamily: FONT_BODY,
        borderRadius: 12,
        padding: 20,
        minHeight: 560,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;500&family=Inter:wght@400;500&display=swap');
        .rp-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .rp-scroll::-webkit-scrollbar-thumb { background: #2A3444; border-radius: 4px; }
        .rp-spin { animation: rp-spin-anim 0.8s linear infinite; }
        @keyframes rp-spin-anim { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Activity size={22} color={THEME.brand} />
          <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 20, letterSpacing: 0.3 }}>
            RailPulse
          </span>
          <span style={{ color: THEME.textFaint, fontSize: 13, marginLeft: 4 }}>Live ETA Control</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: FONT_MONO, fontSize: 13, color: THEME.textMuted }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: error ? THEME.critical : THEME.onTime,
              display: "inline-block",
            }}
          />
          {error ? "OFFLINE" : "LIVE"}
        </div>
      </div>

      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            padding: "10px 14px",
            borderRadius: 8,
            background: "rgba(248,113,113,0.1)",
            border: `1px solid ${THEME.critical}`,
            fontSize: 13,
            color: THEME.critical,
          }}
        >
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>{error}</span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 260px", gap: 16, flex: 1 }}>
        {/* Train list */}
        <div style={{ background: THEME.panel, border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 12 }}>
          <div style={{ fontSize: 11, color: THEME.textFaint, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 10 }}>
            Trains
          </div>

          {loadingTrains ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: THEME.textMuted, fontSize: 13, padding: 8 }}>
              <Loader2 size={14} className="rp-spin" /> Loading...
            </div>
          ) : (
            <div className="rp-scroll" style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 340, overflowY: "auto" }}>
              {trains.map((t) => {
                const isSelected = t.train_no === selectedTrainNo;
                return (
                  <button
                    key={t.train_no}
                    onClick={() => setSelectedTrainNo(t.train_no)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      textAlign: "left",
                      padding: "8px 10px",
                      borderRadius: 8,
                      border: isSelected ? `1px solid ${THEME.brand}` : "1px solid transparent",
                      background: isSelected ? "rgba(76,141,255,0.1)" : "transparent",
                      color: THEME.textPrimary,
                      cursor: "pointer",
                    }}
                  >
                    <Train size={15} color={isSelected ? THEME.brand : THEME.textMuted} />
                    <div>
                      <div style={{ fontFamily: FONT_MONO, fontSize: 13 }}>{t.train_no}</div>
                      <div style={{ fontSize: 11, color: THEME.textMuted }}>
                        Currently at {t.current_station_code}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <button
            onClick={triggerDelayEvent}
            disabled={!selectedTrain || simulating}
            style={{
              marginTop: 16,
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "10px 8px",
              borderRadius: 8,
              border: `1px solid ${THEME.delay}`,
              background: "rgba(245,166,35,0.08)",
              color: THEME.delay,
              fontSize: 12,
              fontWeight: 500,
              cursor: selectedTrain && !simulating ? "pointer" : "not-allowed",
              opacity: selectedTrain && !simulating ? 1 : 0.5,
            }}
          >
            {simulating ? <Loader2 size={14} className="rp-spin" /> : <Zap size={14} />}
            {simulating ? "Sending update..." : "Simulate live delay event"}
          </button>
        </div>

        {/* Route schematic */}
        <div style={{ background: THEME.panel, border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 16, display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 11, color: THEME.textFaint, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 20 }}>
            Route — Train {selectedTrainNo ?? "-"}
          </div>

          {loadingJourney ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: THEME.textMuted, fontSize: 13 }}>
              <Loader2 size={14} className="rp-spin" /> Recalculating ETA...
            </div>
          ) : journey ? (
            <>
              <div className="rp-scroll" style={{ overflowX: "auto", paddingBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", minWidth: journey.stations.length * 130, position: "relative", paddingTop: 30 }}>
                  {journey.stations.map((pred, idx) => {
                    const color = statusColor(pred.predicted_delay_minutes);
                    const isFirst = idx === 0;
                    return (
                      <div key={pred.station.code} style={{ display: "flex", alignItems: "center" }}>
                        <div
                          onClick={() => setSelectedStationIdx(idx)}
                          style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 110, cursor: "pointer", position: "relative" }}
                        >
                          {isFirst && (
                            <div style={{ position: "absolute", top: -26, display: "flex", flexDirection: "column", alignItems: "center" }}>
                              <Train size={16} color={THEME.brand} />
                            </div>
                          )}
                          <div
                            style={{
                              width: 14,
                              height: 14,
                              borderRadius: "50%",
                              background: color,
                              border: `2px solid ${THEME.bg}`,
                              boxShadow: `0 0 0 2px ${idx === selectedStationIdx ? THEME.brand : THEME.panelBorderLight}`,
                            }}
                          />
                          <div style={{ fontSize: 12, fontWeight: 500, marginTop: 8 }}>{pred.station.code}</div>
                          <div style={{ fontFamily: FONT_MONO, fontSize: 11, color, marginTop: 2 }}>
                            +{pred.predicted_delay_minutes.toFixed(1)}m
                          </div>
                        </div>
                        {idx < journey.stations.length - 1 && (
                          <div style={{ width: 40, height: 2, background: THEME.panelBorderLight, marginTop: -20 }} />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {activeStation?.eta_change && (
                <div
                  style={{
                    marginTop: 20,
                    padding: "10px 14px",
                    borderRadius: 8,
                    background: "rgba(245,166,35,0.1)",
                    border: `1px solid ${THEME.delay}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    fontSize: 13,
                  }}
                >
                  <Radio size={15} color={THEME.delay} />
                  <span>
                    ETA updated: <span style={{ fontFamily: FONT_MONO, color: THEME.delay }}>
                      {activeStation.eta_change.previous_predicted_delay_minutes.toFixed(1)}m &rarr; {activeStation.eta_change.new_predicted_delay_minutes.toFixed(1)}m
                    </span>{" "}
                    ({activeStation.eta_change.change_minutes > 0 ? "+" : ""}{activeStation.eta_change.change_minutes.toFixed(1)} min)
                  </span>
                </div>
              )}
            </>
          ) : (
            <div style={{ color: THEME.textFaint, fontSize: 13 }}>No journey data.</div>
          )}
        </div>

        {/* Station detail panel */}
        <div style={{ background: THEME.panel, border: `1px solid ${THEME.panelBorder}`, borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 11, color: THEME.textFaint, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 14 }}>
            Station detail
          </div>

          {activeStation ? (
            <>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
                <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 18 }}>{activeStation.station.code}</span>
                <span style={{ fontSize: 12, color: THEME.textMuted }}>{activeStation.station.name}</span>
              </div>

              <div style={{ display: "flex", gap: 16, margin: "14px 0" }}>
                <div>
                  <div style={{ fontSize: 11, color: THEME.textFaint }}>Predicted ETA</div>
                  <div style={{ fontFamily: FONT_MONO, fontSize: 18, color: statusColor(activeStation.predicted_delay_minutes) }}>
                    {formatTime(activeStation.predicted_eta)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: THEME.textFaint }}>Delay</div>
                  <div style={{ fontFamily: FONT_MONO, fontSize: 18 }}>
                    +{activeStation.predicted_delay_minutes.toFixed(1)}m
                  </div>
                </div>
              </div>

              <div style={{ fontSize: 11, color: THEME.textFaint, display: "flex", alignItems: "center", gap: 4, marginBottom: 12 }}>
                <Clock size={12} />
                Scheduled: {formatTime(activeStation.scheduled_time)}
              </div>

              <div
                style={{
                  fontSize: 12,
                  color: THEME.textMuted,
                  padding: "8px 10px",
                  background: "rgba(255,255,255,0.03)",
                  borderRadius: 6,
                  marginBottom: 14,
                }}
              >
                {activeStation.explanation}
              </div>

              <div style={{ fontSize: 11, color: THEME.textFaint, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>
                Delay contributions
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={activeStation.contributions} layout="vertical" margin={{ left: 0, right: 10 }}>
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="factor"
                    width={110}
                    tick={{ fill: THEME.textMuted, fontSize: 10 }}
                    tickFormatter={(v) => v.replace(/_/g, " ")}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{ background: THEME.panel, border: `1px solid ${THEME.panelBorderLight}`, fontSize: 12 }}
                    labelFormatter={(v) => v.replace(/_/g, " ")}
                    formatter={(v) => [`${v} min`, ""]}
                  />
                  <Bar dataKey="minutes" radius={[0, 4, 4, 0]}>
                    {activeStation.contributions.map((c, i) => (
                      <Cell key={i} fill={c.minutes > 5 ? THEME.delay : THEME.brand} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </>
          ) : (
            <div style={{ color: THEME.textFaint, fontSize: 13 }}>Select a station on the route to view details.</div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 16, fontSize: 11, color: THEME.textFaint }}>
            <CloudRain size={12} />
            Live from FastAPI backend
            <ChevronRight size={12} />
          </div>
        </div>
      </div>
    </div>
  );
}
