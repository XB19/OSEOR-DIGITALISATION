import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { IconComponent } from '../../shared/icon.component';
import { MODULES_MOYENS_GENERAUX, ModuleMetier } from '../../core/modules-metier';
import { GalerieDefilanteComponent } from '../../shared/galerie-defilante.component';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, RouterLink, IconComponent, GalerieDefilanteComponent],
  template: `
  <div class="tete anim-entree">
    <div>
      <h1>Bonjour {{ prenom() }} 👋</h1>
      <p class="sous">{{ stats()?.portee === 'groupe' ? 'Vue d\\'ensemble du groupe' : (stats()?.filiale || 'Votre espace personnel') }}</p>
    </div>
    <a class="btn cta" routerLink="/reserver"><app-icon name="plus"/> Réserver une salle</a>
  </div>

  @if (stats(); as s) {
    <div class="grille stagger">
      <div class="kpi">
        <div class="ic ic-bleu"><app-icon name="building"/></div>
        <div><div class="v">{{ s.nb_salles }}</div><div class="l">Salles actives</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-orange"><app-icon name="clock"/></div>
        <div><div class="v">{{ s.reservations_en_attente }}</div><div class="l">En attente</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-vert"><app-icon name="checkCircle"/></div>
        <div><div class="v">{{ s.reservations_validees }}</div><div class="l">Validées</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-navy"><app-icon name="calendar"/></div>
        <div><div class="v">{{ s.taux_occupation_7j }}%</div><div class="l">Occupation (7j)</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-bleu"><app-icon name="users"/></div>
        <div><div class="v">{{ s.audiences_en_cours }}</div><div class="l">Audiences en cours</div></div>
      </div>
      @if (s.nb_filiales !== undefined) {
        <div class="kpi">
          <div class="ic ic-navy"><app-icon name="mapPin"/></div>
          <div><div class="v">{{ s.nb_filiales }}</div><div class="l">Filiales</div></div>
        </div>
      }
    </div>

    <div class="avec-galerie">
     <div class="colonne-principale">
      <div class="deux">
      <div class="carte anim-entree">
        <h3>Salles les plus demandées</h3>
        @if (s.salles_plus_demandees?.length) {
          <div class="barres">
            @for (sd of s.salles_plus_demandees; track sd.salle) {
              <div class="barre-ligne">
                <span class="nom">{{ sd.salle }}</span>
                <div class="piste"><div class="rempli" [style.width.%]="largeur(sd.reservations)"></div></div>
                <span class="num">{{ sd.reservations }}</span>
              </div>
            }
          </div>
        } @else { <div class="vide">Aucune donnée pour le moment</div> }
      </div>

      <div class="carte anim-entree">
        <h3>Accès rapides</h3>
        <div class="actions">
          <a class="action" routerLink="/calendrier"><app-icon name="calendar"/> Voir le calendrier</a>
          <a class="action" routerLink="/recurrence"><app-icon name="repeat"/> Réservation récurrente</a>
          @if (auth.aRole('SECRETAIRE','ADMINISTRATEUR')) {
            <a class="action" routerLink="/validation"><app-icon name="checkCircle"/> Demandes à valider</a>
          }
          <a class="action" routerLink="/audiences"><app-icon name="users"/> Gérer les audiences</a>
        </div>
      </div>
    </div>

      @if (outilsVisibles().length) {
        <div class="carte anim-entree outils-carte">
          <h3>Vos outils</h3>
          <div class="outils-grille">
            @for (o of outilsVisibles(); track o.lien) {
              <a class="outil" [routerLink]="o.lien"><app-icon [name]="o.icone" [size]="18"/> {{ o.libelle }}</a>
            }
          </div>
        </div>
      }
     </div>

     <aside class="colonne-galerie">
       <app-galerie-defilante/>
     </aside>
    </div>
  } @else {
    <div class="grille">
      @for (i of [1,2,3,4]; track i) { <div class="kpi"><div class="skeleton" style="width:100%;height:54px"></div></div> }
    </div>
  }
  `,
  styles: [`
    .tete { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.4rem; }
    .sous { color: var(--txt-2); margin-top: -.3rem; }
    .grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem; margin-bottom: 1.4rem; }
    .kpi { background: #fff; border: 1px solid var(--bord); border-radius: var(--r);
      padding: 1.1rem 1.2rem; box-shadow: var(--ombre); display: flex; align-items: center; gap: 1rem;
      transition: transform var(--t), box-shadow var(--t); }
    .kpi:hover { transform: translateY(-3px); box-shadow: var(--ombre-md); }
    .ic { width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0; color: #fff; }
    .ic-navy { background: var(--navy); } .ic-bleu { background: var(--bleu); }
    .ic-orange { background: var(--accent); } .ic-vert { background: var(--vert); }
    .kpi .v { font-family: var(--police-titre); font-size: 1.7rem; font-weight: 700; color: var(--navy); line-height: 1; }
    .kpi .l { font-size: .8rem; color: var(--txt-2); margin-top: .25rem; }
    /* Colonne latérale pour la galerie. Elle vient APRÈS le contenu dans
       le flux : sur mobile, le tableau de bord reste en tête et le
       bandeau photo passe dessous, sans jamais repousser l'essentiel. */
    .avec-galerie { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 1rem; align-items: start; }
    .colonne-principale { min-width: 0; }
    .colonne-galerie { position: sticky; top: 1rem; }
    @media (max-width: 1100px) {
      .avec-galerie { grid-template-columns: 1fr; }
      .colonne-galerie { position: static; }
    }
    .deux { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 820px) { .deux { grid-template-columns: 1fr; } }
    .barres { display: flex; flex-direction: column; gap: .8rem; margin-top: .8rem; }
    .barre-ligne { display: grid; grid-template-columns: 1fr 2fr auto; align-items: center; gap: .8rem; }
    .barre-ligne .nom { font-size: .85rem; font-weight: 500; }
    .piste { height: 9px; background: #eef2f7; border-radius: 999px; overflow: hidden; }
    .rempli { height: 100%; background: linear-gradient(90deg, var(--bleu), var(--navy));
      border-radius: 999px; animation: grow .8s cubic-bezier(.2,.8,.2,1) both; }
    @keyframes grow { from { width: 0 !important; } }
    .barre-ligne .num { font-weight: 700; color: var(--navy); font-size: .9rem; }
    .actions { display: flex; flex-direction: column; gap: .5rem; margin-top: .6rem; }
    .action { display: flex; align-items: center; gap: .7rem; padding: .75rem .9rem; border-radius: 10px;
      border: 1px solid var(--bord); color: var(--txt); font-weight: 500; font-size: .9rem;
      transition: background var(--t), border-color var(--t), transform var(--t); }
    .action app-icon { color: var(--bleu); }
    .action:hover { background: #f8fafc; border-color: var(--bleu); transform: translateX(3px); }

    .outils-carte { margin-top: 1rem; }
    .outils-grille { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
      gap: .6rem; margin-top: .8rem; }
    .outil { display: flex; align-items: center; gap: .6rem; padding: .7rem .9rem; border-radius: 10px;
      border: 1px solid var(--bord); color: var(--txt); font-weight: 500; font-size: .85rem;
      transition: background var(--t), border-color var(--t), transform var(--t); }
    .outil app-icon { color: var(--bleu); flex-shrink: 0; }
    .outil:hover { background: #f8fafc; border-color: var(--bleu); transform: translateY(-2px); }
  `],
})
export class DashboardComponent implements OnInit {
  stats = signal<any | null>(null);
  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void { this.api.stats().subscribe((s) => this.stats.set(s)); }

  outilsVisibles(): ModuleMetier[] {
    return MODULES_MOYENS_GENERAUX.filter((m) => !m.roles || this.auth.aRole(...m.roles));
  }

  prenom(): string {
    const u = this.auth.utilisateur();
    return u?.first_name || u?.nom_complet || '';
  }
  largeur(n: number): number {
    const max = Math.max(...(this.stats()?.salles_plus_demandees || []).map((x: any) => x.reservations), 1);
    return Math.round((n / max) * 100);
  }
}
