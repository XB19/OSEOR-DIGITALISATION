import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IconComponent } from '../../shared/icon.component';
import { ToastService } from '../../core/toast.service';
import { AuthService } from '../../core/auth.service';
import { ApiService } from '../../core/api.service';
import { ActivatedRoute } from '@angular/router';
import {
  BonSortie, Caisse, CaisseService, MouvementCaisse, ReglesBon,
} from '../../core/gestion.service';

/**
 * Caisses et bons de sortie.
 *
 * Deux idées doivent se lire sans explication :
 *
 * - le solde est **la somme du registre**, pas un chiffre saisi — d'où le
 *   registre affiché à côté du solde ;
 * - une alimentation **exige une preuve**, et le formulaire le dit avant
 *   que l'utilisateur ne s'y heurte.
 */
@Component({
  selector: 'app-caisse',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <div class="tete anim-entree">
    <div>
      <h1>Caisses</h1>
      <p class="sous">Mouvements d'espèces et bons de sortie</p>
    </div>
    @if (peutDemander()) {
      <button class="btn cta" (click)="ouvrirBon()">
        <app-icon name="plus"/> Demander une sortie
      </button>
    }
  </div>

  @if (caisses().length) {
    <div class="grille stagger">
      @for (c of caisses(); track c.id) {
        <article class="kpi" [class.actif]="selection()?.id === c.id"
                 (click)="choisir(c)">
          <div class="ic ic-navy"><app-icon name="wallet"/></div>
          <div>
            <div class="v">{{ montant(c.solde) }}</div>
            <div class="l">{{ c.nom }} · {{ c.filiale_nom }}</div>
            @if (c.detenteur_nom) { <div class="detail">Tenue par {{ c.detenteur_nom }}</div> }
          </div>
        </article>
      }
    </div>
  } @else {
    <div class="carte vide">Aucune caisse ne vous est accessible.</div>
  }

  <div class="onglets">
    <button [class.actif]="onglet() === 'registre'" (click)="onglet.set('registre')">
      Registre
    </button>
    <button [class.actif]="onglet() === 'bons'" (click)="onglet.set('bons')">
      Bons de sortie
    </button>
    @if (aAutoriser().length) {
      <button [class.actif]="onglet() === 'autoriser'" (click)="onglet.set('autoriser')">
        À autoriser <span class="pastille">{{ aAutoriser().length }}</span>
      </button>
    }
  </div>

  @if (onglet() === 'registre') {
    <div class="carte anim-entree">
      @if (selection(); as c) {
        <div class="entete-registre">
          <div>
            <h3>{{ c.nom }}</h3>
            <p class="sous">
              Le solde est la somme des écritures ci-dessous, jamais un
              chiffre saisi.
            </p>
          </div>
          @if (peutTenir(c)) {
            <div class="boutons">
              <button class="btn cta petit" (click)="alimenterOuvert.set(true)">
                <app-icon name="plus" [size]="14"/> Alimenter
              </button>
              <button class="btn fantome petit" (click)="correctionOuverte.set(true)">
                Corriger un écart
              </button>
            </div>
          }
        </div>

        @if (registre().length) {
          <table class="tableau">
            <thead>
              <tr><th>Date</th><th>Nature</th><th>Montant</th><th>Motif</th><th>Par</th></tr>
            </thead>
            <tbody>
              @for (m of registre(); track m.id) {
                <tr>
                  <td>{{ m.date_operation | date: 'dd/MM/yyyy' }}</td>
                  <td>
                    {{ m.type_libelle }}
                    @if (m.reference) { <div class="detail">réf. {{ m.reference }}</div> }
                  </td>
                  <td class="num" [class.credit]="+m.montant > 0" [class.debit]="+m.montant < 0">
                    {{ +m.montant > 0 ? '+' : '' }}{{ montant(m.montant) }}
                  </td>
                  <td class="detail">{{ m.motif }}</td>
                  <td class="detail">{{ m.cree_par_nom }}</td>
                </tr>
              }
            </tbody>
          </table>
        } @else {
          <div class="vide">Aucun mouvement enregistré.</div>
        }
      } @else {
        <div class="vide">Choisissez une caisse ci-dessus.</div>
      }
    </div>
  }

  @if (onglet() === 'bons' || onglet() === 'autoriser') {
    <div class="carte anim-entree">
      @if (bonsAffiches().length) {
        <table class="tableau">
          <thead>
            <tr>
              <th>Référence</th><th>Objet</th><th>Montant</th>
              <th>Demandeur</th><th>Statut</th><th></th>
            </tr>
          </thead>
          <tbody>
            @for (b of bonsAffiches(); track b.id) {
              <tr>
                <td class="mono">{{ b.reference }}</td>
                <td>
                  {{ b.objet }}
                  <div class="detail">
                    {{ b.type_libelle }}
                    @if (b.moyen_libelle) { · {{ b.moyen_libelle }} }
                    @if (b.destinataire_nom) { · adressé à {{ b.destinataire_nom }} }
                  </div>
                </td>
                <td class="num">
                  {{ montant(b.montant) }}
                  @if (+b.montant_rendu > 0) {
                    <div class="detail">{{ montant(b.montant_rendu) }} rendus</div>
                  }
                </td>
                <td>{{ b.demandeur_nom }}</td>
                <td><span class="etat" [class]="'etat-' + b.statut.toLowerCase()">{{ b.statut_libelle }}</span></td>
                <td class="actions-ligne">
                  @if (b.statut === 'EN_ATTENTE' && b.destinataire === moi()) {
                    <button class="btn petit vert" (click)="deciderBon(b, true)">Autoriser</button>
                    <button class="btn petit rouge" (click)="deciderBon(b, false)">Refuser</button>
                  }
                  @if (b.statut === 'AUTORISE' && peutDecaisser()) {
                    <button class="btn petit cta" (click)="payer(b)">Décaisser</button>
                  }
                  @if (b.statut === 'PAYE') {
                    <button class="lien" (click)="ouvrirRetour(b)">Rendre la monnaie</button>
                    @if (b.document) {
                      <a class="lien" [href]="pdf(b)" target="_blank">PDF</a>
                    }
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      } @else {
        <div class="vide">Aucun bon de sortie.</div>
      }
    </div>
  }

  @if (alimenterOuvert()) {
    <div class="voile" (click)="alimenterOuvert.set(false)">
      <div class="modale anim-entree" (click)="$event.stopPropagation()">
        <h3>Alimenter la caisse</h3>
        <p class="encart">
          Une alimentation exige une preuve : joignez le chèque ou le reçu,
          ou indiquez la référence de la transaction. Sans elle, l'écriture
          est refusée.
        </p>
        <label>Montant</label>
        <input type="number" [(ngModel)]="montantSaisi" min="1"/>
        <label>Référence (chèque, virement…)</label>
        <input [(ngModel)]="reference" placeholder="CHQ-00123"/>
        <label>Justificatif</label>
        <input type="file" (change)="choisirFichier($event)"/>
        <label>Motif</label>
        <input [(ngModel)]="motifSaisi"/>
        <div class="pied">
          <button class="btn fantome" (click)="alimenterOuvert.set(false)">Annuler</button>
          <button class="btn cta" (click)="alimenter()">Enregistrer</button>
        </div>
      </div>
    </div>
  }

  @if (correctionOuverte()) {
    <div class="voile" (click)="correctionOuverte.set(false)">
      <div class="modale anim-entree" (click)="$event.stopPropagation()">
        <h3>Corriger un écart</h3>
        <p class="encart">
          L'écart s'inscrit au registre par une écriture signée — négative
          s'il manque de l'argent. L'historique n'est jamais retouché.
        </p>
        <label>Montant (négatif s'il manque)</label>
        <input type="number" [(ngModel)]="montantSaisi"/>
        <label>Motif</label>
        <input [(ngModel)]="motifSaisi" placeholder="Écart constaté au comptage"/>
        <div class="pied">
          <button class="btn fantome" (click)="correctionOuverte.set(false)">Annuler</button>
          <button class="btn cta" (click)="corriger()">Enregistrer</button>
        </div>
      </div>
    </div>
  }

  @if (bonOuvert()) {
    <div class="voile" (click)="bonOuvert.set(false)">
      <div class="modale anim-entree" (click)="$event.stopPropagation()">
        <h3>Demander une sortie de caisse</h3>

        <label>Caisse</label>
        <select [(ngModel)]="caisseChoisie">
          @for (c of caisses(); track c.id) {
            <option [value]="c.id">{{ c.nom }} — {{ montant(c.solde) }}</option>
          }
        </select>

        <label>Type de dépense</label>
        <select [(ngModel)]="typeDepense">
          <option value="AUTRE">Autre dépense</option>
          <option value="TRANSPORT">Transport</option>
        </select>

        @if (typeDepense === 'TRANSPORT') {
          <label>Moyen</label>
          <select [(ngModel)]="moyenTransport">
            <option value="TAXI">Taxi</option>
            <option value="MOTO">Moto</option>
            <option value="GOZEM">Gozem</option>
          </select>
          <p class="encart">
            @if (justificatifExige()) {
              Gozem conserve l'historique des courses : le justificatif est
              obligatoire.
            } @else {
              Une course en taxi ou à moto se paie sans autorisation
              préalable.
            }
          </p>
          @if (justificatifExige()) {
            <label>Justificatif</label>
            <input type="file" (change)="choisirFichier($event)"/>
          }
        }

        <label>Objet</label>
        <input [(ngModel)]="objet" placeholder="Fournitures de bureau"/>

        <label>Montant</label>
        <input type="number" [(ngModel)]="montantSaisi" min="1"
               (ngModelChange)="montantChange()"/>

        @if (typeDepense !== 'TRANSPORT') {
          <label>Adressé à (personne qui autorise)</label>
          <select [(ngModel)]="destinataire">
            <option [ngValue]="null">— choisir —</option>
            @for (p of approbateursAdmis(); track p.id) {
              <option [ngValue]="p.id">{{ p.nom_complet }} — {{ p.role_libelle }}</option>
            }
          </select>
          @if (regles(); as r) {
            <p class="encart">
              @if (exigeDirection()) {
                Au-delà de {{ montant(r.seuil_direction) }}, seule la
                direction peut autoriser : la liste est réduite en
                conséquence.
              } @else {
                Au-delà de {{ montant(r.seuil_direction) }}, seule la
                direction pourra autoriser. En deçà, un chef de service
                suffit.
              }
            </p>
          }
        }

        <div class="pied">
          <button class="btn fantome" (click)="bonOuvert.set(false)">Annuler</button>
          <button class="btn cta" (click)="deposerBon()">Envoyer</button>
        </div>
      </div>
    </div>
  }

  @if (retourOuvert(); as b) {
    <div class="voile" (click)="retourOuvert.set(null)">
      <div class="modale anim-entree" (click)="$event.stopPropagation()">
        <h3>Retour en caisse</h3>
        <p class="encart">
          {{ montant(b.montant_paye) }} sont sortis pour ce bon. Ce qui n'a
          pas été dépensé revient en caisse.
        </p>
        <label>Montant rendu</label>
        <input type="number" [(ngModel)]="montantSaisi" min="1"/>
        <div class="pied">
          <button class="btn fantome" (click)="retourOuvert.set(null)">Annuler</button>
          <button class="btn cta" (click)="rendre(b)">Enregistrer</button>
        </div>
      </div>
    </div>
  }
  `,
  styles: [`
    .tete { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.4rem; }
    .sous { color: var(--txt-2); margin-top: -.3rem; font-size: .88rem; }
    .grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem; margin-bottom: 1.2rem; }
    .kpi { background: #fff; border: 1px solid var(--bord); border-radius: var(--r);
      padding: 1rem 1.1rem; box-shadow: var(--ombre); display: flex; align-items: center;
      gap: .9rem; cursor: pointer; transition: border-color var(--t), transform var(--t); }
    .kpi:hover { transform: translateY(-2px); }
    .kpi.actif { border-color: var(--bleu); box-shadow: var(--ombre-md); }
    .ic { width: 42px; height: 42px; border-radius: 11px; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0; color: #fff; }
    .ic-navy { background: var(--navy); }
    .kpi .v { font-family: var(--police-titre); font-size: 1.35rem; font-weight: 700;
      color: var(--navy); line-height: 1; }
    .kpi .l { font-size: .78rem; color: var(--txt-2); margin-top: .2rem; }

    .onglets { display: flex; gap: .4rem; margin-bottom: 1rem; border-bottom: 1px solid var(--bord); }
    .onglets button { background: none; border: none; padding: .7rem 1rem; cursor: pointer;
      font-size: .9rem; font-weight: 500; color: var(--txt-2); border-bottom: 2px solid transparent; }
    .onglets button.actif { color: var(--navy); border-bottom-color: var(--bleu); }
    .pastille { background: var(--accent); color: #fff; border-radius: 999px;
      padding: .05rem .4rem; font-size: .7rem; margin-left: .3rem; }

    .entete-registre { display: flex; justify-content: space-between; align-items: flex-start;
      gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .entete-registre h3 { margin: 0; }
    .boutons { display: flex; gap: .5rem; }

    .tableau { width: 100%; border-collapse: collapse; font-size: .88rem; }
    .tableau th { text-align: left; padding: .6rem .5rem; color: var(--txt-2);
      font-weight: 600; font-size: .76rem; text-transform: uppercase;
      border-bottom: 1px solid var(--bord); }
    .tableau td { padding: .65rem .5rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    .tableau .num { font-weight: 700; color: var(--navy); white-space: nowrap; }
    .mono { font-family: monospace; font-size: .82rem; }
    .detail { font-size: .76rem; color: var(--txt-2); margin-top: .12rem; }
    .credit { color: var(--vert); } .debit { color: #b42318; }

    .etat { padding: .2rem .55rem; border-radius: 999px; font-size: .74rem; font-weight: 600; }
    .etat-en_attente { background: #fef3c7; color: #92400e; }
    .etat-autorise { background: #dbeafe; color: #1e40af; }
    .etat-paye { background: #dcfce7; color: #166534; }
    .etat-refuse { background: #fee2e2; color: #991b1b; }
    .etat-annule { background: #f1f5f9; color: #475569; }

    .actions-ligne { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
    .btn.petit { padding: .3rem .7rem; font-size: .78rem; }
    .btn.vert { background: var(--vert); color: #fff; }
    .btn.rouge { background: #b42318; color: #fff; }
    .btn.fantome { background: none; border: 1px solid var(--bord); color: var(--txt); }
    .lien { background: none; border: none; color: var(--bleu); cursor: pointer;
      font-size: .8rem; text-decoration: underline; padding: 0; }

    .vide { text-align: center; color: var(--txt-2); padding: 2rem 1rem; font-size: .9rem; }
    .voile { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex;
      align-items: center; justify-content: center; z-index: 60; padding: 1rem; }
    .modale { background: #fff; border-radius: var(--r); padding: 1.5rem; width: 100%;
      max-width: 460px; max-height: 90vh; overflow-y: auto; box-shadow: var(--ombre-md); }
    .modale h3 { margin: 0 0 1rem; color: var(--navy); }
    .modale label { display: block; font-size: .8rem; font-weight: 600; color: var(--txt-2);
      margin: .8rem 0 .3rem; }
    .modale input, .modale select, .modale textarea { width: 100%; padding: .6rem .7rem;
      border: 1px solid var(--bord); border-radius: 8px; font-size: .9rem; font-family: inherit; }
    .encart { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
      padding: .7rem .8rem; font-size: .82rem; color: #1e40af; margin: .7rem 0 0; line-height: 1.5; }
    .pied { display: flex; justify-content: flex-end; gap: .6rem; margin-top: 1.4rem; }
  `],
})
export class CaisseComponent implements OnInit {
  caisses = signal<Caisse[]>([]);
  selection = signal<Caisse | null>(null);
  registre = signal<MouvementCaisse[]>([]);
  bons = signal<BonSortie[]>([]);
  aAutoriser = signal<BonSortie[]>([]);
  regles = signal<ReglesBon | null>(null);
  approbateurs = signal<any[]>([]);

  onglet = signal<'registre' | 'bons' | 'autoriser'>('registre');
  alimenterOuvert = signal(false);
  correctionOuverte = signal(false);
  bonOuvert = signal(false);
  retourOuvert = signal<BonSortie | null>(null);

  montantSaisi = 0;
  motifSaisi = '';
  reference = '';
  objet = '';
  typeDepense = 'AUTRE';
  moyenTransport = 'TAXI';
  destinataire: number | null = null;
  caisseChoisie: number | null = null;
  private fichier: File | null = null;

  constructor(
    private service: CaisseService,
    private api: ApiService,
    private toast: ToastService,
    private route: ActivatedRoute,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    // Une notification de bon renvoie ici : c'est le bon qu'on vient voir,
    // pas le registre de la caisse.
    if (this.route.snapshot.queryParamMap.get('id')) this.onglet.set('bons');

    this.charger();
    this.service.regles().subscribe((r) => this.regles.set(r));
  }

  charger(): void {
    this.service.caisses().subscribe((r) => {
      const liste = (r.results ?? (r as any) ?? []) as Caisse[];
      this.caisses.set(liste);
      if (liste.length && !this.selection()) this.choisir(liste[0]);
    });
    this.service.bons().subscribe(
      (r) => this.bons.set((r.results ?? (r as any) ?? []) as BonSortie[]));
    this.service.aAutoriser().subscribe((b) => this.aAutoriser.set(b));
  }

  choisir(c: Caisse): void {
    this.selection.set(c);
    this.caisseChoisie = c.id;
    this.service.registre(c.id).subscribe((m) => this.registre.set(m));
  }

  moi(): number | undefined { return this.auth.utilisateur()?.id; }

  peutTenir(c: Caisse): boolean {
    return this.auth.aRole('DIRECTEUR', 'ADMINISTRATEUR', 'COMPTABLE')
      || c.detenteur === this.moi();
  }

  peutDecaisser(): boolean {
    const c = this.selection();
    return !!c && this.peutTenir(c);
  }

  peutDemander(): boolean { return true; }

  justificatifExige(): boolean {
    return this.typeDepense === 'TRANSPORT'
      && (this.regles()?.moyens_avec_justificatif ?? []).includes(this.moyenTransport);
  }

  bonsAffiches(): BonSortie[] {
    return this.onglet() === 'autoriser' ? this.aAutoriser() : this.bons();
  }

  montant(valeur: string): string {
    const n = parseFloat(valeur);
    if (Number.isNaN(n)) return '—';
    return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' F';
  }

  pdf(b: BonSortie): string { return this.service.urlPdf(b.id); }

  choisirFichier(evenement: Event): void {
    this.fichier = (evenement.target as HTMLInputElement).files?.[0] ?? null;
  }

  private reinitialiser(): void {
    this.montantSaisi = 0;
    this.motifSaisi = this.reference = this.objet = '';
    this.fichier = null;
    this.destinataire = null;
  }

  alimenter(): void {
    const c = this.selection();
    if (!c) return;

    this.service.alimenter(c.id, {
      montant: String(this.montantSaisi),
      reference: this.reference,
      motif: this.motifSaisi,
      justificatif: this.fichier,
    }).subscribe({
      next: () => {
        this.alimenterOuvert.set(false);
        this.reinitialiser();
        this.toast.succes('Caisse alimentée.');
        this.charger();
        this.choisir(c);
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Alimentation refusée.'),
    });
  }

  corriger(): void {
    const c = this.selection();
    if (!c) return;

    this.service.corriger(c.id, String(this.montantSaisi), this.motifSaisi).subscribe({
      next: () => {
        this.correctionOuverte.set(false);
        this.reinitialiser();
        this.toast.succes('Écart consigné au registre.');
        this.charger();
        this.choisir(c);
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Correction refusée.'),
    });
  }

  ouvrirBon(): void {
    this.reinitialiser();
    this.typeDepense = 'AUTRE';
    this.moyenTransport = 'TAXI';
    this.caisseChoisie = this.selection()?.id ?? this.caisses()[0]?.id ?? null;
    this.chargerApprobateurs();
    this.bonOuvert.set(true);
  }

  private chargerApprobateurs(): void {
    this.api.utilisateurs().subscribe({
      next: (r: any) => this.approbateurs.set(r.results ?? []),
      error: () => this.approbateurs.set([]),
    });
  }

  /**
   * Un montant relevé peut rendre le destinataire déjà choisi
   * insuffisant : on efface alors la sélection plutôt que de laisser
   * partir un bon que le serveur refusera.
   */
  montantChange(): void {
    if (this.destinataire === null) return;
    const admis = this.approbateursAdmis();
    if (!admis.some((u: any) => u.id === this.destinataire)) {
      this.destinataire = null;
    }
  }

  /** Le montant saisi dépasse-t-il le seuil au-delà duquel il faut la direction ? */
  exigeDirection(): boolean {
    const seuil = Number(this.regles()?.seuil_direction ?? 0);
    return !!seuil && Number(this.montantSaisi) > seuil;
  }

  /**
   * Destinataires proposés pour le montant en cours.
   *
   * Le niveau exigé dépend du montant : au-delà du seuil, un chef de
   * service ne suffit plus. Proposer quand même toute la liste ferait
   * choisir quelqu'un que le serveur refuserait ensuite. Tant que les
   * règles ne sont pas chargées on montre tout le monde : mieux vaut un
   * refus au dépôt qu'une liste vide sans explication.
   */
  approbateursAdmis(): any[] {
    const regles = this.regles();
    if (!regles) return this.approbateurs();

    const admis = this.exigeDirection()
      ? regles.roles_au_dessus : regles.roles_sous_seuil;

    return this.approbateurs().filter((u: any) => admis.includes(u.role));
  }

  deposerBon(): void {
    if (!this.caisseChoisie || !this.objet.trim() || this.montantSaisi <= 0) {
      this.toast.erreur('Caisse, objet et montant sont obligatoires.');
      return;
    }

    this.service.deposerBon({
      caisse: this.caisseChoisie,
      objet: this.objet,
      montant: String(this.montantSaisi),
      type_depense: this.typeDepense,
      moyen_transport: this.typeDepense === 'TRANSPORT' ? this.moyenTransport : '',
      destinataire: this.typeDepense === 'TRANSPORT' ? null : this.destinataire,
      justificatif: this.fichier,
    }).subscribe({
      next: () => {
        this.bonOuvert.set(false);
        this.reinitialiser();
        this.toast.succes('Bon de sortie envoyé.');
        this.charger();
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Demande refusée.'),
    });
  }

  deciderBon(b: BonSortie, autorise: boolean): void {
    this.service.deciderBon(b.id, autorise).subscribe({
      next: () => {
        this.toast.succes(autorise ? 'Bon autorisé.' : 'Bon refusé.');
        this.charger();
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Action impossible.'),
    });
  }

  payer(b: BonSortie): void {
    this.service.payerBon(b.id).subscribe({
      next: () => {
        this.toast.succes('Décaissement enregistré.');
        this.charger();
        const c = this.selection();
        if (c) this.choisir(c);
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Décaissement impossible.'),
    });
  }

  ouvrirRetour(b: BonSortie): void {
    this.montantSaisi = 0;
    this.retourOuvert.set(b);
  }

  rendre(b: BonSortie): void {
    this.service.rendreMonnaie(b.id, String(this.montantSaisi)).subscribe({
      next: () => {
        this.retourOuvert.set(null);
        this.toast.succes('Monnaie remise en caisse.');
        this.charger();
        const c = this.selection();
        if (c) this.choisir(c);
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Retour refusé.'),
    });
  }
}
