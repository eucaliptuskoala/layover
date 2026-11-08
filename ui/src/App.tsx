import { useState } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router';

import type { Orchestrator, Scenario, ScenarioKey } from './api/contracts';
import { getHealth, getScenarios } from './api/gateway';
import { Toast } from './components/Toast';
import { useBooking } from './hooks/useBooking';
import { useResource } from './hooks/useResource';
import { useRouteFocus } from './hooks/useRouteFocus';
import { useToast } from './hooks/useToast';
import { readScenario, saveScenario } from './lib/storage';
import { CheckoutPage } from './pages/CheckoutPage';
import { ProcessingPage } from './pages/ProcessingPage';

export default function App() {
  const [selectedKey, setSelectedKey] = useState<ScenarioKey>(readScenario);
  const scenarios = useResource(getScenarios);
  const health = useResource(getHealth);
  const { run, startBooking } = useBooking();
  const [selectedOrchestrator, setSelectedOrchestrator] = useState<Orchestrator>(
    run?.request.orchestrator ?? 'temporal',
  );
  const { message, notify } = useToast();
  const navigate = useNavigate();
  useRouteFocus();

  function selectScenario(key: ScenarioKey) {
    setSelectedKey(key);
    saveScenario(key);
  }

  function submit(scenario: Scenario) {
    const bookingId = startBooking(scenario, selectedOrchestrator);
    if (bookingId) void navigate(`/processing/${encodeURIComponent(bookingId)}`);
  }

  return (
    <>
      <Routes>
        <Route
          path="/checkout"
          element={
            <CheckoutPage
              scenarios={scenarios}
              selectedKey={selectedKey}
              onSelect={selectScenario}
              selectedOrchestrator={selectedOrchestrator}
              onSelectOrchestrator={setSelectedOrchestrator}
              health={health}
              run={run}
              onSubmit={submit}
              notify={notify}
            />
          }
        />
        <Route
          path="/processing/:bookingId"
          element={
            <ProcessingPage
              run={run}
              health={health.status === 'success' ? health.data : null}
              notify={notify}
            />
          }
        />
        <Route path="*" element={<Navigate to="/checkout" replace />} />
      </Routes>
      <Toast message={message} />
    </>
  );
}
