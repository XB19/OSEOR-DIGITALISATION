import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GalerieService, Photo } from '../core/vie-interne.service';
import { IconComponent } from './icon.component';

/**
 * Bandeau photo défilant — la « mémoire » du groupe sur le tableau de bord.
 *
 * Défilement vertical continu, à la manière des murs de photos des sites
 * vitrines : les vignettes montent lentement en boucle, sans à-coups ni
 * flèches à cliquer. L'animation est portée par une transformation CSS
 * (`translate3d`), donc composée par le GPU : elle ne déclenche ni
 * recalcul de mise en page ni repeinture, et ne pèse pas sur le reste de
 * la page.
 *
 * Trois précautions, parce qu'un ornement ne doit jamais casser l'écran
 * qui l'accueille :
 *
 * - sans photo, le composant ne rend rien du tout — pas de cadre vide ;
 * - l'animation s'arrête au survol, pour laisser lire une légende ;
 * - `prefers-reduced-motion` la désactive entièrement, le bandeau
 *   redevenant une simple grille défilable.
 */
@Component({
  selector: 'app-galerie-defilante',
  imports: [CommonModule, RouterLink, IconComponent],
  template: `
  @if (photos().length) {
    <div class="carte galerie-carte anim-entree">
      <div class="entete">
        <h3><app-icon name="image" [size]="16"/> Mémoire du groupe</h3>
        <a routerLink="/galerie" class="tout">Voir tout</a>
      </div>

      <div class="hublot" [class.fige]="fige()"
           (mouseenter)="fige.set(true)" (mouseleave)="fige.set(false)">
        <div class="ruban" [style.animation-duration.s]="duree()">
          <!-- La liste est doublée : quand la première moitié a fini de
               défiler, la seconde occupe exactement la même position, et
               la boucle est invisible. -->
          @for (p of ruban(); track $index) {
            <figure class="vignette">
              <img [src]="p.miniature || p.image" [alt]="p.legende || 'Photo'"
                   loading="lazy" decoding="async"/>
              @if (p.legende) { <figcaption>{{ p.legende }}</figcaption> }
            </figure>
          }
        </div>
      </div>
    </div>
  }
  `,
  styles: [`
    .galerie-carte { padding: 1rem 1rem .8rem; display: flex; flex-direction: column; }
    .entete { display: flex; align-items: center; justify-content: space-between; margin-bottom: .7rem; }
    .entete h3 { margin: 0; display: flex; align-items: center; gap: .45rem; font-size: 1rem; }
    .entete h3 app-icon { color: var(--bleu); }
    .tout { font-size: .78rem; color: var(--bleu); font-weight: 600; }
    .tout:hover { text-decoration: underline; }

    /* Fenêtre fixe : c'est elle qui masque le ruban hors champ. */
    .hublot {
      position: relative;
      height: 320px;
      overflow: hidden;
      border-radius: 10px;
      /* Estompe le haut et le bas plutôt que de couper net les vignettes. */
      -webkit-mask-image: linear-gradient(to bottom, transparent, #000 8%, #000 92%, transparent);
      mask-image: linear-gradient(to bottom, transparent, #000 8%, #000 92%, transparent);
    }

    .ruban {
      display: flex;
      flex-direction: column;
      gap: .6rem;
      animation-name: defiler;
      animation-timing-function: linear;
      animation-iteration-count: infinite;
      will-change: transform;
    }

    /* -50 % : exactement la première moitié du ruban, celle qui est
       dupliquée — la boucle se referme sans saut visible. */
    @keyframes defiler {
      from { transform: translate3d(0, 0, 0); }
      to   { transform: translate3d(0, -50%, 0); }
    }

    .hublot.fige .ruban { animation-play-state: paused; }

    .vignette { position: relative; margin: 0; border-radius: 10px; overflow: hidden;
      flex-shrink: 0; background: #f1f5f9; }
    .vignette img { display: block; width: 100%; height: 150px; object-fit: cover;
      transition: transform var(--t); }
    .vignette:hover img { transform: scale(1.05); }
    .vignette figcaption {
      position: absolute; inset: auto 0 0 0; padding: .8rem .6rem .45rem;
      background: linear-gradient(transparent, rgba(15, 23, 42, .8));
      color: #fff; font-size: .74rem; line-height: 1.3;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }

    /* Accessibilité : pas de mouvement imposé à qui n'en veut pas. */
    @media (prefers-reduced-motion: reduce) {
      .ruban { animation: none; }
      .hublot { overflow-y: auto; -webkit-mask-image: none; mask-image: none; }
    }
  `],
})
export class GalerieDefilanteComponent implements OnInit, OnDestroy {
  photos = signal<Photo[]>([]);
  fige = signal(false);

  /** Nombre de vignettes chargées — au-delà, le bandeau n'apporte rien. */
  private static readonly MAX = 12;

  /** Secondes par vignette : lent, pour rester un fond et non une distraction. */
  private static readonly SECONDES_PAR_VIGNETTE = 4;

  constructor(private galerie: GalerieService) {}

  ngOnInit(): void {
    this.galerie.photos().subscribe({
      next: (r) => {
        const liste = (r.results ?? (r as any) ?? []) as Photo[];
        this.photos.set(liste.slice(0, GalerieDefilanteComponent.MAX));
      },
      // Un bandeau décoratif ne doit jamais faire échouer le tableau de
      // bord : en cas d'erreur, il disparaît simplement.
      error: () => this.photos.set([]),
    });
  }

  ngOnDestroy(): void { this.photos.set([]); }

  /** La liste doublée qui rend la boucle continue. */
  ruban(): Photo[] {
    const liste = this.photos();
    return liste.length ? [...liste, ...liste] : [];
  }

  duree(): number {
    return Math.max(this.photos().length, 1)
      * GalerieDefilanteComponent.SECONDES_PAR_VIGNETTE;
  }
}
