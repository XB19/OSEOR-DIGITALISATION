import { Component, ElementRef, HostListener, ViewChild, effect, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { IconComponent } from './icon.component';
import { EntreeAide, ModuleAide } from '../core/models';

interface MessageChat {
  auteur: 'bot' | 'utilisateur';
  texte?: string;
  chipsModules?: ModuleAide[];
  chipsQuestions?: EntreeAide[];
}

/**
 * Assistant d'aide flottant, monté une seule fois dans le shell : visible
 * sur toutes les pages, pour tous les rôles. Répond à partir du référentiel
 * de questions/réponses géré côté admin (module `aide`) — aucune saisie
 * libre n'est envoyée à un service externe.
 */
@Component({
  selector: 'app-aide-chatbot',
  standalone: true,
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  @if (bulleAccueil()) {
    <div class="bulle-accueil anim-entree" (click)="ouvrirDepuisBulle($event)">
      <button class="fermer-bulle" (click)="fermerBulleAccueil($event)" aria-label="Fermer">
        <app-icon name="close" [size]="13"/>
      </button>
      <strong>👋 Besoin d'aide ?</strong>
      <span>Je suis l'assistant OSEOR, cliquez ici si vous êtes bloqué sur une action.</span>
    </div>
  }

  <button class="aide-fab" [class.pulse]="!dejaVu()" (click)="basculer($event)"
          aria-label="Ouvrir l'assistant d'aide OSEOR" title="Assistant d'aide OSEOR">
    <app-icon name="helpCircle" [size]="22"/>
    <span>Aide</span>
  </button>

  @if (ouvert()) {
    <div class="aide-panneau anim-entree" (click)="$event.stopPropagation()">
      <div class="entete">
        <div class="titre"><app-icon name="helpCircle" [size]="18"/> Assistant OSEOR</div>
        <button class="fermer" (click)="ouvert.set(false)" aria-label="Fermer"><app-icon name="close" [size]="17"/></button>
      </div>

      <div class="corps" #corps>
        @for (m of messages(); track $index) {
          <div class="bulle" [class.bot]="m.auteur === 'bot'" [class.utilisateur]="m.auteur === 'utilisateur'">
            @if (m.texte) { <div class="texte">{{ m.texte }}</div> }
            @if (m.chipsModules?.length) {
              <div class="puces">
                @for (mo of m.chipsModules; track mo.module) {
                  <button class="puce" (click)="choisirModule(mo)">{{ mo.libelle }}</button>
                }
              </div>
            }
            @if (m.chipsQuestions?.length) {
              <div class="puces col">
                @for (q of m.chipsQuestions; track q.id) {
                  <button class="puce" (click)="choisirQuestion(q)">{{ q.question }}</button>
                }
              </div>
            }
          </div>
        }
        @if (enChargement()) {
          <div class="bulle bot"><div class="texte">…</div></div>
        }
      </div>

      <form class="pied" (ngSubmit)="envoyer()">
        <input type="text" placeholder="Posez votre question…" [(ngModel)]="saisie" name="saisie" autocomplete="off" />
        <button type="submit" aria-label="Envoyer" [disabled]="!saisie.trim()"><app-icon name="send" [size]="16"/></button>
      </form>
    </div>
  }
  `,
  styles: [`
    .aide-fab {
      position: fixed; bottom: 1.5rem; right: 1.5rem; height: 52px;
      border-radius: 999px; background: var(--accent); color: #fff; border: none;
      box-shadow: var(--ombre-lg); cursor: pointer; z-index: 60;
      display: flex; align-items: center; gap: .5rem; padding: 0 1.2rem 0 1rem;
      font-family: inherit; font-size: .92rem; font-weight: 700; white-space: nowrap;
      transition: transform var(--t);
    }
    .aide-fab:hover { transform: scale(1.05); }
    .aide-fab.pulse { animation: pulseAide 2.2s infinite; }
    @keyframes pulseAide {
      0% { box-shadow: var(--ombre-lg), 0 0 0 0 rgba(249,115,22,.55); }
      70% { box-shadow: var(--ombre-lg), 0 0 0 14px rgba(249,115,22,0); }
      100% { box-shadow: var(--ombre-lg), 0 0 0 0 rgba(249,115,22,0); }
    }

    .bulle-accueil {
      position: fixed; bottom: 6.3rem; right: 1.5rem; width: 260px; max-width: calc(100vw - 2rem);
      background: #fff; border: 1px solid var(--bord); border-radius: 14px; box-shadow: var(--ombre-lg);
      padding: .85rem 1rem; z-index: 60; cursor: pointer; display: flex; flex-direction: column; gap: .2rem;
    }
    .bulle-accueil strong { font-size: .88rem; color: var(--navy); }
    .bulle-accueil span { font-size: .8rem; color: var(--txt-2); line-height: 1.35; }
    .bulle-accueil::after {
      content: ''; position: absolute; bottom: -7px; right: 1.7rem; width: 14px; height: 14px;
      background: #fff; border-right: 1px solid var(--bord); border-bottom: 1px solid var(--bord);
      transform: rotate(45deg);
    }
    .fermer-bulle {
      position: absolute; top: .4rem; right: .4rem; background: none; border: none; color: var(--txt-3);
      cursor: pointer; display: flex; padding: .25rem; border-radius: 6px; transition: background var(--t);
    }
    .fermer-bulle:hover { background: #f1f5f9; color: var(--txt-2); }

    .aide-panneau {
      position: fixed; bottom: 5.5rem; right: 1.5rem; width: 380px; max-width: calc(100vw - 2rem);
      max-height: min(560px, calc(100vh - 7.5rem)); background: #fff; border-radius: 16px;
      box-shadow: var(--ombre-lg); z-index: 60; display: flex; flex-direction: column; overflow: hidden;
      border: 1px solid var(--bord);
    }
    .entete {
      background: var(--navy); color: #fff; padding: .85rem 1.1rem;
      display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
    }
    .titre { display: flex; align-items: center; gap: .5rem; font-weight: 700; font-size: .92rem; }
    .fermer { background: none; border: none; color: #cdd9ee; cursor: pointer; display: flex; padding: .2rem; }
    .fermer:hover { color: #fff; }

    .corps {
      flex: 1; overflow-y: auto; padding: .9rem; background: #f8fafc;
      display: flex; flex-direction: column; gap: .6rem;
    }
    .bulle { max-width: 88%; }
    .bulle .texte { border-radius: 12px; padding: .6rem .8rem; font-size: .85rem; line-height: 1.4; white-space: pre-line; }
    .bulle.bot { align-self: flex-start; }
    .bulle.bot .texte { background: #fff; border: 1px solid var(--bord); border-bottom-left-radius: 2px; }
    .bulle.utilisateur { align-self: flex-end; }
    .bulle.utilisateur .texte { background: var(--navy); color: #fff; border-bottom-right-radius: 2px; }

    .puces { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .4rem; }
    .puces.col { flex-direction: column; align-items: stretch; }
    .puce {
      background: #eff6ff; color: var(--navy); border: 1px solid var(--bord); border-radius: 999px;
      padding: .4rem .8rem; font-size: .78rem; font-weight: 600; cursor: pointer; text-align: left;
      transition: background var(--t), color var(--t);
    }
    .puce:hover { background: var(--accent); color: #fff; border-color: transparent; }

    .pied {
      flex-shrink: 0; display: flex; gap: .5rem; padding: .7rem; border-top: 1px solid var(--bord); background: #fff;
    }
    .pied input {
      flex: 1; border: 1px solid var(--bord); border-radius: 999px; padding: .55rem 1rem; font-size: .85rem;
    }
    .pied input:focus { outline: none; border-color: var(--accent); }
    .pied button {
      width: 38px; height: 38px; border-radius: 50%; background: var(--accent); color: #fff; border: none;
      cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
      transition: opacity var(--t);
    }
    .pied button:disabled { opacity: .4; cursor: default; }

    @media (max-width: 480px) {
      .aide-panneau { right: 1rem; left: 1rem; width: auto; }
      .aide-fab { right: 1rem; bottom: 1rem; }
      .bulle-accueil { right: 1rem; bottom: 5.8rem; }
    }
  `],
})
export class AideChatbotComponent {
  ouvert = signal(false);
  messages = signal<MessageChat[]>([]);
  enChargement = signal(false);
  saisie = '';

  /** Bulle de bienvenue affichée automatiquement pour signaler le chatbot aux inattentifs. */
  bulleAccueil = signal(false);
  /** Passe à `true` dès que l'utilisateur a vu/utilisé l'assistant une première fois : arrête la pulsation. */
  dejaVu = signal(false);

  @ViewChild('corps') private corpsRef?: ElementRef<HTMLDivElement>;

  constructor(private api: ApiService) {
    // Fait défiler automatiquement vers le bas à chaque nouveau message
    // (question posée, réponse reçue, indicateur de chargement) pour que
    // l'utilisateur voie la réponse sans avoir à scroller lui-même.
    effect(() => {
      this.messages();
      this.enChargement();
      setTimeout(() => this.scrollEnBas());
    });

    // Signale la présence de l'assistant dès l'arrivée sur l'application,
    // pour les utilisateurs qui ne remarqueraient pas spontanément le bouton.
    setTimeout(() => {
      if (this.dejaVu()) return;
      this.bulleAccueil.set(true);
      setTimeout(() => this.bulleAccueil.set(false), 9000);
    }, 1500);
  }

  private scrollEnBas(): void {
    const el = this.corpsRef?.nativeElement;
    if (el) el.scrollTop = el.scrollHeight;
  }

  basculer(e: MouseEvent): void {
    e.stopPropagation();
    this.dejaVu.set(true);
    this.bulleAccueil.set(false);
    const ouverture = !this.ouvert();
    this.ouvert.set(ouverture);
    if (ouverture && this.messages().length === 0) this.initialiser();
  }

  /** Clic sur la bulle de bienvenue elle-même : ouvre directement le chat. */
  ouvrirDepuisBulle(e: MouseEvent): void {
    this.basculer(e);
  }

  fermerBulleAccueil(e: MouseEvent): void {
    e.stopPropagation();
    this.dejaVu.set(true);
    this.bulleAccueil.set(false);
  }

  private initialiser(): void {
    this.messages.set([{
      auteur: 'bot',
      texte: "Bonjour ! Je suis l'assistant OSEOR. Choisissez une catégorie ci-dessous, ou tapez directement votre question.",
    }]);
    this.api.modulesAide().subscribe({
      next: (mods) => this.messages.update((m) => [...m, { auteur: 'bot', chipsModules: mods }]),
      error: () => this.ajouterErreur(),
    });
  }

  choisirModule(mo: ModuleAide): void {
    this.messages.update((m) => [...m, { auteur: 'utilisateur', texte: mo.libelle }]);
    this.api.entreesAide({ module: mo.module }).subscribe({
      next: (res) => this.messages.update((m) => [...m, {
        auteur: 'bot',
        texte: `Sur « ${mo.libelle} », voici les questions les plus fréquentes :`,
        chipsQuestions: res.results,
      }]),
      error: () => this.ajouterErreur(),
    });
  }

  choisirQuestion(q: EntreeAide): void {
    this.messages.update((m) => [...m, { auteur: 'utilisateur', texte: q.question }]);
    this.messages.update((m) => [...m, { auteur: 'bot', texte: q.reponse }]);
  }

  envoyer(): void {
    const question = this.saisie.trim();
    if (!question) return;
    this.messages.update((m) => [...m, { auteur: 'utilisateur', texte: question }]);
    this.saisie = '';
    this.enChargement.set(true);
    this.api.poserQuestionAide(question).subscribe({
      next: (rep) => {
        this.enChargement.set(false);
        if (rep.trouve) {
          const [meilleure, ...autres] = rep.resultats;
          this.messages.update((m) => [...m, { auteur: 'bot', texte: meilleure.reponse }]);
          if (autres.length) {
            this.messages.update((m) => [...m, {
              auteur: 'bot', texte: 'Cela peut aussi vous intéresser :', chipsQuestions: autres,
            }]);
          }
        } else {
          this.messages.update((m) => [...m, {
            auteur: 'bot',
            texte: "Je n'ai pas trouvé de réponse à cette question. Essayez de la reformuler, ou choisissez une catégorie :",
          }]);
        }
      },
      error: () => this.ajouterErreur(),
    });
  }

  private ajouterErreur(): void {
    this.enChargement.set(false);
    this.messages.update((m) => [...m, {
      auteur: 'bot', texte: "Une erreur est survenue, réessayez dans un instant.",
    }]);
  }

  /** Ferme le panneau quand on clique en dehors, même pattern que le panneau de notifications. */
  @HostListener('document:click', ['$event'])
  onClicDocument(e: MouseEvent): void {
    if (!this.ouvert()) return;
    const cible = e.target as HTMLElement;
    if (cible.closest('.aide-panneau') || cible.closest('.aide-fab')) return;
    this.ouvert.set(false);
  }
}
