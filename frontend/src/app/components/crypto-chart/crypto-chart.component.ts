import { Component, OnInit, OnDestroy, ViewChild, ElementRef, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Chart, ChartConfiguration, registerables } from 'chart.js';
import { CandlestickController, CandlestickElement } from 'chartjs-chart-financial';
import 'chartjs-adapter-date-fns';
import { BinanceApiService } from '../../services/binance-api.service';
import {
  Kline,
  Prediction,
  Symbol,
  TimeRange,
  TimeRangeOption,
  WebSocketMessage
} from '../../models/crypto.models';
import { Subscription, interval } from 'rxjs';

Chart.register(...registerables, CandlestickController, CandlestickElement);

// Plugin personalizado para evitar errores con hover colors en candlesticks
const candlestickHoverPlugin = {
  id: 'candlestickHoverFix',
  beforeUpdate(chart: any) {
    chart.data.datasets.forEach((dataset: any) => {
      if (dataset.type === 'candlestick') {
        // Prevenir que Chart.js intente auto-generar hover colors
        dataset.hoverBackgroundColor = dataset.color;
        dataset.hoverBorderColor = dataset.borderColor;
      }
    });
  }
};

Chart.register(candlestickHoverPlugin);

@Component({
  selector: 'app-crypto-chart',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './crypto-chart.component.html',
  styleUrls: ['./crypto-chart.component.css']
})
export class CryptoChartComponent implements OnInit, OnDestroy {
  @ViewChild('chartCanvas', { static: true }) chartCanvas!: ElementRef<HTMLCanvasElement>;

  // Chart
  chart: Chart | null = null;

  // Símbolos disponibles
  availableSymbols: Symbol[] = [];
  selectedSymbol: string = 'BTCUSDT';

  // Rangos de tiempo
  timeRanges: TimeRangeOption[] = [
    { value: '15min', label: '15 Minutos', minutes: 15 },
    { value: '30min', label: '30 Minutos', minutes: 30 },
    { value: '1hour', label: '1 Hora', minutes: 60 },
    { value: 'day', label: 'Día', minutes: 1440 }
  ];
  selectedTimeRange: TimeRange = 'day';

  // Datos
  klines: Kline[] = [];
  predictions: Prediction[] = [];

  // Estado
  loading: boolean = true;
  wsConnected: boolean = false;
  error: string | null = null;
  lastUpdate: Date | null = null;

  // Estado de zoom/selección
  private isSelecting: boolean = false;
  private selectionStart: number | null = null;
  private selectionEnd: number | null = null;
  private zoomStartTime: number | null = null;
  private zoomEndTime: number | null = null;
  isZoomed: boolean = false;
  private previousTimeRange: TimeRange | null = null;

  // Estado de predicción seleccionada
  selectedPrediction: Prediction | null = null;

  // Subscripciones
  private subscriptions: Subscription[] = [];
  private pingInterval: any;

  constructor(
    private apiService: BinanceApiService,
    private ngZone: NgZone
  ) {}

  ngOnInit(): void {
    this.initializeComponent();
  }

  ngOnDestroy(): void {
    this.cleanup();
  }

  /**
   * Inicializa el componente
   */
  private async initializeComponent(): Promise<void> {
    try {
      // 1. Cargar símbolos disponibles
      await this.loadSymbols();

      // 2. Conectar WebSocket
      this.connectWebSocket();

      // 3. Cargar datos iniciales
      await this.loadInitialData();

      // 4. Crear chart
      this.createChart();

      // 5. Iniciar ping periódico (cada 30 segundos)
      this.startPingInterval();

    } catch (error) {
      console.error('Error al inicializar componente:', error);
      this.error = 'Error al cargar datos iniciales';
      this.loading = false;
    }
  }

  /**
   * Carga la lista de símbolos disponibles
   */
  private async loadSymbols(): Promise<void> {
    return new Promise((resolve, reject) => {
      const sub = this.apiService.getSymbols().subscribe({
        next: (response) => {
          if (response.success && response.symbols) {
            this.availableSymbols = response.symbols;
            console.log('Símbolos cargados:', this.availableSymbols.length);
          }
          resolve();
        },
        error: (error) => {
          console.error('Error al cargar símbolos:', error);
          reject(error);
        }
      });
      this.subscriptions.push(sub);
    });
  }

  /**
   * Conecta al WebSocket y maneja mensajes
   */
  private connectWebSocket(): void {
    // Conectar
    this.apiService.connectWebSocket();

    // Escuchar estado de conexión
    const statusSub = this.apiService.getConnectionStatus().subscribe({
      next: (connected) => {
        this.wsConnected = connected;
        if (connected) {
          // Suscribirse al símbolo seleccionado
          this.apiService.subscribe([this.selectedSymbol]);
        }
      }
    });
    this.subscriptions.push(statusSub);

    // Escuchar mensajes
    const messagesSub = this.apiService.getWebSocketMessages().subscribe({
      next: (message) => this.handleWebSocketMessage(message)
    });
    this.subscriptions.push(messagesSub);
  }

