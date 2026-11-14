import { useEffect, useState } from 'react';

import type { BookingResponse } from '../api/contracts';

export type NodeVisualState = 'idle' | 'running' | 'ok' | 'err' | 'unwinding' | 'cancel' | 'skip';

interface NodePlaybackState {
  state: NodeVisualState;
  badge: string;
  sub: string;
}

interface LinkPlaybackState {
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

const STEP_MS = 320;

function computePlayback(
  frame: number,
  response: BookingResponse | null,
  isPending: boolean,
): TopologyPlayback {
  if (isPending && !response) {
    return {
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
    };
  }

  if (!response) {
    return {
      nodes: DEFAULT_NODES,
      links: DEFAULT_LINKS,
      isComplete: false,
    };
  }

  const hasFlightReserved = response.steps_completed.includes('reserve_flight');
  const hasHotelReserved = response.steps_completed.includes('reserve_hotel');
  const hasPaymentCharged = response.steps_completed.includes('charge_payment');
  const isFlightCancelled = response.compensations_executed.includes('cancel_flight');
  const isHotelCancelled = response.compensations_executed.includes('cancel_hotel');
  const isConfirmed = response.status === 'CONFIRMED';
  const isCompensated = response.status === 'COMPENSATED';
  const isFailed = response.status === 'FAILED';

  const hotelErr = !hasHotelReserved && (isCompensated || isFailed);
  const payErr = !hasPaymentCharged && (isCompensated || isFailed);

  const finalFlight: NodePlaybackState = isFlightCancelled
    ? { state: 'cancel', badge: 'CANCELLED', sub: 'seat hold released' }
    : isConfirmed
      ? { state: 'ok', badge: 'CONFIRMED', sub: 'seat 12A confirmed' }
      : hasFlightReserved
        ? { state: 'ok', badge: 'RESERVED', sub: 'seat held' }
        : { state: 'idle', badge: 'unreported', sub: 'not attempted' };

  const finalHotel: NodePlaybackState = isHotelCancelled
    ? { state: 'cancel', badge: 'CANCELLED', sub: 'room hold released' }
    : isConfirmed
      ? { state: 'ok', badge: 'CONFIRMED', sub: 'room confirmed' }
      : hasHotelReserved
        ? { state: 'ok', badge: 'RESERVED', sub: 'room held' }
        : isCompensated && !hasHotelReserved
          ? { state: 'err', badge: 'HTTP 422', sub: 'overbooked · rejected' }
          : { state: 'skip', badge: 'SKIPPED', sub: 'not attempted' };

  const finalPayment: NodePlaybackState = isConfirmed
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

  if (frame >= 5) {
    return {
      nodes: {
        flight: finalFlight,
        hotel: finalHotel,
        payment: finalPayment,
      },
      links: finalLinks,
      isComplete: true,
    };
  }

  switch (frame) {
    case 0:
      return {
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
      };

    case 1:
      return {
        nodes: {
          flight: { state: 'ok', badge: 'RESERVED', sub: 'seat hold created' },
          hotel: {
            state: hasHotelReserved || hotelErr ? 'running' : 'idle',
            badge: hasHotelReserved || hotelErr ? 'running' : 'idle',
            sub: 'POST /reserve',
          },
          payment: { state: 'idle', badge: 'idle', sub: 'pending upstream' },
        },
        links: [
          { isLive: true, isReverse: false },
          { isLive: false, isReverse: false },
        ],
        isComplete: false,
      };

    case 2:
      return {
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
      };

    case 3:
      if (hotelErr) {
        return {
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
        };
      }

      if (payErr) {
        return {
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
        };
      }

      return {
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
      };

    case 4:
      if (hotelErr) {
        return {
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
        };
      }

      if (payErr) {
        return {
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
        };
      }

      return {
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
      };

    default:
      return {
        nodes: {
          flight: finalFlight,
          hotel: finalHotel,
          payment: finalPayment,
        },
        links: finalLinks,
        isComplete: true,
      };
  }
}

export function useTopologyPlayback({
  response,
  isPending,
  isHistorical = false,
}: {
  response: BookingResponse | null;
  isPending: boolean;
  isHistorical?: boolean;
}): TopologyPlayback {
  const isTest = typeof import.meta !== 'undefined' && import.meta.env?.MODE === 'test';
  const shouldAnimate = !isHistorical && !isTest && !!response;

  const [prevResponse, setPrevResponse] = useState(response);
  const [frame, setFrame] = useState(shouldAnimate ? 0 : 5);

  if (prevResponse !== response) {
    setPrevResponse(response);
    setFrame(shouldAnimate ? 0 : 5);
  }

  useEffect(() => {
    if (!shouldAnimate) {
      return;
    }

    const interval = setInterval(() => {
      setFrame((prev) => {
        if (prev >= 4) {
          clearInterval(interval);
          return 5;
        }
        return prev + 1;
      });
    }, STEP_MS);

    return () => clearInterval(interval);
  }, [response, shouldAnimate]);

  return computePlayback(frame, response, isPending);
}

