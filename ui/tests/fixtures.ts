export const scenarios = [
  {
    key: 'happy_path',
    name: 'Happy Path',
    description: 'Valid reservation within the test account balance. Expects CONFIRMED.',
    customer_id: 'user_1',
    flight_number: 'LH-204',
    flight_price: 250,
    hotel_name: 'Grand Palace Hotel',
    hotel_price: 150,
    expected_total: 400,
  },
  {
    key: 'fail_payment',
    name: 'Fail Payment',
    description: 'Exceeds account balance. Payment rejects and triggers LIFO rollback.',
    customer_id: 'user_1',
    flight_number: 'KLM-401',
    flight_price: 1200,
    hotel_name: 'Luxury Resort & Spa',
    hotel_price: 1300,
    expected_total: 2500,
  },
  {
    key: 'fail_hotel',
    name: 'Fail Hotel',
    description: 'Negative hotel price triggers HTTP 422 and flight cancellation.',
    customer_id: 'user_1',
    flight_number: 'AF-310',
    flight_price: 300,
    hotel_name: 'INVALID_HOTEL_OVERBOOKED',
    hotel_price: -1,
    expected_total: 299,
  },
];

export const healthyReport = {
  overall_status: 'HEALTHY',
  services: [
    {
      name: 'Flight Service',
      url: 'http://localhost:8001',
      status: 'UP',
      latency_ms: 12.4,
      error: null,
    },
    {
      name: 'Hotel Service',
      url: 'http://localhost:8002',
      status: 'UP',
      latency_ms: 15.1,
      error: null,
    },
    {
      name: 'Payment Service',
      url: 'http://localhost:8003',
      status: 'UP',
      latency_ms: 18,
      error: null,
    },
    {
      name: 'Temporal Engine',
      url: 'grpc://localhost:7233',
      status: 'UP',
      latency_ms: 5.2,
      error: null,
    },
  ],
};

export const confirmedResponse = {
  booking_id: 'bk-test',
  orchestrator: 'temporal',
  scenario: 'happy_path',
  status: 'CONFIRMED',
  total_amount: 400,
  steps_completed: [
    'reserve_flight',
    'reserve_hotel',
    'charge_payment',
    'confirm_flight',
    'confirm_hotel',
  ],
  compensations_executed: [],
  error_message: null,
  temporal_ui_url: 'http://localhost:8233/namespaces/layover/workflows/bk-test',
};

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}
