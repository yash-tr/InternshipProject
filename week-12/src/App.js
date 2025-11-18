import "./index.css";
import { ToastContainer } from "./components/ToastContainer";
import { JobTagsPanel } from "./components/JobTagsPanel";
import { ClickOptimizationPanel } from "./components/ClickOptimizationPanel";
import { CareerMisconductAdmin } from "./components/CareerMisconductAdmin";
import { JobHighlightsPanel } from "./components/JobHighlightsPanel";

function App() {
  return (
    <>
      <header className="page-header">
        <div>
          <h1>Week 12 Control Center</h1>
          <p>
            Monitor rollout health, enforce policies, and accelerate job discovery.
          </p>
        </div>
      </header>

      <main className="grid">
        <JobTagsPanel />
        <ClickOptimizationPanel />
        <CareerMisconductAdmin />
        <JobHighlightsPanel />
      </main>

      <ToastContainer />
    </>
  );
}

export default App;

