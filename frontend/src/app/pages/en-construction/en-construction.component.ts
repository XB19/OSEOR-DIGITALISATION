import { Component } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-en-construction',
  imports: [IconComponent],
  template: `
  <div class="carte anim-entree bloc">
    <app-icon name="clock" [size]="40"/>
    <h2>{{ titre }}</h2>
    <p>Ce module est en cours de développement et sera bientôt disponible.</p>
  </div>
  `,
  styles: [`
    .bloc {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      text-align: center; padding: 4rem 2rem; gap: 1rem; color: var(--txt-2);
    }
    .bloc app-icon { color: var(--bleu); opacity: .55; }
    .bloc h2 { color: var(--navy); margin: 0; }
    .bloc p { max-width: 420px; margin: 0; font-size: .9rem; }
  `],
})
export class EnConstructionComponent {
  titre: string;

  constructor(route: ActivatedRoute) {
    this.titre = route.snapshot.data['titre'] || 'Module';
  }
}
