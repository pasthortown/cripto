/**
 * Modelos TypeScript para datos de criptomonedas
 */

export interface Kline {
  open_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  close_time: number;
  quote_asset_volume?: number;
  number_of_trades?: number;
  taker_buy_base_asset_volume?: number;
  taker_buy_quote_asset_volume?: number;
  timestamp?: string;
}

export interface Prediction {
  open_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  close_time: number;
  predicted_at: string;
  model_version?: string;
  sequence_length?: number;
}

export interface Symbol {
  symbol: string;
  total_records: number;
  first_record: string;
  last_record: string;
  last_price: number;
}

export interface ApiResponse<T> {
  success: boolean;
  count?: number;
  data?: T[];
  symbol?: string;
  statistics?: Statistics;
  symbols?: Symbol[];
  error?: boolean;
  message?: string;
}

export interface Statistics {
  symbol: string;
  total_records: number;
  first_record: string;
  last_record: string;
  last_price?: number;
}

export interface WebSocketMessage {
  type: 'connected' | 'subscribed' | 'unsubscribed' | 'sync_complete' | 'pong' | 'stats' | 'error';
  message?: string;
  symbols?: string[];
  symbol?: string;
  timestamp: string;
  statistics?: {
    new_records: number;
    total_records: number;
    last_price: number;
    last_record: string;
  };
  data?: any;
}

export type TimeRange = '15min' | '30min' | '1hour' | 'day' | 'week' | 'month' | 'year';

export interface TimeRangeOption {
  value: TimeRange;
  label: string;
  minutes: number;
}
