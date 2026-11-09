import { useEffect, useRef, useState } from 'react';

import type { BookingResponse } from '../api/contracts';

export type NodeVisualState = 'idle' | 'running' | 'ok' | 'err' | 'unwinding' | 'cancel' | 'skip';

export interface NodePlaybackState {
  state: NodeVisualState;
  badge: string;
  sub: string;
}

export interface LinkPlaybackState {
  isLive: boolean;
  isReverse: boolean;
}

export interface TopologyPlayback {
  nodes: {
    flight: NodePlaybackState;
    hotel: NodePlaybackState;
    payment: NodePlaybackState;
  };
  links: [LinkPlaybackState, LinkPlaybackState];
  isComplete: boolean;
}

const DEFAULT_NODES: TopologyPlayback['nodes'] = {
  flight: { state: 'idle', badge: 'idle', sub: 'reserve · confirm · cancel' },
  hotel: { state: 'idle', badge: 'idle', sub: 'reserve · confirm · cancel' },
  payment: { state: 'idle', badge: 'idle', sub: 'charge · refund' },
};

const DEFAULT_LINKS: [LinkPlaybackState, LinkPlaybackState] = [
  { isLive: false, isReverse: false },
  { isLive: false, isReverse: false },
];

export function useTopologyPlayback({
  response,
  isPending,
  isHistorical = false,
}: {
  response: BookingResponse | null;
  isPending: boolean;
  isHistorical?: boolean;
}): TopologyPlayback {
  const [playbackState, setPlaybackState] = useState<TopologyPlayback>({
    nodes: DEFAULT_NODES,
    links: DEFAULT_LINKS,
    isComplete: !isPending && !!response,
  });

  const timerRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  function clearTimers() {
    timerRef.current.forEach(clearTimeout);
    timerRef.current = [];
  }

  useEffect(() => {
    clearTimers();

    // Case 1: In-flight without response yet (e.g. slow_demo or real network latency)
    if (isPending && !response) {
      setPlaybackState({
        nodes: {
          flight: { state: 'running', badge: 'dispatching', sub: 'reserving seat...' },
          hotel: { state: 'idle', badge: 'queued', sub: 'awaiting upstream' },
          payment: { state: 'idle', badge: 'queued', sub: 'awaiting upstream' },
        },
        links: [
          { isLive: true, isReverse: false },
          { isLive: false, isReverse: false },
        ],
        isComplete: false,
      });
      return;
    }

    // Case 2: No response and not pending
    if (!response) {
      setPlaybackState({
        nodes: DEFAULT_NODES,
        links: DEFAULT_LINKS,
        isComplete: false,
      });
      return;
    }

    // Determine final target states from response
    const hasFlightReserved = response.steps_completed.includes('reserve_flight');
    const hasHotelReserved = response.steps_completed.includes('reserve_hotel');
    const hasPaymentCharged = response.steps_completed.includes('charge_payment');
    const isFlightCancelled = response.compensations_executed.includes('cancel_flight');
    const isHotelCancelled = response.compensations_executed.includes('cancel_hotel');
    const isConfirmed = response.status === 'CONFIRMED';
    const isCompensated = response.status === 'COMPENSATED';
    const isFailed = response.status === 'FAILED';

    const finalFlightState: NodePlaybackState = isFlightCancelled
      ? { state: 'cancel', badge: 'CANCELLED', sub: 'seat hold released' }
      : isConfirmed
        ? { state: 'ok', badge: 'CONFIRMED', sub: 'seat 12A confirmed' }
        : hasFlightReserved
          ? { state: 'ok', badge: 'RESERVED', sub: 'seat held' }
          : { state: 'idle', badge: 'unreported', sub: 'not attempted' };

    const finalHotelState: NodePlaybackState = isHotelCancelled
      ? { state: 'cancel', badge: 'CANCELLED', sub: 'room hold released' }
      : isConfirmed
        ? { state: 'ok', badge: 'CONFIRMED', sub: 'room confirmed' }
        : hasHotelReserved
          ? { state: 'ok', badge: 'RESERVED', sub: 'room held' }
          : isCompensated && !hasHotelReserved
            ? { state: 'err', badge: 'HTTP 422', sub: 'overbooked · rejected' }
            : { state: 'skip', badge: 'SKIPPED', sub: 'not attempted' };

    const finalPaymentState: NodePlaybackState = isConfirmed
      ? { state: 'ok', badge: 'CHARGED', sub: '$400.00 captured' }
      : hasPaymentCharged
        ? { state: 'cancel', badge: 'REFUNDED', sub: '$400.00 refunded' }
        : isCompensated && hasHotelReserved
          ? { state: 'err', badge: 'HTTP 400', sub: 'insufficient funds' }
          : isFailed
            ? { state: 'err', badge: 'ERROR', sub: 'transaction halted' }
            : { state: 'skip', badge: 'SKIPPED', sub: 'not attempted' };

    const finalLinks: [LinkPlaybackState, LinkPlaybackState] = [
      {
        isLive: hasFlightReserved && !isFlightCancelled,
        isReverse: isFlightCancelled,
      },
      {
        isLive: hasHotelReserved && !isHotelCancelled,
        isReverse: isHotelCancelled,
      },
    ];

    // If historical or test mode, skip animation and jump immediately to final settled state
    const isTest = typeof import.meta !== 'undefined' && import.meta.env?.MODE === 'test';
    if (isHistorical || isTest) {
      setPlaybackState({
        nodes: {
          flight: finalFlightState,
          hotel: finalHotelState,
          payment: finalPaymentState,
        },
        links: finalLinks,
        isComplete: true,
      });
      return;
    }

    // Step-by-step playback sequence (approx 320ms per transition)
    const STEP_MS = 320;

    // Frame 0: Flight running
    setPlaybackState({
      nodes: {
        flight: { state: 'running', badge: 'running', sub: 'POST /reserve' },
        hotel: { state: 'idle', badge: 'idle', sub: 'pending upstream' },
        payment: { state: 'idle', badge: 'idle', sub: 'pending upstream' },
      },
      links: [
        { isLive: false, isReverse: false },
        { isLive: false, isReverse: false },
      ],
      isComplete: false,
    });

    // Frame 1: Flight succeeds, Link 0 active, Hotel running
    const t1 = setTimeout(() => {
      setPlaybackState({
        nodes: {
          flight: { state: 'ok', badge: 'RESERVED', sub: 'seat hold created' },
          hotel: {
            state: hasHotelReserved || (isCompensated && !hasHotelReserved) ? 'running' : 'idle',
            badge: hasHotelReserved || (isCompensated && !hasHotelReserved) ? 'running' : 'idle',
            sub: 'POST /reserve',
          },
          payment: { state: 'idle', badge: 'idle', sub: 'pending upstream' },
        },
        links: [
          { isLive: true, isReverse: false },
          { isLive: false, isReverse: false },
        ],
        isComplete: false,
      });
    }, STEP_MS);
    timerRef.current.push(t1);

    // Frame 2: Hotel result, Link 1 active if successful, Payment running
    const t2 = setTimeout(() => {
      const hotelErr = !hasHotelReserved && (isCompensated || isFailed);

      setPlaybackState({
        nodes: {
          flight: { state: 'ok', badge: 'RESERVED', sub: 'seat hold created' },
          hotel: hotelErr
            ? { state: 'err', badge: 'HTTP 422', sub: 'overbooked · rejected' }
            : { state: 'ok', badge: 'RESERVED', sub: 'room hold created' },
          payment: !hotelErr
            ? { state: 'running', badge: 'running', sub: 'POST /charge' }
            : { state: 'skip', badge: 'SKIPPED', sub: 'upstream rejected' },
        },
        links: [
          { isLive: !hotelErr, isReverse: false },
          { isLive: !hotelErr, isReverse: false },
        ],
        isComplete: false,
      });
    }, STEP_MS * 2);
    timerRef.current.push(t2);

    // Frame 3: Payment result or Rollback initiation
    const t3 = setTimeout(() => {
      const payErr = !hasPaymentCharged && (isCompensated || isFailed);
      const hotelErr = !hasHotelReserved && (isCompensated || isFailed);

      if (hotelErr) {
        // Rollback flight: Link 0 becomes reverse, Flight starts unwinding
        setPlaybackState({
          nodes: {
            flight: { state: 'unwinding', badge: 'unwinding', sub: 'POST /cancel' },
            hotel: { state: 'err', badge: 'HTTP 422', sub: 'overbooked · rejected' },
            payment: { state: 'skip', badge: 'SKIPPED', sub: 'not attempted' },
          },
          links: [
            { isLive: false, isReverse: true },
            { isLive: false, isReverse: false },
          ],
          isComplete: false,
        });
      } else if (payErr) {
        // Payment failed, unwind hotel: Payment turns red (err). Link 1 reverses. Hotel starts unwinding. Flight stays green (ok).
        setPlaybackState({
          nodes: {
            flight: { state: 'ok', badge: 'RESERVED', sub: 'seat hold created' },
            hotel: { state: 'unwinding', badge: 'unwinding', sub: 'POST /cancel' },
            payment: { state: 'err', badge: 'HTTP 400', sub: 'insufficient funds' },
          },
          links: [
            { isLive: false, isReverse: false },
            { isLive: false, isReverse: true },
          ],
          isComplete: false,
        });
      } else {
        // Payment succeeded
        setPlaybackState({
          nodes: {
            flight: { state: 'ok', badge: 'CONFIRMED', sub: 'confirmed' },
            hotel: { state: 'ok', badge: 'CONFIRMED', sub: 'confirmed' },
            payment: { state: 'ok', badge: 'CHARGED', sub: 'captured' },
          },
          links: [
            { isLive: true, isReverse: false },
            { isLive: true, isReverse: false },
          ],
          isComplete: false,
        });
      }
    }, STEP_MS * 3);
    timerRef.current.push(t3);

    // Frame 4: Rollback progression
    const t4 = setTimeout(() => {
      const hotelErr = !hasHotelReserved && (isCompensated || isFailed);
      const payErr = !hasPaymentCharged && isCompensated && hasHotelReserved;

      if (hotelErr) {
        // Flight finishes cancelling
        setPlaybackState({
          nodes: {
            flight: { state: 'cancel', badge: 'CANCELLED', sub: 'seat hold released' },
            hotel: { state: 'err', badge: 'HTTP 422', sub: 'overbooked · rejected' },
            payment: { state: 'skip', badge: 'SKIPPED', sub: 'not attempted' },
          },
          links: [
            { isLive: false, isReverse: true },
            { isLive: false, isReverse: false },
          ],
          isComplete: false,
        });
      } else if (payErr) {
        // Hotel cancelled, now unwind flight: Link 0 reverses, Flight begins unwinding
        setPlaybackState({
          nodes: {
            flight: { state: 'unwinding', badge: 'unwinding', sub: 'POST /cancel' },
            hotel: { state: 'cancel', badge: 'CANCELLED', sub: 'room hold released' },
            payment: { state: 'err', badge: 'HTTP 400', sub: 'insufficient funds' },
          },
          links: [
            { isLive: false, isReverse: true },
            { isLive: false, isReverse: true },
          ],
          isComplete: false,
        });
      }
    }, STEP_MS * 4);
    timerRef.current.push(t4);

    // Frame 5: Final Settled State
    const t5 = setTimeout(() => {
      setPlaybackState({
        nodes: {
          flight: finalFlightState,
          hotel: finalHotelState,
          payment: finalPaymentState,
        },
        links: finalLinks,
        isComplete: true,
      });
    }, STEP_MS * 5);
    timerRef.current.push(t5);

    return clearTimers;
  }, [response, isPending, isHistorical]);

  return playbackState;
}
