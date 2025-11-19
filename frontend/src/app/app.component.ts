import { Component } from '@angular/core';
import { CryptoChartComponent } from './components/crypto-chart/crypto-chart.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CryptoChartComponent],
  template: '<app-crypto-chart></app-crypto-chart>',
  styles: [`
    :host {
      display: block;
      min-height: 100vh;
      background: linear-gradient(135deg, #494949 0%, #1F1F1F 100%);
      padding: 20px;
    }

    @media (max-width: 768px) {
      :host {
        padding: 10px;
      }
    }
  `]
})
export class AppComponent {
  title = 'Binance Crypto Analysis';
}
