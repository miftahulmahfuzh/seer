// Sean's shared types. No imports and no data access, so routes, client islands, tests and the
// live smoke script can all read this file.

export type OrderSide = 'buy' | 'sell';

/** One partial-fill line printed under "Average price": "· 0.38 shares   @ $131.47". */
export type SeanFill = { shares: number; price: number };

/**
 * One Gotrade order, as its Order Summary sheet printed it. Mirrors table sean_orders
 * (db/migrations/015_sean.sql). Money is US dollars, already rounded to cents; the three fee
 * fields are magnitudes, because the receipt's + / - sign only restates the side.
 */
export type SeanOrder = {
  side: OrderSide;
  /** As printed, spaces collapsed: 'Market Buy', 'Limit Sell'. */
  orderType: string;
  /** As printed: 'Filled' (toOrder accepts nothing else). */
  status: string;
  /** Canonical ticker, the way the engine stores it: 'PLTR', 'BRK.B'. */
  symbol: string;
  /** ISO 8601 with the WIB offset: '2026-10-07T21:55:00+07:00'. */
  executedAt: string;
  /** 'Average price' or 'Execution price', up to 6 decimals. */
  price: number;
  /** 'Filled shares', up to 9 decimals. */
  shares: number;
  /** 'Trade amount'. */
  amountUsd: number;
  tradingFeeUsd: number;
  regulatoryFeeUsd: number;
  ppnUsd: number;
  /** Buy: amount + fees. Sell: amount - fees. */
  totalUsd: number;
  /** The sell receipt's 'Net Profit' (Gotrade's own figure); null on buys. */
  netProfitUsd: number | null;
  /** Partial-fill lines, [] when none were printed. */
  fills: SeanFill[];
};

/** A partial-fill line as the model transcribes it: printed text, not numbers. */
export type RawFill = { shares: string | null; price: string | null };

/**
 * What the model is asked to return (prompt.ts ORDER_SHAPE). Every value is the printed text;
 * money.ts turns it into numbers and order.ts checks the arithmetic. toOrder accepts `unknown`,
 * so this type documents the shape and types the fixtures; it is not trusted.
 */
export type RawReceipt = {
  isOrderSummary: boolean | null;
  status: string | null;
  date: string | null;
  time: string | null;
  orderType: string | null;
  ticker: string | null;
  priceLabel: string | null;
  price: string | null;
  fills: RawFill[];
  filledShares: string | null;
  tradeAmount: string | null;
  tradingFee: string | null;
  regulatoryFee: string | null;
  ppn: string | null;
  total: string | null;
  netProfit: string | null;
  netProfitColor: 'green' | 'red' | null;
};