  /**
   * Maneja mensajes del WebSocket
   */
  private handleWebSocketMessage(message: WebSocketMessage): void {
    console.log('📨 Mensaje WebSocket recibido:', message.type, message);

    switch (message.type) {
      case 'connected':
        console.log('🔌 WebSocket conectado:', message.message);
        break;

      case 'subscribed':
        console.log('✅ Suscrito a:', message.symbols);
        break;

      case 'sync_complete':
        console.log('🔄 Sincronización completada para:', message.symbol, '| Symbol actual:', this.selectedSymbol);
        if (message.symbol === this.selectedSymbol) {
          console.log('✅ Símbolos coinciden, recargando datos...');
          this.lastUpdate = new Date();
          // Recargar datos
          this.loadLatestData();
        } else {
          console.log('⏭️ Símbolo diferente, ignorando actualización');
        }
        break;

      case 'pong':
        console.log('🏓 Pong recibido');
        break;

      case 'error':
        console.error('❌ Error WebSocket:', message.message);
        break;

      default:
        console.warn('⚠️ Tipo de mensaje desconocido:', message.type);
        break;
    }
  }

  /**
   * Calcula el rango de tiempo para cargar predicciones
   * REGLA: Cargar predicciones según el intervalo seleccionado
   * - 1 día: Desde 00:00 del día actual hasta ahora + 1h
   * - Otros: Desde (ahora - intervalo) hasta (ahora + predicción futura)
   *
   * El filtrado de qué predicciones mostrar se hace en getPredictionCandlestickData()
   * IMPORTANTE: Trabaja en UTC para coincidir con los datos del backend
   */
  private getPredictionTimeRange(): { start_time: number, end_time: number } {
    const timeRange = this.getSelectedTimeRangeOption();
    const now = new Date();
    const nowMs = now.getTime();

    let start_time: number;
    let end_time: number;

    if (timeRange.minutes >= 1440) {
      // 1 día o mayor: Cargar desde 00:00 del día actual hasta ahora + 1h
      const startOfDay = new Date(now);
      startOfDay.setUTCHours(0, 0, 0, 0);
      start_time = startOfDay.getTime();
      end_time = nowMs + (60 * 60 * 1000); // +1 hora
    } else {
      // Otros rangos: Cargar desde (ahora - intervalo) hasta (ahora + predicción futura)
      let futurePredictionMinutes: number;

      if (timeRange.minutes >= 60) {
        futurePredictionMinutes = 60;
      } else if (timeRange.minutes >= 30) {
        futurePredictionMinutes = 30;
      } else {
        futurePredictionMinutes = 15;
      }

      start_time = nowMs - (timeRange.minutes * 60 * 1000); // Desde ahora - intervalo
      end_time = nowMs + (futurePredictionMinutes * 60 * 1000); // Hasta ahora + predicción futura
    }

    console.log(`📊 Cargando predicciones para ${timeRange.label}`);
    console.log(`   Desde (UTC): ${new Date(start_time).toISOString()}`);
    console.log(`   Hasta (UTC): ${new Date(end_time).toISOString()}`);
    console.log(`   Rango total: ${(end_time - start_time) / (1000 * 60)} minutos`);

    return {
      start_time: start_time,
      end_time: end_time
    };
  }

  /**
   * Carga datos iniciales
   * IMPORTANTE: Siempre carga datos del día completo (1440 minutos)
   * Los intervalos de tiempo (1h, 30min, 15min) son solo zoom sobre estos datos
   */
  private async loadInitialData(): Promise<void> {
    this.loading = true;
    this.error = null;

    try {
      // SIEMPRE cargar datos del día completo
      const limit = 1440; // 24 horas

      console.log(`📊 Cargando datos reales del día completo`);
      console.log(`   Límite: ${limit} minutos (1 día)`);

      // Cargar datos históricos (datos reales)
      // Para evitar problemas de zona horaria, solo usamos limit sin start_time/end_time
      // El backend retornará automáticamente los últimos N minutos disponibles
      const dataPromise = new Promise<void>((resolve, reject) => {
        const sub = this.apiService.getData(
          this.selectedSymbol,
          undefined,  // No start_time para evitar problemas de zona horaria
          undefined,  // No end_time
          limit       // Solo limit - backend retorna últimos N registros
        ).subscribe({
          next: (response) => {
            if (response.success && response.data) {
              this.klines = response.data;
              console.log('✅ Datos reales cargados:', this.klines.length, 'minutos');
              if (this.klines.length > 0) {
                const first = new Date(this.klines[0].open_time).toLocaleString();
                const last = new Date(this.klines[this.klines.length - 1].open_time).toLocaleString();
                console.log(`   Rango: ${first} - ${last}`);
              }
            }
            resolve();
          },
          error: (error) => {
            console.error('❌ Error al cargar datos:', error);
            reject(error);
          }
        });
        this.subscriptions.push(sub);
      });

      // Cargar predicciones según el rango de tiempo
      const predictionsPromise = new Promise<void>((resolve, reject) => {
        const { start_time, end_time } = this.getPredictionTimeRange();

        const sub = this.apiService.getPredictions(this.selectedSymbol, start_time, end_time, undefined).subscribe({
          next: (response) => {
            if (response.success && response.data) {
              this.predictions = response.data;
              console.log('✅ Predicciones cargadas:', this.predictions.length, 'minutos');
            }
            resolve();
          },
          error: (error) => {
            console.error('⚠️ Error al cargar predicciones:', error);
            // No rechazar si no hay predicciones
            this.predictions = [];
            resolve();
          }
        });
        this.subscriptions.push(sub);
      });

      await Promise.all([dataPromise, predictionsPromise]);

      // IMPORTANTE: Actualizar el chart después de cargar los datos
      if (this.chart) {
        this.updateChart();
      }

    } catch (error) {
      console.error('❌ Error al cargar datos iniciales:', error);
      this.error = 'Error al cargar datos';
    } finally {
      this.loading = false;
    }
  }

