import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-profil',
  imports: [CommonModule, IconComponent],
  template: `
  <div class="entete anim-entree">
    <h1>Mon profil</h1>
    <p class="sous-titre">{{ auth.utilisateur()?.nom_complet }} — {{ auth.utilisateur()?.role_libelle }}</p>
  </div>

  @if (message()) {
    <div class="alerte" [class.err]="!messageOk()" [class.ok]="messageOk()">
      <app-icon [name]="messageOk() ? 'checkCircle' : 'close'" [size]="16"/> {{ message() }}
    </div>
  }

  <div class="deux">
    <div class="carte anim-entree">
      <h3>Photo de profil</h3>
      <div class="apercu">
        @if (auth.utilisateur()?.photo_profil) {
          <img [src]="auth.utilisateur()!.photo_profil" alt="Photo de profil" />
        } @else {
          <div class="vide-apercu"><app-icon name="user" [size]="28"/></div>
        }
      </div>
      <input type="file" accept="image/*" #entreePhoto (change)="choisir($event, 'photo_profil')" />
      <button class="btn vert" [disabled]="!fichierPhoto || envoiPhoto()" (click)="envoyer('photo_profil')">
        @if (envoiPhoto()) { <span class="spinner petit"></span> Envoi… } @else { Enregistrer la photo }
      </button>
    </div>

    <div class="carte anim-entree">
      <h3>Signature électronique</h3>
      <p class="note">
        Utilisée pour tracer vos visas sur les documents administratifs
        (Fiche de besoin, Demande d'achat…).
      </p>
      <div class="apercu apercu-signature">
        @if (auth.utilisateur()?.signature) {
          <img [src]="auth.utilisateur()!.signature" alt="Signature" />
        } @else {
          <div class="vide-apercu"><app-icon name="edit" [size]="28"/></div>
        }
      </div>
      <input type="file" accept="image/*" #entreeSignature (change)="choisir($event, 'signature')" />
      <button class="btn vert" [disabled]="!fichierSignature || envoiSignature()" (click)="envoyer('signature')">
        @if (envoiSignature()) { <span class="spinner petit"></span> Envoi… } @else { Enregistrer la signature }
      </button>
    </div>
  </div>
  `,
  styles: [`
    .entete { margin-bottom: 1rem; }
    .sous-titre { color: var(--txt-2); font-size: .82rem; margin: .2rem 0 0; }
    .deux { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 820px) { .deux { grid-template-columns: 1fr; } }

    .note { font-size: .82rem; color: var(--txt-2); margin: -.4rem 0 .8rem; }
    .apercu {
      width: 100%; height: 140px; border: 1px dashed var(--bord); border-radius: 10px;
      display: flex; align-items: center; justify-content: center; overflow: hidden;
      background: #f8fafc; margin-bottom: .8rem;
    }
    .apercu img { max-width: 100%; max-height: 100%; object-fit: contain; }
    .apercu-signature img { background: #fff; }
    .vide-apercu { color: var(--txt-3); }
    input[type="file"] { display: block; margin-bottom: .7rem; font-size: .83rem; }

    .alerte { display: flex; align-items: center; gap: .5rem; margin: .8rem 0; padding: .6rem .9rem;
      border-radius: 8px; font-size: .83rem; }
    .alerte.err { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .alerte.ok { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }
  `],
})
export class ProfilComponent {
  fichierPhoto: File | null = null;
  fichierSignature: File | null = null;
  envoiPhoto = signal(false);
  envoiSignature = signal(false);
  message = signal('');
  messageOk = signal(false);

  constructor(private api: ApiService, public auth: AuthService) {}

  choisir(event: Event, champ: 'photo_profil' | 'signature'): void {
    const fichier = (event.target as HTMLInputElement).files?.[0] ?? null;
    if (champ === 'photo_profil') this.fichierPhoto = fichier;
    else this.fichierSignature = fichier;
  }

  envoyer(champ: 'photo_profil' | 'signature'): void {
    const fichier = champ === 'photo_profil' ? this.fichierPhoto : this.fichierSignature;
    if (!fichier) return;

    const enCours = champ === 'photo_profil' ? this.envoiPhoto : this.envoiSignature;
    enCours.set(true);
    this.message.set('');

    const donnees = new FormData();
    donnees.append(champ, fichier);

    this.api.majMonProfil(donnees).subscribe({
      next: (u) => {
        enCours.set(false);
        this.auth.utilisateur.set(u);
        this.messageOk.set(true);
        this.message.set(champ === 'photo_profil' ? 'Photo enregistrée.' : 'Signature enregistrée.');
        if (champ === 'photo_profil') this.fichierPhoto = null;
        else this.fichierSignature = null;
      },
      error: (e) => {
        enCours.set(false);
        this.messageOk.set(false);
        this.message.set(e?.error?.detail || "Échec de l'envoi.");
      },
    });
  }
}
