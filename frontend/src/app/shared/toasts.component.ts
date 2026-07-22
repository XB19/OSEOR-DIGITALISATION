import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService } from '../core/toast.service';
import { IconComponent } from './icon.component';

@Component({
  selector: 'app-toasts',
  imports: [CommonModule, IconComponent],
  template: `
  <div class="pile" aria-live="polite">
    @for (t of toasts.toasts(); track t.id) {
      <div class="toast" [class]="'t-' + t.type.toLowerCase()">
        <div class="ic"><app-icon [name]="icone(t.type)" [size]="18"/></div>
        <div class="corps">
          <div class="titre">{{ t.titre }}</div>
          <div class="msg">{{ t.message }}</div>
        </div>
        <button class="fermer" (click)="toasts.retirer(t.id)" aria-label="Fermer">
          <app-icon name="close" [size]="14"/>
        </button>
        <div class="barre"></div>
      </div>
    }
  </div>
  `,
  styles: [`
    .pile { position: fixed; top: 1.2rem; right: 1.2rem; z-index: 1000;
      display: flex; flex-direction: column; gap: .7rem; max-width: 360px; width: calc(100vw - 2.4rem); }
    .toast {
      position: relative; background: #fff; border: 1px solid var(--bord);
      border-left: 4px solid var(--bleu); border-radius: 12px; box-shadow: var(--ombre-lg);
      padding: .85rem 1rem; display: flex; align-items: flex-start; gap: .7rem; overflow: hidden;
      animation: toastEntree .35s cubic-bezier(.2, .8, .2, 1) both;
    }
    .toast.t-success { border-left-color: var(--vert); }
    .toast.t-warning { border-left-color: var(--accent); }
    .toast.t-error { border-left-color: var(--rouge); }
    .ic { width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center; background: #eff6ff; color: var(--bleu-700); }
    .t-success .ic { background: var(--vert-bg); color: #027a48; }
    .t-warning .ic { background: var(--orange-bg); color: #c2410c; }
    .t-error .ic { background: var(--rouge-bg); color: #b91c1c; }
    .corps { flex: 1; min-width: 0; }
    .titre { font-weight: 700; font-size: .88rem; color: var(--txt); }
    .msg { font-size: .82rem; color: var(--txt-2); margin-top: 1px; }
    .fermer { background: none; border: none; cursor: pointer; color: var(--txt-3);
      padding: 2px; border-radius: 6px; transition: background var(--t); flex-shrink: 0; }
    .fermer:hover { background: #f1f5f9; color: var(--txt); }
    .barre { position: absolute; bottom: 0; left: 0; height: 3px; background: var(--bleu);
      width: 100%; transform-origin: left; animation: toastBarre 6s linear forwards; }
    .t-success .barre { background: var(--vert); }
    .t-warning .barre { background: var(--accent); }
    .t-error .barre { background: var(--rouge); }
    @keyframes toastEntree { from { opacity: 0; transform: translateX(40px); } to { opacity: 1; transform: none; } }
    @keyframes toastBarre { from { transform: scaleX(1); } to { transform: scaleX(0); } }
    @media (prefers-reduced-motion: reduce) {
      .toast { animation: none; } .barre { animation: none; display: none; }
    }
  `],
})
export class ToastsComponent {
  toasts = inject(ToastService);
  icone(type: string): string {
    return type === 'SUCCESS' ? 'checkCircle'
      : type === 'ERROR' ? 'close'
      : type === 'WARNING' ? 'bell' : 'bell';
  }
}
