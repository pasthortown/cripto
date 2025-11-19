import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, Subject, BehaviorSubject } from 'rxjs';
import {
  Kline,
  Prediction,
  Symbol,
  ApiResponse,
  Statistics,
  WebSocketMessage
} from '../models/crypto.models';

@Injectable({
  providedIn: 'root'
})
export class BinanceApiService {
  private readonly BASE_URL = 'http://localhost:8888';
  private readonly WS_URL = 'ws://localhost:8888/ws/updates';

  private ws: WebSocket | null = null;
  private wsMessages$ = new Subject<WebSocketMessage>();
  private wsConnected$ = new BehaviorSubject<boolean>(false);
  private reconnectAttempts = 0;
  private readonly MAX_RECONNECT_ATTEMPTS = 5;

  constructor(private http: HttpClient) {}

  // ==================== REST API Endpoints ====================

  /**
   * Health check del backend
   */
  healthCheck(): Observable<any> {
    return this.http.get(`${this.BASE_URL}/health`);
  }

  /**
   * Obtiene la lista de símbolos disponibles
   */
  getSymbols(): Observable<ApiResponse<Symbol>> {
    return this.http.get<ApiResponse<Symbol>>(`${this.BASE_URL}/api/symbols`);
  }

  /**
   * Sincroniza datos de una moneda
   */
  syncData(symbol: string): Observable<ApiResponse<any>> {
    return this.http.post<ApiResponse<any>>(`${this.BASE_URL}/api/sync`, { symbol });
  }

  /**
   * Obtiene datos históricos de una moneda
   */
  getData(
    symbol: string,
    startTime?: number,
    endTime?: number,
    limit?: number
  ): Observable<ApiResponse<Kline>> {
    let params: any = {};

    if (startTime) params.start_time = startTime.toString();
    if (endTime) params.end_time = endTime.toString();
    if (limit) params.limit = limit.toString();

    return this.http.get<ApiResponse<Kline>>(
      `${this.BASE_URL}/api/data/${symbol}`,
      { params }
    );
  }

  /**
   * Obtiene predicciones de una moneda
   */
  getPredictions(
    symbol: string,
    startTime?: number,
    endTime?: number,
    limit?: number
  ): Observable<ApiResponse<Prediction>> {
    let params: any = {};

    if (startTime) params.start_time = startTime.toString();
    if (endTime) params.end_time = endTime.toString();
    if (limit) params.limit = limit.toString();

    return this.http.get<ApiResponse<Prediction>>(
      `${this.BASE_URL}/api/predictions/${symbol}`,
      { params }
    );
  }

  /**
   * Obtiene estadísticas de una moneda
   */
  getStats(symbol: string): Observable<ApiResponse<Statistics>> {
    return this.http.get<ApiResponse<Statistics>>(
      `${this.BASE_URL}/api/stats/${symbol}`
    );
  }

  // ==================== WebSocket ====================

  /**
   * Conecta al WebSocket
   */
  connectWebSocket(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket ya está conectado');
      return;
    }

    try {
      this.ws = new WebSocket(this.WS_URL);

      this.ws.onopen = () => {
        console.log('WebSocket conectado');
        this.wsConnected$.next(true);
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          console.log('🔵 WebSocket onmessage raw:', event.data);
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('🔵 WebSocket mensaje parseado:', message);
          this.wsMessages$.next(message);
          console.log('🔵 Mensaje emitido al Subject wsMessages$');
        } catch (error) {
          console.error('❌ Error al parsear mensaje WebSocket:', error, event.data);
        }
      };

      this.ws.onerror = (error) => {
        console.error('Error en WebSocket:', error);
        this.wsConnected$.next(false);
      };

      this.ws.onclose = () => {
        console.log('WebSocket desconectado');
        this.wsConnected$.next(false);
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('Error al conectar WebSocket:', error);
      this.wsConnected$.next(false);
    }
  }

  /**
   * Intenta reconectar el WebSocket
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

      console.log(`Reintentando conexión en ${delay}ms (intento ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})`);

      setTimeout(() => {
        this.connectWebSocket();
      }, delay);
    } else {
      console.error('Máximo de intentos de reconexión alcanzado');
    }
  }

  /**
   * Desconecta el WebSocket
   */
  disconnectWebSocket(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.wsConnected$.next(false);
    }
  }

  /**
   * Suscribe a uno o más símbolos
   */
  subscribe(symbols: string[]): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: symbols
      }));
    } else {
      console.warn('WebSocket no está conectado. No se puede suscribir.');
    }
  }

  /**
   * Desuscribe de uno o más símbolos
   */
  unsubscribe(symbols: string[]): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'unsubscribe',
        symbols: symbols
      }));
    }
  }

  /**
   * Envía ping al servidor (heartbeat)
   */
  ping(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'ping' }));
    }
  }

  /**
   * Obtiene estadísticas del servidor WebSocket
   */
  getServerStats(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'stats' }));
    }
  }

  /**
   * Observable de mensajes WebSocket
   */
  getWebSocketMessages(): Observable<WebSocketMessage> {
    return this.wsMessages$.asObservable();
  }

  /**
   * Observable del estado de conexión WebSocket
   */
  getConnectionStatus(): Observable<boolean> {
    return this.wsConnected$.asObservable();
  }

  /**
   * Limpia recursos al destruir el servicio
   */
  ngOnDestroy(): void {
    this.disconnectWebSocket();
  }
}
