import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Salle } from '../core/models';
import { IconComponent } from './icon.component';

/**
 * Représentation visuelle d'une salle (EF-02) : places autour d'une table
 * + pictogrammes d'équipements, lisible d'un coup d'œil sans texte.
 */
@Component({
  selector: 'app-salle-visuelle',
  imports: [CommonModule, IconComponent],
  template: `
  <div class="salle-vis">
    <div class="plan">
      @for (p of places(); track p) {
        <span class="place" [style.transform]="positionPlace(p)"></span>
      }
      <div class="table"><span class="cap">{{ salle.capacite }}</span></div>
    </div>
    <div class="equip">
      @if (a('VIDEO_PROJECTEUR')) { <span class="pic" title="Vidéoprojecteur"><app-icon name="video" [size]="16"/></span> }
      @if (a('TABLEAU_BLANC')) { <span class="pic" title="Paper board / tableau"><app-icon name="presentation" [size]="16"/></span> }
      @if (a('POINTEUR_LASER')) { <span class="pic" title="Pointeur laser"><app-icon name="pointer" [size]="16"/></span> }
      @if (!salle.equipements?.length) { <small class="sans">Sans équipement</small> }
    </div>
  </div>
  `,
  styles: [`
    .salle-vis { display: flex; flex-direction: column; align-items: center; gap: .7rem; }
    .plan { position: relative; width: 160px; height: 118px; }
    .table { position: absolute; top: 39px; left: 40px; width: 80px; height: 40px;
      background: linear-gradient(135deg, var(--navy), var(--bleu)); border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 12px rgba(30,58,138,.3); }
    .table .cap { color: #fff; font-family: var(--police-titre); font-weight: 700; font-size: 1rem; }
    .place { position: absolute; top: 50%; left: 50%; width: 13px; height: 13px; margin: -6px;
      background: #cbd5e1; border: 2px solid #fff; border-radius: 50%; transform-origin: center;
      box-shadow: var(--ombre-sm); }
    .equip { display: flex; gap: .4rem; align-items: center; min-height: 28px; }
    .pic { width: 30px; height: 30px; border-radius: 8px; background: #eff6ff; color: var(--bleu-700);
      display: flex; align-items: center; justify-content: center; }
    .sans { color: var(--txt-3); font-size: .76rem; }
  `],
})
export class SalleVisuelleComponent {
  @Input({ required: true }) salle!: Salle;

  places(): number[] {
    const n = Math.min(this.salle.capacite || 0, 16);
    return Array.from({ length: n }, (_, i) => i);
  }
  positionPlace(i: number): string {
    const total = this.places().length || 1;
    const angle = (i / total) * 2 * Math.PI - Math.PI / 2;
    const x = Math.cos(angle) * 66;
    const y = Math.sin(angle) * 50;
    return `translate(${x}px, ${y}px)`;
  }
  a(code: string): boolean { return (this.salle.equipements || []).includes(code); }
}
