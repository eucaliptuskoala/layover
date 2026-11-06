import { useId } from 'react';

export function CanalIllustration() {
  const sky = useId();
  const water = useId();
  return (
    <svg viewBox="0 0 92 92" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={sky} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FBF2E0" />
          <stop offset="1" stopColor="#F4E6CD" />
        </linearGradient>
        <linearGradient id={water} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#DDEBE5" />
          <stop offset="1" stopColor="#C9DFD7" />
        </linearGradient>
      </defs>
      <rect width="92" height="92" fill={`url(#${sky})`} />
      <circle cx="71" cy="20" r="8" fill="#F3D49B" opacity=".9" />
      <path d="M0 63h92v29H0z" fill={`url(#${water})`} />
      <path d="M4 63V37l7-7 7 7v26z" fill="#C98A55" />
      <path d="M8 40h6v4H8zm0 8h6v4H8zm0 8h6v4H8z" fill="#FDF4E3" opacity=".9" />
      <path d="M20 63V27l9-9 9 9v36z" fill="#B2744B" />
      <path d="M25 34h8v4h-8zm0 8h8v4h-8zm0 8h8v4h-8z" fill="#FBEEDB" opacity=".92" />
      <path d="M40 63V39l7-7 7 7v24z" fill="#D9A468" />
      <path d="M44 44h6v4h-6zm0 8h6v4h-6z" fill="#FFF7E9" opacity=".92" />
      <path d="M56 63V31l8-8 8 8v32z" fill="#C08052" />
      <path d="M61 38h7v4h-7zm0 8h7v4h-7zm0 8h7v4h-7z" fill="#FBEFDC" opacity=".92" />
      <path d="M74 63V41l6-6 6 6v22z" fill="#CE9460" />
      <path d="M78 46h5v4h-5zm0 8h5v4h-5z" fill="#FFF7E9" opacity=".9" />
      <path d="M0 70h92M0 76h92M0 82h92" stroke="#B9D4CB" opacity=".7" />
      <path d="M10 70v6M30 76v6M52 70v6M72 76v6" stroke="#B9D4CB" opacity=".45" />
    </svg>
  );
}