  /**
   * Carga los últimos datos disponibles de forma incremental (sliding window)
   */
  private async loadLatestData(): Promise<void> {
    console.log('🔄 loadLatestData() iniciado para', this.selectedSymbol);

    try {
      // Si no hay datos previos, cargar todo
      if (this.klines.length === 0) {
        console.log('⚠️ No hay datos previos, cargando datos iniciales...');
        await this.loadInitialData();
        return;
      }

      // Obtener el último timestamp graficado
      const lastKline = this.klines[this.klines.length - 1];
      const lastOpenTime = lastKline.open_time;
      const startTime = lastOpenTime + 60000; // Siguiente minuto después del último dato

      console.log('📊 Último dato graficado:', new Date(lastOpenTime).toISOString());
      console.log('📊 Solicitando datos desde:', new Date(startTime).toISOString());

      // Solicitar solo los datos nuevos desde el último timestamp
      const sub = this.apiService.getData(
        this.selectedSymbol,
        startTime,
        undefined, // end_time = ahora
        undefined  // sin límite, traer todo lo nuevo
      ).subscribe({
        next: (response) => {
          console.log('📥 Respuesta recibida:', response.success, 'con', response.data?.length, 'nuevos datos');

          if (response.success && response.data && response.data.length > 0) {
            // Ejecutar dentro de NgZone para que Angular detecte los cambios
            this.ngZone.run(() => {
              const newData = response.data!;
              const newDataCount = newData.length;

              console.log(`➕ Agregando ${newDataCount} nuevos datos al final`);
              console.log(`➖ Eliminando ${newDataCount} datos del inicio`);

              // Agregar nuevos datos al final
              this.klines.push(...newData);

              // Eliminar la misma cantidad del inicio (sliding window)
              this.klines.splice(0, newDataCount);

              // Obtener el rango de tiempo seleccionado
              const timeRange = this.getSelectedTimeRangeOption();
              const maxDataPoints = timeRange.minutes;

              // Asegurar que no excedemos el límite del rango de tiempo
              if (this.klines.length > maxDataPoints) {
                const excess = this.klines.length - maxDataPoints;
                console.log(`⚠️ Exceso de ${excess} datos, recortando...`);
                this.klines.splice(0, excess);
              }

              console.log(`📊 Total de datos después de sliding window: ${this.klines.length}`);

              this.lastUpdate = new Date();

              // Actualizar el chart
              if (this.chart) {
                this.updateChart();
                console.log('✅ Chart actualizado con sliding window');
              } else {
                console.warn('⚠️ Chart no existe');
              }
            });
          } else {
            console.log('ℹ️ No hay datos nuevos disponibles');
          }
        },
        error: (error) => {
          console.error('❌ Error al cargar últimos datos:', error);
        }
      });
      this.subscriptions.push(sub);

    } catch (error) {
      console.error('❌ Error al cargar últimos datos:', error);
    }
  }

