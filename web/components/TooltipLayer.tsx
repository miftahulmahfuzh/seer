'use client';

import { useEffect } from 'react';
import { installTooltips } from './tooltip';

export function TooltipLayer() {
  useEffect(() => installTooltips(), []);
  return null;
}
