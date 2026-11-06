import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { PriceSummary } from '../src/components/PriceSummary';
import { scenarios } from './fixtures';

function renderSummary() {
  const onSubmit = vi.fn();
  const notify = vi.fn();
  render(
    <PriceSummary
      scenario={scenarios[0]!}
      isPending={false}
      isDisabled={false}
      onSubmit={onSubmit}
      notify={notify}
    />,
  );
  return { onSubmit, notify };
}

describe('demo payment picker', () => {
  it('returns keyboard focus to Change after selecting a display-only card', async () => {
    const { onSubmit, notify } = renderSummary();
    const user = userEvent.setup();
    const changeButton = screen.getByRole('button', { name: 'Change' });
    await user.click(changeButton);
    screen.getByRole('radio', { name: /Visa/ }).focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByText(/Amex ···· 1009/)).toBeVisible();
    expect(screen.queryByRole('group', { name: 'Demo payment methods' })).not.toBeInTheDocument();
    expect(changeButton).toHaveFocus();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith(
      'Amex selected for display. Bookings use the test account balance.',
    );
  });

  it.each(['trigger', 'radio'])('dismisses the picker with Escape from the %s', async (target) => {
    renderSummary();
    const user = userEvent.setup();
    const changeButton = screen.getByRole('button', { name: 'Change' });
    await user.click(changeButton);
    if (target === 'radio') screen.getByRole('radio', { name: /Visa/ }).focus();
    await user.keyboard('{Escape}');

    expect(changeButton).toHaveAttribute('aria-expanded', 'false');
    expect(changeButton).toHaveFocus();
  });
});