  /**
   * Crea el chart de Chart.js
   */
  private createChart(): void {
    const ctx = this.chartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    // Construir datasets dinámicamente
    const datasets: any[] = [
      {
        type: 'candlestick',
        label: `${this.selectedSymbol} - Precio Real`,
        data: this.getCandlestickData(),
        color: {
          up: 'rgba(38, 166, 154, 0.8)',
          down: 'rgba(239, 83, 80, 0.8)',
          unchanged: 'rgba(158, 158, 158, 0.8)'
        },
        borderColor: {
          up: 'rgb(38, 166, 154)',
          down: 'rgb(239, 83, 80)',
          unchanged: 'rgb(158, 158, 158)'
        }
      }
    ];

    // Solo agregar dataset de predicciones si hay datos disponibles
    const predictionData = this.getPredictionCandlestickData();
    console.log('📊 Predicciones disponibles para el chart:', predictionData?.length || 0);
    if (predictionData && predictionData.length > 0) {
      console.log('✅ Agregando dataset de predicciones como área (open-close range)');

      // Crear datos para la línea de apertura (open)
      const openData = predictionData.map(pred => ({
        x: pred.x,
        y: pred.o
      }));

      // Crear datos para la línea de cierre (close)
      const closeData = predictionData.map(pred => ({
        x: pred.x,
        y: pred.c
      }));

      // Dataset para el límite superior del área (puede ser max de open/close)
      const upperData = predictionData.map(pred => ({
        x: pred.x,
        y: Math.max(pred.o, pred.c)
      }));

      // Dataset para el límite inferior del área (puede ser min de open/close)
      const lowerData = predictionData.map(pred => ({
        x: pred.x,
        y: Math.min(pred.o, pred.c)
      }));

      // Crear datos para high y low
      const highData = predictionData.map(pred => ({
        x: pred.x,
        y: pred.h
      }));

      const lowData = predictionData.map(pred => ({
        x: pred.x,
        y: pred.l
      }));

      // Dataset para el límite inferior del área (min entre open/close) - invisible
      datasets.push({
        type: 'line',
        label: `${this.selectedSymbol} - Predicción (rango inferior)`,
        data: lowerData,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        order: 2
      });

      // Dataset para el límite superior del área (max entre open/close) - con fill
      datasets.push({
        type: 'line',
        label: `${this.selectedSymbol} - Predicción (área)`,
        data: upperData,
        borderColor: 'rgba(147, 112, 219, 0.6)',
        backgroundColor: 'rgba(147, 112, 219, 0.3)',
        borderWidth: 1,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: '-1', // Rellenar hasta el dataset anterior
        tension: 0.1,
        order: 2
      });

      // Línea para High (máximo) - color morado más oscuro
      datasets.push({
        type: 'line',
        label: `${this.selectedSymbol} - Predicción High`,
        data: highData,
        borderColor: 'rgba(147, 112, 219, 0.9)',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [5, 3],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.1,
        order: 1
      });

      // Línea para Low (mínimo) - color morado más oscuro
      datasets.push({
        type: 'line',
        label: `${this.selectedSymbol} - Predicción Low`,
        data: lowData,
        borderColor: 'rgba(147, 112, 219, 0.9)',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [5, 3],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.1,
        order: 1
      });

      console.log('📊 Total datasets en el chart:', datasets.length);
    } else {
      console.log('❌ No hay predicciones para agregar al chart');
    }

    const config: ChartConfiguration = {
      type: 'candlestick' as any,
      data: {
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'nearest',
          intersect: false,
          axis: 'x'
        },
        events: ['mousedown', 'mouseup', 'mousemove', 'click', 'touchstart', 'touchmove', 'touchend'],
        plugins: {
          legend: {
            display: true,
            position: 'top'
          },
          title: {
            display: true,
            text: this.getChartTitle(),
            font: {
              size: 18
            }
          },
          tooltip: {
            callbacks: {
              title: (context) => {
                const dataPoint = context[0];
                if (dataPoint.raw && typeof dataPoint.raw === 'object' && 'x' in dataPoint.raw) {
                  const timestamp = (dataPoint.raw as any).x;
                  return new Date(timestamp).toLocaleString('es-ES', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  });
                }
                return '';
              },
              label: (context) => {
                const raw = context.raw as any;

                // Para velas (candlestick)
                if (raw && typeof raw === 'object' && 'o' in raw && 'h' in raw && 'l' in raw && 'c' in raw) {
                  const formatter = new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: 'USD',
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                  });

                  return [
                    `Apertura: ${formatter.format(raw.o)}`,
                    `Máximo:   ${formatter.format(raw.h)}`,
                    `Mínimo:   ${formatter.format(raw.l)}`,
                    `Cierre:   ${formatter.format(raw.c)}`
                  ];
                }

                // Para línea de predicción
                if (raw && typeof raw === 'object' && 'y' in raw) {
                  const label = context.dataset.label || '';
                  const value = new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: 'USD',
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                  }).format(raw.y);
                  return `${label}: ${value}`;
                }

                return '';
              }
            }
          }
        },
        onClick: (event, activeElements) => {
          this.onChartClick(event, activeElements);
        },
        scales: {
          x: {
            type: 'time',
            time: {
              unit: 'minute',
              displayFormats: {
                minute: 'HH:mm',
                hour: 'HH:mm',
                day: 'dd/MM HH:mm'
              },
              tooltipFormat: 'dd/MM/yyyy HH:mm'
            },
            display: true,
            title: {
              display: true,
              text: 'Tiempo'
            }
          },
          y: {
            display: true,
            title: {
              display: true,
              text: 'Precio (USD)'
            },
            ticks: {
              callback: (value) => {
                return new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: 'USD',
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 2
                }).format(value as number);
              }
            }
          }
        }
      }
    };

    this.chart = new Chart(ctx, config);

    // Agregar eventos para selección de zoom
    this.setupZoomEvents();
  }

  /**
   * Configura los eventos del mouse para selección de zoom
   */
  private setupZoomEvents(): void {
    const canvas = this.chartCanvas.nativeElement;

    canvas.addEventListener('mousedown', (e: MouseEvent) => this.onMouseDown(e));
    canvas.addEventListener('mousemove', (e: MouseEvent) => this.onMouseMove(e));
    canvas.addEventListener('mouseup', (e: MouseEvent) => this.onMouseUp(e));
    canvas.addEventListener('mouseleave', () => this.onMouseLeave());
  }

  /**
   * Maneja el evento mousedown
   */
  private onMouseDown(event: MouseEvent): void {
    if (!this.chart) return;

    const rect = this.chartCanvas.nativeElement.getBoundingClientRect();
    const x = event.clientX - rect.left;

    this.isSelecting = true;
    this.selectionStart = x;
    this.selectionEnd = null;
  }

  /**
   * Maneja el evento mousemove
   */
  private onMouseMove(event: MouseEvent): void {
    if (!this.isSelecting || !this.chart) return;

    const rect = this.chartCanvas.nativeElement.getBoundingClientRect();
    const x = event.clientX - rect.left;

    this.selectionEnd = x;

    // Redibujar el chart con la selección visual
    this.drawSelection();
  }

  /**
   * Maneja el evento mouseup
   */
  private onMouseUp(event: MouseEvent): void {
    if (!this.isSelecting || !this.chart) return;

    const rect = this.chartCanvas.nativeElement.getBoundingClientRect();
    const x = event.clientX - rect.left;

    this.selectionEnd = x;
    this.isSelecting = false;

    // Convertir posiciones de píxeles a timestamps
    if (this.selectionStart !== null && this.selectionEnd !== null) {
      // VALIDACIÓN 1: Debe haber un movimiento mínimo de píxeles (evitar clicks simples)
      const pixelDistance = Math.abs(this.selectionEnd - this.selectionStart);
      const MIN_PIXEL_DISTANCE = 20; // Mínimo 20 píxeles de arrastre

      if (pixelDistance < MIN_PIXEL_DISTANCE) {
        // Click simple, no activar zoom
        this.selectionStart = null;
        this.selectionEnd = null;
        return;
      }

      const xScale = this.chart.scales['x'];

      const time1 = xScale.getValueForPixel(this.selectionStart);
      const time2 = xScale.getValueForPixel(this.selectionEnd);

      if (time1 && time2) {
        const minTime = Math.min(time1, time2);
        const maxTime = Math.max(time1, time2);

        // VALIDACIÓN 2: El rango de tiempo debe ser al menos 1 minuto
        const timeRange = maxTime - minTime;
        const MIN_TIME_RANGE = 60 * 1000; // 1 minuto en milisegundos

        if (timeRange < MIN_TIME_RANGE) {
          // Rango muy pequeño, no activar zoom
          this.selectionStart = null;
          this.selectionEnd = null;
          return;
        }

        // Ambas validaciones pasadas, activar zoom
        this.previousTimeRange = this.selectedTimeRange;
        this.zoomStartTime = minTime;
        this.zoomEndTime = maxTime;
        this.isZoomed = true;

        // Actualizar el chart con el zoom
        this.updateChart();
      }
    }

    // Limpiar selección
    this.selectionStart = null;
    this.selectionEnd = null;
  }

  /**
   * Maneja el evento mouseleave
   */
  private onMouseLeave(): void {
    if (this.isSelecting) {
      this.isSelecting = false;
      this.selectionStart = null;
      this.selectionEnd = null;
    }
  }

  /**
   * Dibuja el área de selección visual
   */
  private drawSelection(): void {
    if (!this.chart || this.selectionStart === null || this.selectionEnd === null) return;

    // Redibujar el chart
    this.chart.update('none');

    // Dibujar rectángulo de selección
    const ctx = this.chartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const chartArea = this.chart.chartArea;
    const start = Math.min(this.selectionStart, this.selectionEnd);
    const end = Math.max(this.selectionStart, this.selectionEnd);

    ctx.save();
    ctx.fillStyle = 'rgba(0, 123, 255, 0.1)';
    ctx.strokeStyle = 'rgba(0, 123, 255, 0.5)';
    ctx.lineWidth = 2;

    ctx.fillRect(start, chartArea.top, end - start, chartArea.bottom - chartArea.top);
    ctx.strokeRect(start, chartArea.top, end - start, chartArea.bottom - chartArea.top);

    ctx.restore();
  }

  /**
   * Resetea el zoom y vuelve SIEMPRE a la vista de 1 día completo
   */
  resetZoom(): void {
    this.zoomStartTime = null;
    this.zoomEndTime = null;
    this.isZoomed = false;
    this.previousTimeRange = null;

    // SIEMPRE volver a la vista de 1 día completo
    this.selectedTimeRange = 'day';

    // Actualizar el chart para mostrar todos los datos sin zoom
    this.updateChart();
  }

  /**
   * Maneja el click en el gráfico para seleccionar predicciones
   */
  private onChartClick(event: any, activeElements: any[]): void {
    // No procesar clicks si estamos en modo selección para zoom
    if (this.isSelecting) return;

    if (!this.chart || !event.native) return;

    // Obtener la posición del click
    const rect = this.chartCanvas.nativeElement.getBoundingClientRect();
    const x = event.native.clientX - rect.left;

    // Convertir posición X a timestamp
    const xScale = this.chart.scales['x'];
    if (!xScale) return;

    const clickedTime = xScale.getValueForPixel(x);
    if (!clickedTime) return;

    // Buscar la predicción más cercana al tiempo clickeado
    const TOLERANCE_MS = 60000; // 1 minuto de tolerancia
    let closestPrediction: Prediction | null = null;
    let minDiff = Infinity;

    for (const prediction of this.predictions) {
      const predTime = new Date(prediction.close_time).getTime();
      const diff = Math.abs(predTime - clickedTime);

      if (diff < TOLERANCE_MS && diff < minDiff) {
        minDiff = diff;
        closestPrediction = prediction;
      }
    }

    // Actualizar la predicción seleccionada
    this.ngZone.run(() => {
      this.selectedPrediction = closestPrediction;
    });
  }

  /**
   * Obtiene el gradiente CSS para la card de predicción según la tendencia
   */
  getPredictionGradient(): string {
    if (!this.selectedPrediction) return '';

    const open = parseFloat(String(this.selectedPrediction.open));
    const close = parseFloat(String(this.selectedPrediction.close));

    // Tendencia alcista: close > open (verde oscuro)
    // Tendencia bajista: close < open (rojo oscuro)
    if (close > open) {
      return 'linear-gradient(135deg, #2D8B8B 0%, #1A5F5F 100%)';
    } else {
      return 'linear-gradient(135deg, #D63649 0%, #A01F2E 100%)';
    }
  }

  /**
   * Actualiza el chart con nuevos datos
   */
  private updateChart(): void {
    if (!this.chart) {
      console.warn('Chart no existe, no se puede actualizar');
      return;
    }

    try {
      const now = Date.now();
      const timeRange = this.getSelectedTimeRangeOption();

      console.log('Actualizando chart con', this.klines.length, 'datos reales y', this.predictions.length, 'predicciones');

      // Log de ventana de tiempo para rangos pequeños
      if (timeRange.minutes < 1440) {
        const windowStart = now - (timeRange.minutes * 60 * 1000);
        const windowEnd = now + (timeRange.minutes * 60 * 1000);
        console.log('📊 Ventana deslizante:', {
          now: new Date(now).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }),
          start: new Date(windowStart).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }),
          end: new Date(windowEnd).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
        });
      }

      // Actualizar dataset de velas (precios reales)
      const candlestickData = this.getCandlestickData();
      console.log('📊 Datos de velas reales:', candlestickData.length);
      this.chart.data.datasets[0].data = candlestickData;
      this.chart.data.datasets[0].label = `${this.selectedSymbol} - Precio Real`;

      // Actualizar datasets de predicción (área + líneas high/low)
      const predictionCandlestickData = this.getPredictionCandlestickData();
      console.log('🔮 Datos de predicción:', predictionCandlestickData.length);

      // Eliminar datasets de predicción antiguos (indices 1-4)
      while (this.chart.data.datasets.length > 1) {
        this.chart.data.datasets.pop();
      }

      // Si hay datos de predicción, crear los datasets de área
      if (predictionCandlestickData && predictionCandlestickData.length > 0) {
        // Crear datos para lower, upper, high, low
        const upperData = predictionCandlestickData.map(pred => ({
          x: pred.x,
          y: Math.max(pred.o, pred.c)
        }));

        const lowerData = predictionCandlestickData.map(pred => ({
          x: pred.x,
          y: Math.min(pred.o, pred.c)
        }));

        const highData = predictionCandlestickData.map(pred => ({
          x: pred.x,
          y: pred.h
        }));

        const lowData = predictionCandlestickData.map(pred => ({
          x: pred.x,
          y: pred.l
        }));

        // Dataset para el límite inferior del área - invisible
        this.chart.data.datasets.push({
          type: 'line',
          label: `${this.selectedSymbol} - Predicción (rango inferior)`,
          data: lowerData,
          borderColor: 'transparent',
          backgroundColor: 'transparent',
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: false,
          order: 2
        } as any);

        // Dataset para el límite superior del área - con fill
        this.chart.data.datasets.push({
          type: 'line',
          label: `${this.selectedSymbol} - Predicción (área)`,
          data: upperData,
          borderColor: 'rgba(147, 112, 219, 0.6)',
          backgroundColor: 'rgba(147, 112, 219, 0.3)',
          borderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 3,
          fill: '-1',
          tension: 0.1,
          order: 2
        } as any);

        // Línea para High
        this.chart.data.datasets.push({
          type: 'line',
          label: `${this.selectedSymbol} - Predicción High`,
          data: highData,
          borderColor: 'rgba(147, 112, 219, 0.9)',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          borderDash: [5, 3],
          pointRadius: 0,
          pointHoverRadius: 3,
          fill: false,
          tension: 0.1,
          order: 1
        } as any);

        // Línea para Low
        this.chart.data.datasets.push({
          type: 'line',
          label: `${this.selectedSymbol} - Predicción Low`,
          data: lowData,
          borderColor: 'rgba(147, 112, 219, 0.9)',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          borderDash: [5, 3],
          pointRadius: 0,
          pointHoverRadius: 3,
          fill: false,
          tension: 0.1,
          order: 1
        } as any);

        console.log('✅ Datasets de predicción actualizados:', this.chart.data.datasets.length - 1, 'datasets');
      }

      // Actualizar título
      if (this.chart.options.plugins?.title) {
        this.chart.options.plugins.title.text = this.getChartTitle();
      }

      // Forzar actualización del chart con animación
      this.chart.update('active');

      console.log('✅ Chart actualizado correctamente');
    } catch (error) {
      console.error('❌ Error al actualizar chart:', error);
      this.error = 'Error al actualizar gráfico';
    }
  }

  /**
   * Obtiene todos los timestamps únicos (reales + predicciones) ordenados,
   * filtrados según el rango de tiempo seleccionado (ventana deslizante)
   */
  private getAllTimestamps(): number[] {
    const now = Date.now();
    const timeRange = this.getSelectedTimeRangeOption();
    const timestamps = new Set<number>();

    // Para rangos pequeños (< 1 día), usar ventana deslizante
    if (timeRange.minutes < 1440) {
      // Ventana: [now - timeRange] hasta [now + timeRange]
      const windowStart = now - (timeRange.minutes * 60 * 1000);
      const windowEnd = now + (timeRange.minutes * 60 * 1000);

      // Agregar timestamps de datos reales dentro de la ventana
      this.klines.forEach(kline => {
        if (kline.open_time >= windowStart && kline.open_time <= windowEnd) {
          timestamps.add(kline.open_time);
        }
      });

      // Agregar timestamps de predicciones dentro de la ventana
      this.predictions.forEach(pred => {
        if (pred.open_time >= windowStart && pred.open_time <= windowEnd) {
          timestamps.add(pred.open_time);
        }
      });
    } else {
      // Para rangos grandes (>= 1 día), mostrar todos los datos disponibles
      this.klines.forEach(kline => timestamps.add(kline.open_time));
      this.predictions.forEach(pred => timestamps.add(pred.open_time));
    }

    // Convertir a array y ordenar
    return Array.from(timestamps).sort((a, b) => a - b);
  }

  /**
   * Obtiene los datos en formato candlestick (velas japonesas)
   * IMPORTANTE: Siempre muestra TODOS los datos reales cargados, sin filtro de ventana
   */
  private getCandlestickData(): any[] {
    console.log('🔍 getCandlestickData() iniciado');
    console.log('  this.klines existe?', !!this.klines);
    console.log('  this.klines.length:', this.klines?.length);

    if (!this.klines || this.klines.length === 0) {
      console.log('❌ No hay klines, retornando array vacío');
      return [];
    }

    let filteredKlines = this.klines;

    // Si hay zoom activo, filtrar por el rango de zoom
    if (this.isZoomed && this.zoomStartTime && this.zoomEndTime) {
      console.log('🔍 Zoom activo, filtrando...');
      filteredKlines = this.klines.filter(kline =>
        kline.open_time >= this.zoomStartTime! && kline.open_time <= this.zoomEndTime!
      );
      console.log('  Después del filtro de zoom:', filteredKlines.length);
    }
    // Para rangos normales, mostrar TODOS los datos reales cargados
    // NO aplicar filtro de ventana deslizante a datos reales

    console.log('🔍 Mapeando', filteredKlines.length, 'klines a formato candlestick...');
    if (filteredKlines.length > 0) {
      const first = filteredKlines[0];
      console.log('  Primer kline:', {
        open_time: new Date(first.open_time).toISOString(),
        open: first.open,
        high: first.high,
        low: first.low,
        close: first.close
      });
    }

    const mapped = filteredKlines
      .filter(kline => kline.open_time && kline.open_time > 0) // Filtrar valores inválidos ANTES de mapear
      .map(kline => ({
        x: kline.open_time,
        o: parseFloat(String(kline.open)),
        h: parseFloat(String(kline.high)),
        l: parseFloat(String(kline.low)),
        c: parseFloat(String(kline.close))
      }));

    console.log('  Después del map:', mapped.length);
    if (mapped.length > 0) {
      console.log('  Primera vela mapeada:', mapped[0]);
    }

    const filtered = mapped.filter(candle =>
      candle.x && candle.x > 0 &&
      !isNaN(candle.o) && !isNaN(candle.h) && !isNaN(candle.l) && !isNaN(candle.c)
    );

    console.log('  Después del filter NaN:', filtered.length);
    if (filtered.length < mapped.length) {
      console.warn('⚠️  Se eliminaron', mapped.length - filtered.length, 'velas por valores NaN');
    }

    return filtered;
  }

  /**
   * Obtiene los datos de predicción en formato candlestick (velas moradas tenues)
   * IMPORTANTE: Filtra qué predicciones mostrar según el intervalo seleccionado
   * - 1 día o mayor: Mostrar 1h de predicción desde ahora
   * - 1h: Mostrar 1h de predicción desde ahora
   * - 30min: Mostrar 30min de predicción desde ahora
   * - 15min: Mostrar 15min de predicción desde ahora
   */
  private getPredictionCandlestickData(): any[] {
    console.log('🔮 getPredictionCandlestickData() iniciado');
    console.log('  this.predictions existe?', !!this.predictions);
    console.log('  this.predictions.length:', this.predictions?.length);

    if (!this.predictions || this.predictions.length === 0) {
      console.log('❌ No hay predicciones, retornando array vacío');
      return [];
    }

    let filteredPredictions = this.predictions;

    // Si hay zoom activo, filtrar por el rango de zoom
    if (this.isZoomed && this.zoomStartTime && this.zoomEndTime) {
      console.log('🔍 Zoom activo, filtrando predicciones...');
      filteredPredictions = this.predictions.filter(pred =>
        pred.close_time >= this.zoomStartTime! && pred.close_time <= this.zoomEndTime!
      );
      console.log('  Después del filtro de zoom:', filteredPredictions.length);
    } else {
      // Filtrar por intervalo seleccionado
      const timeRange = this.getSelectedTimeRangeOption();
      const now = Date.now();

      // Determinar cuántos minutos de predicción FUTURA mostrar según el intervalo
      let futurePredictionMinutes: number;

      if (timeRange.minutes >= 1440) {
        // 1 día o mayor: mostrar 1h de predicción futura
        futurePredictionMinutes = 60;
      } else if (timeRange.minutes >= 60) {
        // 1h: mostrar 1h de predicción futura
        futurePredictionMinutes = 60;
      } else if (timeRange.minutes >= 30) {
        // 30min: mostrar 30min de predicción futura
        futurePredictionMinutes = 30;
      } else {
        // 15min o menor: mostrar 15min de predicción futura
        futurePredictionMinutes = 15;
      }

      // Mostrar predicciones desde el inicio del rango de datos reales hasta ahora + predicción futura
      // Esto permite comparar las predicciones pasadas con los datos reales
      const predictionStartTime = now - (timeRange.minutes * 60 * 1000); // Mismo rango que datos reales
      const predictionEndTime = now + (futurePredictionMinutes * 60 * 1000); // + predicción futura

      console.log(`🔍 Filtrando predicciones para ${timeRange.label}`);
      console.log(`  Total predicciones cargadas: ${this.predictions.length}`);
      console.log(`  Datos reales: últimos ${timeRange.minutes} minutos`);
      console.log(`  Predicciones: ${timeRange.minutes} minutos pasados + ${futurePredictionMinutes} minutos futuros`);
      console.log(`  Desde: ${new Date(predictionStartTime).toISOString()}`);
      console.log(`  Hasta: ${new Date(predictionEndTime).toISOString()}`);
      console.log(`  Ahora: ${new Date(now).toISOString()}`);

      // IMPORTANTE: Filtrar predicciones que se superponen con el rango deseado
      // Una predicción se incluye si: open_time < predictionEndTime Y close_time > predictionStartTime
      filteredPredictions = this.predictions.filter(pred =>
        pred.open_time < predictionEndTime && pred.close_time > predictionStartTime
      );
      console.log(`  Predicciones después del filtro: ${filteredPredictions.length}`);

      if (filteredPredictions.length > 0) {
        const sorted = filteredPredictions.sort((a, b) => a.close_time - b.close_time);
        console.log(`  Primera predicción: open=${new Date(sorted[0].open_time).toISOString()}, close=${new Date(sorted[0].close_time).toISOString()}`);
        console.log(`  Última predicción: open=${new Date(sorted[sorted.length - 1].open_time).toISOString()}, close=${new Date(sorted[sorted.length - 1].close_time).toISOString()}`);
      }
    }

    console.log('🔍 Mapeando', filteredPredictions.length, 'predicciones a formato candlestick...');
    if (filteredPredictions.length > 0) {
      const first = filteredPredictions[0];
      console.log('  Primera predicción:', {
        open_time: new Date(first.open_time).toISOString(),
        open: first.open,
        high: first.high,
        low: first.low,
        close: first.close
      });
    }

    const mapped = filteredPredictions
      .filter(pred => pred.close_time && pred.close_time > 0) // Filtrar valores inválidos ANTES de mapear
      .map(pred => ({
        x: pred.close_time, // Usar close_time como X para distribuir las predicciones
        o: parseFloat(String(pred.open)),
        h: parseFloat(String(pred.high)),
        l: parseFloat(String(pred.low)),
        c: parseFloat(String(pred.close))
      }));

    console.log('  Después del map:', mapped.length);
    if (mapped.length > 0) {
      console.log('  Primera vela de predicción mapeada:', mapped[0]);
    }

    const filtered = mapped.filter(candle =>
      candle.x && candle.x > 0 &&
      !isNaN(candle.o) && !isNaN(candle.h) && !isNaN(candle.l) && !isNaN(candle.c)
    );

    console.log('  Después del filter NaN:', filtered.length);
    if (filtered.length < mapped.length) {
      console.warn('⚠️  Se eliminaron', mapped.length - filtered.length, 'velas de predicción por valores NaN');
    }

    return filtered;
  }

  /**
   * Obtiene la opción de rango de tiempo seleccionada
   */
  private getSelectedTimeRangeOption(): TimeRangeOption {
    return this.timeRanges.find(tr => tr.value === this.selectedTimeRange) || this.timeRanges[3];
  }

  /**
   * Genera el título del gráfico con fecha si es necesario
   */
  private getChartTitle(): string {
    const timeRange = this.getSelectedTimeRangeOption();

    // Para rangos >= 1 día, incluir la fecha en el título
    if (timeRange.minutes >= 1440) {
      const now = new Date();
      const dateStr = now.toLocaleDateString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
      });
      return `${this.selectedSymbol} - ${timeRange.label}: ${dateStr}`;
    } else {
      return `${this.selectedSymbol} - ${timeRange.label}`;
    }
  }

  /**
   * Inicia el intervalo de ping al servidor
   */
  private startPingInterval(): void {
    this.pingInterval = setInterval(() => {
      this.apiService.ping();
    }, 30000); // Cada 30 segundos
  }

  // ==================== Event Handlers ====================

  /**
   * Maneja el cambio de símbolo
   */
  async onSymbolChange(): Promise<void> {
    console.log('Símbolo cambiado a:', this.selectedSymbol);

    // Desuscribirse del símbolo anterior
    const previousSymbols = this.availableSymbols.map(s => s.symbol);
    this.apiService.unsubscribe(previousSymbols);

    // Suscribirse al nuevo símbolo
    this.apiService.subscribe([this.selectedSymbol]);

    // Recargar datos y esperar a que termine
    await this.loadInitialData();
  }

  /**
   * Maneja el cambio de rango de tiempo
   * Aplica zoom sobre los datos ya cargados en lugar de recargar
   */
  async onTimeRangeChange(): Promise<void> {
    console.log('Rango de tiempo cambiado a:', this.selectedTimeRange);

    const timeRange = this.getSelectedTimeRangeOption();
    const now = Date.now();

    if (timeRange.value === 'day') {
      // Para "Día": mostrar todos los datos (sin zoom)
      this.resetZoom();
    } else {
      // Para otros rangos: aplicar zoom
      // Calcular rango de zoom según el intervalo
      let zoomStart: number;
      let zoomEnd: number;

      if (timeRange.minutes >= 60) {
        // 1 Hora: desde (ahora - 1h) hasta (ahora + 1h) = 2h total
        zoomStart = now - (60 * 60 * 1000);
        zoomEnd = now + (60 * 60 * 1000);
      } else if (timeRange.minutes >= 30) {
        // 30 min: desde (ahora - 30min) hasta (ahora + 1h) = 1.5h total
        zoomStart = now - (30 * 60 * 1000);
        zoomEnd = now + (60 * 60 * 1000);
      } else {
        // 15 min: desde (ahora - 15min) hasta (ahora + 1h) = 1.25h total
        zoomStart = now - (15 * 60 * 1000);
        zoomEnd = now + (60 * 60 * 1000);
      }

      // Aplicar zoom
      this.previousTimeRange = null; // No guardar rango anterior
      this.zoomStartTime = zoomStart;
      this.zoomEndTime = zoomEnd;
      this.isZoomed = true;

      console.log(`📊 Aplicando zoom para ${timeRange.label}`);
      console.log(`  Desde: ${new Date(zoomStart).toISOString()}`);
      console.log(`  Hasta: ${new Date(zoomEnd).toISOString()}`);

      // Actualizar el chart con el zoom
      this.updateChart();
    }
  }

  /**
   * Recarga manualmente los datos
   */
  refreshData(): void {
    this.loadInitialData();
  }

  // ==================== Cleanup ====================

  /**
   * Limpia recursos
   */
  private cleanup(): void {
    // Cancelar subscripciones
    this.subscriptions.forEach(sub => sub.unsubscribe());

    // Detener ping interval
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }

    // Destruir chart
    if (this.chart) {
      this.chart.destroy();
    }

    // Desconectar WebSocket
    this.apiService.disconnectWebSocket();
  }
}
