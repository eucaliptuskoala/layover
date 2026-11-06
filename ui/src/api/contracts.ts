export type ScenarioKey = 'happy_path' | 'fail_payment' | 'fail_hotel' | 'custom';
export type Orchestrator = 'temporal' | 'naive';

export interface Scenario {
  key: string;
  name: string;
  description: string;
  customer_id: string;
  flight_number: string;
  flight_price: number;
  hotel_name: string;
  hotel_price: number;
  expected_total: number;
}

export interface BookingRequest {
  orchestrator: Orchestrator;
  scenario: ScenarioKey;
  booking_id?: string;
  customer_id?: string;
  flight_number?: string;
  flight_price?: number;
  hotel_name?: string;
  hotel_price?: number;
}

export interface BookingResponse {
  booking_id: string;
  orchestrator: string;
  scenario: string;
  status: string;
  total_amount: number;
  steps_completed: string[];
  compensations_executed: string[];
  error_message?: string | null;
  temporal_ui_url?: string | null;
}

export interface ServiceHealth {
  name: string;
  url: string;
  status: string;
  latency_ms?: number | null;
  error?: string | null;
}

export interface HealthReport {
  overall_status: string;
  services: ServiceHealth[];
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isOptionalString(value: unknown) {
  return value == null || typeof value === 'string';
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function isScenarioKey(value: unknown): value is ScenarioKey {
  return ['happy_path', 'fail_payment', 'fail_hotel', 'custom'].includes(String(value));
}

export function isScenario(value: unknown): value is Scenario {
  return (
    isRecord(value) &&
    ['key', 'name', 'description', 'customer_id', 'flight_number', 'hotel_name'].every(
      (key) => typeof value[key] === 'string',
    ) &&
    ['flight_price', 'hotel_price', 'expected_total'].every((key) => isNumber(value[key]))
  );
}

export function isBookingResponse(value: unknown): value is BookingResponse {
  return (
    isRecord(value) &&
    ['booking_id', 'orchestrator', 'scenario', 'status'].every(
      (key) => typeof value[key] === 'string',
    ) &&
    isNumber(value.total_amount) &&
    isStringArray(value.steps_completed) &&
    isStringArray(value.compensations_executed) &&
    isOptionalString(value.error_message) &&
    isOptionalString(value.temporal_ui_url)
  );
}

export function isHealthReport(value: unknown): value is HealthReport {
  return (
    isRecord(value) &&
    typeof value.overall_status === 'string' &&
    Array.isArray(value.services) &&
    value.services.every(
      (service: unknown) =>
        isRecord(service) &&
        ['name', 'url', 'status'].every((key) => typeof service[key] === 'string') &&
        (service.latency_ms == null || isNumber(service.latency_ms)) &&
        isOptionalString(service.error),
    )
  );
}
