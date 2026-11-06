const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export function formatMoney(value: number) {
  return currency.format(value);
}

export function formatDuration(value: number | null) {
  if (value == null) return '—';
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} s`;
}

export function formatTime(value: number) {
  return new Date(value).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function getServiceAddress(value: string) {
  try {
    return new URL(value).host;
  } catch {
    return value;
  }
}
