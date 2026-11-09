import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StrictMode } from 'react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../src/App';
import * as gateway from '../src/api/gateway';
import { saveRun } from '../src/lib/storage';
import { confirmedResponse, deferred, healthyReport, scenarios } from './fixtures';

vi.mock('../src/api/gateway', async (importOriginal) => {
  const actual = await importOriginal<typeof gateway>();
  return {
    ...actual,
    getScenarios: vi.fn(),
    getHealth: vi.fn(),
    createBooking: vi.fn(),
  };
});

function renderApp(path = '/checkout') {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </StrictMode>,
  );
}

async function openCheckout() {
  renderApp();
  return screen.findByRole('button', { name: /Confirm & Pay/ });
}

beforeEach(() => {
  vi.mocked(gateway.getScenarios).mockResolvedValue(scenarios);
  vi.mocked(gateway.getHealth).mockResolvedValue(healthyReport);
  vi.mocked(gateway.createBooking).mockResolvedValue(confirmedResponse);
});

describe('booking sandbox', () => {
  it('loads gateway scenarios and updates flight, hotel and total when selected', async () => {
    await openCheckout();
    const user = userEvent.setup();
    await user.click(screen.getByRole('radio', { name: /Payment decline/ }));

    expect(screen.getByRole('button', { name: /Confirm & Pay.*2,500/ })).toBeEnabled();
    expect(screen.getByText('KLM-401')).toBeVisible();
    expect(screen.getByText('Luxury Resort & Spa')).toBeVisible();
    expect(localStorage.getItem('layover.ui.scenario.v1')).toBe('fail_payment');
  });

  it('shows deliberate hotel fault values instead of silently fixing the scenario', async () => {
    await openCheckout();
    await userEvent.click(screen.getByRole('radio', { name: /Hotel rejection/ }));

    expect(screen.getByRole('button', { name: /Confirm & Pay.*299/ })).toBeEnabled();
    expect(screen.getByText('INVALID_HOTEL_OVERBOOKED')).toBeVisible();
    expect(screen.getByText(/Negative hotel price/)).toBeVisible();
  });

  it('enables both engines and defaults to Temporal', async () => {
    await openCheckout();

    expect(screen.getByRole('radio', { name: /In-memory/ })).toBeEnabled();
    expect(screen.getByRole('radio', { name: /Happy path/ })).toBeEnabled();
    expect(screen.getByRole('radio', { name: /Temporal/ })).toBeChecked();
  });

  it('shows actual health status and probe latency, with an explicit refresh', async () => {
    vi.mocked(gateway.getHealth).mockResolvedValue({
      ...healthyReport,
      overall_status: 'DEGRADED',
      services: healthyReport.services.map((service) =>
        service.name === 'Hotel Service'
          ? { ...service, status: 'DOWN', error: 'Connection refused' }
          : service,
      ),
    });
    await openCheckout();
    await userEvent.click(await screen.findByRole('button', { name: /3\/4 healthy/ }));

    expect(screen.getByText('Connection refused')).toBeVisible();
    expect(screen.getByText(/12.4 ms/)).toBeVisible();
    const count = vi.mocked(gateway.getHealth).mock.calls.length;
    await userEvent.click(screen.getByRole('button', { name: /Refresh health/ }));
    await waitFor(() => expect(gateway.getHealth).toHaveBeenCalledTimes(count + 1));
  });

  it('does not leave fabricated healthy indicators when the gateway is unreachable', async () => {
    vi.mocked(gateway.getHealth).mockRejectedValue(new Error('Gateway offline'));
    await openCheckout();

    await userEvent.click(await screen.findByRole('button', { name: /Health unavailable/ }));
    expect(screen.getByText(/Gateway offline/)).toBeVisible();
    expect(screen.queryByText('4/4 healthy')).not.toBeInTheDocument();
  });

  it('renders a recoverable scenario-loading error and does not submit without metadata', async () => {
    vi.mocked(gateway.getScenarios).mockRejectedValue(new Error('Gateway offline'));
    renderApp();

    expect(await screen.findByRole('alert')).toHaveTextContent('Gateway offline');
    expect(gateway.createBooking).not.toHaveBeenCalled();
    vi.mocked(gateway.getScenarios).mockResolvedValue(scenarios);
    await userEvent.click(screen.getByRole('button', { name: /Retry scenarios/ }));
    expect(await screen.findByRole('button', { name: /Confirm & Pay/ })).toBeEnabled();
  });

  it('submits exactly once on rapid clicks, including StrictMode, without demo card fields', async () => {
    const pending = deferred<typeof confirmedResponse>();
    vi.mocked(gateway.createBooking).mockReturnValue(pending.promise);
    const button = await openCheckout();
    fireEvent.click(button);
    fireEvent.click(button);

    expect(gateway.createBooking).toHaveBeenCalledTimes(1);
    const request = vi.mocked(gateway.createBooking).mock.calls[0]![0];
    expect(request).toEqual({
      booking_id: expect.stringMatching(/^bk-/),
      orchestrator: 'temporal',
      scenario: 'happy_path',
      customer_id: 'user_1',
      flight_number: 'LH-204',
      flight_price: 250,
      hotel_name: 'Grand Palace Hotel',
      hotel_price: 150,
    });
    expect(screen.getByText('Awaiting gateway result')).toBeVisible();
    expect(screen.queryByText('48 ms')).not.toBeInTheDocument();
    await act(async () =>
      pending.resolve({ ...confirmedResponse, booking_id: request.booking_id! }),
    );
  });

  it('shows all returned confirmation steps and the actual workflow URL', async () => {
    const button = await openCheckout();
    await userEvent.click(button);

    expect(await screen.findByRole('heading', { name: 'Layover confirmed' })).toBeVisible();
    const log = screen.getByRole('region', { name: 'Execution summary' });
    expect(within(log).getByText('Confirm flight')).toBeVisible();
    expect(within(log).getByText('Confirm hotel')).toBeVisible();
    expect(screen.getByRole('link', { name: /Open in Temporal Web UI/ })).toHaveAttribute(
      'href',
      confirmedResponse.temporal_ui_url,
    );
    expect(screen.getByRole('button', { name: /Download booking summary/ })).toBeEnabled();
    expect(screen.queryByText(/Receipt issued/)).not.toBeInTheDocument();
  });

  it('uses returned compensation ordering and does not claim every hold was released', async () => {
    vi.mocked(gateway.createBooking).mockResolvedValue({
      ...confirmedResponse,
      status: 'COMPENSATED',
      steps_completed: ['reserve_flight', 'reserve_hotel'],
      compensations_executed: ['cancel_hotel', 'cancel_flight'],
      error_message: 'Insufficient funds',
    });
    await userEvent.click(await openCheckout());

    expect(await screen.findByRole('heading', { name: 'Booking rolled back' })).toBeVisible();
    const log = screen.getByRole('region', { name: 'Execution summary' });
    const rows = within(log).getAllByRole('listitem');
    expect(rows.at(-2)).toHaveTextContent('Cancel hotel');
    expect(rows.at(-1)).toHaveTextContent('Cancel flight');
    expect(screen.getByText('Insufficient funds')).toBeVisible();
  });

  it('treats a gateway FAILED response as a workflow result, not a transport error', async () => {
    vi.mocked(gateway.createBooking).mockResolvedValue({
      ...confirmedResponse,
      status: 'FAILED',
      steps_completed: [],
      error_message: 'Temporal submission error: cluster unavailable',
    });
    await userEvent.click(await openCheckout());

    expect(await screen.findByRole('heading', { name: 'Booking failed' })).toBeVisible();
    expect(screen.getByText(/cluster unavailable/)).toBeVisible();
    expect(screen.queryByText('Layover confirmed')).not.toBeInTheDocument();
  });

  it('shows outcome unknown on a disconnected request and never silently retries', async () => {
    vi.mocked(gateway.createBooking).mockRejectedValue(new Error('Network disconnected'));
    await userEvent.click(await openCheckout());

    expect(await screen.findByRole('heading', { name: 'Booking outcome unknown' })).toBeVisible();
    expect(screen.getByText(/may still be running/)).toBeVisible();
    expect(gateway.createBooking).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: /Retry booking/ })).not.toBeInTheDocument();
  });

  it('does not dispatch a booking when opening a result URL directly', async () => {
    renderApp('/processing/bk-missing');

    expect(await screen.findByRole('heading', { name: 'No saved booking result' })).toBeVisible();
    expect(gateway.createBooking).not.toHaveBeenCalled();
    expect(screen.queryByRole('link', { name: /Temporal/ })).not.toBeInTheDocument();
  });

  it('restores a pending run as unknown after refresh without resubmitting', async () => {
    saveRun({
      phase: 'pending',
      request: { booking_id: 'bk-refresh', orchestrator: 'temporal', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
    });
    renderApp('/processing/bk-refresh');

    expect(await screen.findByRole('heading', { name: 'Booking outcome unknown' })).toBeVisible();
    expect(gateway.createBooking).not.toHaveBeenCalled();
  });

  it('keeps unknown-outcome acknowledgment visible, focused and reversible without submitting', async () => {
    saveRun({
      phase: 'pending',
      request: { booking_id: 'bk-unknown', orchestrator: 'temporal', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
    });
    const payButton = await openCheckout();
    const acknowledgment = screen.getByRole('checkbox', {
      name: /I checked the previous workflow/,
    });
    expect(payButton).toBeDisabled();

    await userEvent.click(acknowledgment);
    expect(screen.getByRole('checkbox', { name: /I checked the previous workflow/ })).toBeChecked();
    expect(acknowledgment).toHaveFocus();
    expect(payButton).toBeEnabled();
    expect(gateway.createBooking).not.toHaveBeenCalled();

    await userEvent.click(acknowledgment);
    expect(acknowledgment).not.toBeChecked();
    expect(payButton).toBeDisabled();
  });

  it('restores a final result after refresh without another booking', async () => {
    saveRun({
      phase: 'result',
      request: { booking_id: 'bk-test', orchestrator: 'temporal', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
      durationMs: 140,
      response: confirmedResponse,
    });
    renderApp('/processing/bk-test');

    expect(await screen.findByRole('heading', { name: 'Layover confirmed' })).toBeVisible();
    expect(gateway.createBooking).not.toHaveBeenCalled();
  });

  it('keeps the pending request alive when navigating back to checkout', async () => {
    const pending = deferred<typeof confirmedResponse>();
    vi.mocked(gateway.createBooking).mockReturnValue(pending.promise);
    await userEvent.click(await openCheckout());
    await userEvent.click(screen.getByRole('link', { name: /Back to checkout/ }));

    expect(screen.getByRole('button', { name: /Booking in progress/ })).toBeDisabled();
    expect(screen.getByRole('link', { name: /View active booking/ })).toBeVisible();
    expect(gateway.createBooking).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(confirmedResponse));
  });

  it('resets scroll and focuses the new heading on navigation without stealing focus on result updates', async () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    const pending = deferred<typeof confirmedResponse>();
    vi.mocked(gateway.createBooking).mockReturnValue(pending.promise);
    await userEvent.click(await openCheckout());

    expect(screen.getByRole('heading', { name: 'Reserving your layover' })).toHaveFocus();
    expect(scrollTo).toHaveBeenCalledWith(0, 0);

    const copyButton = screen.getByRole('button', { name: 'Copy booking ID' });
    copyButton.focus();
    const scrollCount = scrollTo.mock.calls.length;
    await act(async () => pending.resolve(confirmedResponse));
    expect(copyButton).toHaveFocus();
    expect(scrollTo).toHaveBeenCalledTimes(scrollCount);

    await userEvent.click(screen.getByRole('link', { name: 'Back to checkout' }));
    expect(screen.getByRole('heading', { name: /Frankfurt to Amsterdam/ })).toHaveFocus();
    expect(scrollTo).toHaveBeenCalledTimes(scrollCount + 1);
  });

  it('submits the selected naive engine and shows its labels without a Temporal link', async () => {
    vi.mocked(gateway.createBooking).mockResolvedValue({
      ...confirmedResponse,
      orchestrator: 'naive',
      temporal_ui_url: null,
    });
    const button = await openCheckout();
    await userEvent.click(screen.getByRole('radio', { name: /In-memory/ }));
    expect(screen.getByRole('radio', { name: /Temporal/ })).not.toBeChecked();
    await userEvent.click(button);

    expect(await screen.findByRole('heading', { name: 'Layover confirmed' })).toBeVisible();
    expect(gateway.createBooking).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        orchestrator: 'naive',
        scenario: 'happy_path',
      }),
    );
    expect(screen.getByText('In-memory')).toBeVisible();
    expect(screen.getByRole('region', { name: 'Booking service topology' })).toHaveTextContent(
      'Engine: In-memory (baseline)',
    );
    expect(screen.getByText(/No durable history or automatic restart recovery/)).toBeVisible();
    expect(screen.queryByRole('link', { name: /Temporal/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Open Temporal for the full history/)).not.toBeInTheDocument();
  });

  it('keeps engine switching disabled during a naive request and preserves the submitted snapshot', async () => {
    const pending = deferred<typeof confirmedResponse>();
    vi.mocked(gateway.createBooking).mockReturnValue(pending.promise);
    const button = await openCheckout();
    await userEvent.click(screen.getByRole('radio', { name: /In-memory/ }));
    await userEvent.click(button);

    expect(screen.getByText('In-memory Saga')).toBeVisible();
    expect(screen.queryByText(/worker is offline/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: /Back to checkout/ }));
    expect(screen.getByRole('radio', { name: /In-memory/ })).toBeDisabled();
    expect(screen.getByRole('radio', { name: /Temporal/ })).toBeDisabled();
    expect(screen.getByRole('radio', { name: /In-memory/ })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: /Temporal/ }));
    expect(gateway.createBooking).toHaveBeenCalledTimes(1);
    expect(JSON.parse(sessionStorage.getItem('layover.ui.run.v1')!).request.orchestrator).toBe(
      'naive',
    );

    const request = vi.mocked(gateway.createBooking).mock.calls[0]![0];
    await act(async () =>
      pending.resolve({
        ...confirmedResponse,
        booking_id: request.booking_id!,
        orchestrator: 'naive',
      }),
    );
    await userEvent.click(screen.getByRole('radio', { name: /Temporal/ }));
    await userEvent.click(screen.getByRole('link', { name: /View last booking/ }));
    expect(screen.getByText('In-memory')).toBeVisible();
    // Even an unexpected Temporal URL in a naive response must not create an inspection link.
    expect(screen.queryByRole('link', { name: /Temporal/ })).not.toBeInTheDocument();
  });

  it.each([
    {
      status: 'COMPENSATED',
      title: 'Booking rolled back',
      compensations: ['cancel_hotel', 'cancel_flight'],
    },
    { status: 'FAILED', title: 'Booking failed', compensations: ['cancel_hotel'] },
  ])(
    'renders naive $status using only reported compensations',
    async ({ status, title, compensations }) => {
      vi.mocked(gateway.createBooking).mockResolvedValue({
        ...confirmedResponse,
        orchestrator: 'naive',
        temporal_ui_url: null,
        status,
        steps_completed: ['reserve_flight', 'reserve_hotel'],
        compensations_executed: compensations,
        error_message:
          status === 'FAILED'
            ? 'cancel_flight failed; reconciliation required'
            : 'Payment declined',
      });
      const button = await openCheckout();
      await userEvent.click(screen.getByRole('radio', { name: /In-memory/ }));
      await userEvent.click(button);

      expect(await screen.findByRole('heading', { name: title })).toBeVisible();
      expect(screen.queryByRole('link', { name: /Temporal/ })).not.toBeInTheDocument();
      const rows = within(
        screen.getByRole('list', { name: 'Executed compensations' }),
      ).getAllByRole('listitem');
      expect(rows).toHaveLength(compensations.length);
    },
  );

  it('reports a disconnected naive run without suggesting durable workflow recovery', async () => {
    vi.mocked(gateway.createBooking).mockRejectedValue(new Error('Network disconnected'));
    const button = await openCheckout();
    await userEvent.click(screen.getByRole('radio', { name: /In-memory/ }));
    await userEvent.click(button);

    expect(await screen.findByRole('heading', { name: 'Booking outcome unknown' })).toBeVisible();
    expect(
      screen.getByText(/in-memory Saga may still be running.*does not recover automatically/i),
    ).toBeVisible();
    expect(screen.queryByRole('link', { name: /Temporal/ })).not.toBeInTheDocument();
    expect(gateway.createBooking).toHaveBeenCalledTimes(1);
  });

  it('restores a refreshed naive run without resubmission or a misleading Temporal link', async () => {
    saveRun({
      phase: 'pending',
      request: { booking_id: 'bk-naive-refresh', orchestrator: 'naive', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
    });
    renderApp('/processing/bk-naive-refresh');

    expect(await screen.findByRole('heading', { name: 'Booking outcome unknown' })).toBeVisible();
    expect(screen.getByText(/does not recover automatically/)).toBeVisible();
    expect(screen.queryByRole('link', { name: /Temporal/ })).not.toBeInTheDocument();
    expect(gateway.createBooking).not.toHaveBeenCalled();
  });
});
