import { Component, effect, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DialogueService } from '../core/dialogue.service';

/**
 * Boîte de dialogue globale (remplace window.prompt()). Rendue une seule
 * fois dans ShellComponent, pilotée par DialogueService.demanderMotif().
 */
@Component({
  selector: 'app-dialogue',
  imports: [FormsModule],
  template: `
  @if (service.demande(); as d) {
    <div class="fond" (click)="annuler()">
      <div class="boite anim-entree" (click)="$event.stopPropagation()">
        <h3>{{ d.titre }}</h3>
        @if (d.message) { <p class="message">{{ d.message }}</p> }
        @if (!d.sansTexte) {
          <textarea [(ngModel)]="valeur" rows="3" [placeholder]="d.placeholder || ''"
                    (keydown.enter)="$event.stopPropagation()"></textarea>
          @if (erreurVide) { <div class="erreur">Ce champ est obligatoire.</div> }
        }
        <div class="boutons">
          <button class="btn secondaire" (click)="annuler()">Annuler</button>
          <button class="btn" [class.rouge]="d.dangereux" [class.vert]="!d.dangereux" (click)="confirmer()">
            {{ d.libelleConfirmer || 'Confirmer' }}
          </button>
        </div>
      </div>
    </div>
  }
  `,
  styles: [`
    .fond { position: fixed; inset: 0; background: rgba(15,23,42,.4); z-index: 200;
      display: flex; align-items: center; justify-content: center; }
    .boite { background: #fff; border-radius: var(--r, 12px); box-shadow: var(--ombre-lg);
      padding: 1.4rem 1.6rem; min-width: 340px; max-width: 460px; width: calc(100vw - 2.4rem); }
    .boite h3 { margin: 0 0 .4rem; }
    .message { font-size: .85rem; color: var(--txt-2); margin: 0 0 .8rem; }
    textarea { width: 100%; border: 1px solid var(--bord); border-radius: 8px;
      padding: .6rem .7rem; font-size: .87rem; font-family: inherit; resize: vertical; }
    .erreur { color: var(--rouge); font-size: .78rem; margin-top: .3rem; }
    .boutons { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1rem; }
  `],
})
export class DialogueComponent {
  service = inject(DialogueService);
  valeur = '';
  erreurVide = false;

  constructor() {
    effect(() => {
      if (this.service.demande()) {
        this.valeur = '';
        this.erreurVide = false;
      }
    });
  }

  confirmer(): void {
    const d = this.service.demande();
    if (d?.obligatoire && !this.valeur.trim()) {
      this.erreurVide = true;
      return;
    }
    this.service.confirmer(this.valeur.trim());
  }

  annuler(): void {
    this.service.annuler();
  }
}
