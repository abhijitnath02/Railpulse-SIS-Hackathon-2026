import React from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  MapPinned,
  TrainFront,
  Siren,
  ChartNoAxesColumnIncreasing,
  FileBarChart,
  Settings,
  Bell,
  CircleUserRound,
  MapPin,
  Minus,
  Plus,
  Navigation,
  AlertTriangle,
  Clock3,
  ChevronRight,
} from "lucide-react";
import "./styles.css";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "Live Map", icon: MapPinned },
  { label: "Trains", icon: TrainFront },
  { label: "Alert", icon: Siren },
  { label: "Analytics", icon: ChartNoAxesColumnIncreasing },
  { label: "Reports", icon: FileBarChart },
  { label: "Settings", icon: Settings },
];

const stats = [
  { label: "Active Trains", value: "128", icon: TrainFront, tone: "cyan" },
  { label: "On Time", value: "72", icon: Clock3, tone: "green" },
  { label: "Delayed time", value: "56", icon: Clock3, tone: "yellow" },
  { label: "Alerts", value: "7", icon: AlertTriangle, tone: "red" },
];

const stations = [
  ["New Jalpaiguri (NJP)", "08:45 PM", "08:52 PM", "+7 min"],
  ["Alipurduar (APDJ)", "09:37 PM", "09:46 PM", "+9 min"],
  ["Kishanganj (KIR)", "10:20 PM", "10:38 PM", "+18 min"],
  ["New Bongaigaon (NBQ)", "11:05 PM", "11:20 PM", "+15 min"],
  ["Guwahati (GHY)", "01:15 AM", "01:25 AM", "+10 min"],
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        Rail<span>Pulse</span>
      </div>

      <nav className="nav">
        {navItems.map(({ label, icon: Icon, active }) => (
          <button key={label} className={`nav-item ${active ? "active" : ""}`}>
            <Icon size={24} strokeWidth={2.2} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}

function StatCard({ label, value, icon: Icon, tone }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${tone}`}>
        <Icon size={45} strokeWidth={2.2} />
      </div>
      <div className="stat-copy">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
      </div>
    </div>
  );
}

function RouteMap() {
  return (
    <section className="map-card">
      <div className="panel-heading">
        <span>Live Train Tracking</span>
        <button className="small-button">View Full Map</button>
      </div>

      <div className="map">
        <div className="map-noise" />

        <div className="map-city siliguri">Siliguri</div>
        <div className="map-city patna">Patna</div>
        <div className="map-city ranchi">Ranchi</div>
        <div className="map-city kolkata">Kolkata</div>
        <div className="map-city guwahati">Guwahati</div>

        <div className="route route-green" />
        <div className="route route-orange" />

        <div className="station-dot p1" />
        <div className="station-dot p2" />
        <div className="station-dot p3 orange" />
        <div className="station-dot p4 orange" />
        <div className="station-dot p5 orange" />
        <div className="station-dot p6 orange" />
        <div className="station-dot p7 orange" />
        <div className="station-dot p8 orange" />

        <div className="train-marker">
          <TrainFront size={17} />
        </div>

        <div className="route-popup">
          <strong>12000 - NDLS TO DIBRUGARH</strong>
          <span>Speed: 62 kmph</span>
          <span>Delay: <b>+18 min</b></span>
          <span>Next Station: Kishanganj (KIR)</span>
          <span>ETA: <em>10:45 PM</em></span>
        </div>

        <div className="map-controls">
          <button><Plus size={15} /></button>
          <button><Minus size={15} /></button>
        </div>
      </div>
    </section>
  );
}

function StationTable() {
  return (
    <section className="station-card">
      <div className="panel-heading">
        <span>Upcoming Stations &amp; ETA</span>
      </div>

      <div className="table-wrap">
        <div className="table-row table-head">
          <span>Station</span>
          <span>Scheduled</span>
          <span>Predicted ETA</span>
          <span>Delay</span>
        </div>

        {stations.map(([station, scheduled, eta, delay]) => (
          <div className="table-row" key={station}>
            <span>{station}</span>
            <span>{scheduled}</span>
            <span>{eta}</span>
            <span className="delay">{delay}</span>
          </div>
        ))}
      </div>

      <button className="route-button">
        View Full Route <ChevronRight size={13} />
      </button>
    </section>
  );
}

function App() {
  return (
    <div className="app-shell">
      <Sidebar />

      <main className="main">
        <header className="topbar">
          <h1>Dashboard</h1>
          <div className="top-actions">
            <button className="circle-action"><Bell size={24} fill="white" /></button>
            <button className="circle-action"><Settings size={25} fill="white" /></button>
            <button className="avatar"><CircleUserRound size={25} /></button>
          </div>
        </header>

        <section className="stats-grid">
          {stats.map((stat) => <StatCard key={stat.label} {...stat} />)}
        </section>

        <section className="content-grid">
          <RouteMap />
          <StationTable />
        </section>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
