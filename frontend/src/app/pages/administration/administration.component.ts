import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { ParametresLDAP } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-administration',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <div class="entete anim-entree">
    <div>
      <h1>Administration générale</h1>
      <p class="sous-titre">Paramètres système réservés aux administrateurs</p>
    </div>
  </div>

  <div class="carte anim-entree">
    <div class="carte-entete">
      <div class="carte-titre">
        <app-icon name="server" [size]="18"/>
        <h3>Active Directory (LDAP)</h3>
        @if (parametres()?.configure) {
          <span class="badge validee">Configuré</span>
        } @else {
          <span class="badge rouge">Non configuré</span>
        }
      </div>
      <p class="carte-sous-titre">
        Connexion utilisée par le bouton « Synchroniser depuis Azure AD » de la page
        Utilisateurs, pour importer/mettre à jour les comptes depuis un annuaire
        Active Directory local (LDAP) — nécessite un serveur accessible depuis le réseau
        de l'application.
      </p>
    </div>

    @if (chargement()) {
      <p class="txt-attente">Chargement…</p>
    } @else {
      <div class="ligne">
        <div class="champ">
          <label>Adresse du serveur LDAP</label>
          <input [(ngModel)]="form.server_uri" placeholder="ldap://192.168.1.10" />
        </div>
        <div class="champ">
          <label>Domaine NetBIOS</label>
          <input [(ngModel)]="form.domaine" placeholder="OSEOR" />
        </div>
      </div>
      <div class="ligne">
        <div class="champ">
          <label>Base DN</label>
          <input [(ngModel)]="form.base_dn" placeholder="DC=oseor,DC=local" />
        </div>
        <div class="champ">
          <label>DN du compte de service</label>
          <input [(ngModel)]="form.bind_dn" placeholder="CN=svcOseor,OU=Services,DC=oseor,DC=local" />
        </div>
      </div>
      <div class="ligne">
        <div class="champ">
          <label>
            Mot de passe du compte de service
            {{ parametres()?.mot_de_passe_defini ? '(laisser vide = inchangé)' : '' }}
          </label>
          <input type="password" [(ngModel)]="form.bind_password" />
        </div>
      </div>

      @if (message()) {
        <div class="alerte" [class.err]="!messageOk()" [class.ok]="messageOk()">
          <app-icon [name]="messageOk() ? 'checkCircle' : 'close'" [size]="16"/> {{ message() }}
        </div>
      }

      <div class="boutons">
        <button class="btn secondaire" (click)="tester()" [disabled]="test_en_cours() || enregistrement_en_cours()">
          @if (test_en_cours()) { <span class="spinner petit"></span> Test en cours… }
          @else { Tester la connexion }
        </button>
        <button class="btn vert" (click)="enregistrer()" [disabled]="enregistrement_en_cours() || test_en_cours()">
          @if (enregistrement_en_cours()) { <span class="spinner petit"></span> Enregistrement… }
          @else { Enregistrer }
        </button>
      </div>
    }
  </div>
  `,
  styles: [`
    .entete { display: flex; justify-content: space-between; align-items: flex-start; }
    .sous-titre { color: var(--txt-2); font-size: .82rem; margin: .2rem 0 0; }

    .carte-entete { margin-bottom: 1.2rem; }
    .carte-titre { display: flex; align-items: center; gap: .6rem; }
    .carte-titre h3 { margin: 0; }
    .carte-sous-titre { font-size: .82rem; color: var(--txt-2); margin: .5rem 0 0; line-height: 1.6; }

    .txt-attente { color: var(--txt-2); font-size: .85rem; }

    .ligne { display: flex; gap: 1rem; margin-bottom: .9rem; }
    .champ { flex: 1; display: flex; flex-direction: column; gap: .3rem; }
    .champ label { font-size: .78rem; font-weight: 600; color: var(--txt-2); }
    .champ input {
      border: 1px solid var(--bord); border-radius: 8px; padding: .55rem .7rem; font-size: .85rem;
    }

    .alerte { display: flex; align-items: center; gap: .5rem; margin: .8rem 0; padding: .6rem .9rem;
      border-radius: 8px; font-size: .83rem; }
    .alerte.err { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .alerte.ok { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }

    .boutons { display: flex; gap: .6rem; margin-top: .6rem; }
  `],
})
export class AdministrationComponent implements OnInit {
  parametres = signal<ParametresLDAP | null>(null);
  chargement = signal(true);
  test_en_cours = signal(false);
  enregistrement_en_cours = signal(false);
  message = signal('');
  messageOk = signal(false);

  form: any = { server_uri: '', domaine: '', base_dn: '', bind_dn: '', bind_password: '' };

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.charger();
  }

  charger(): void {
    this.chargement.set(true);
    this.api.parametresLDAP().subscribe((p) => {
      this.parametres.set(p);
      this.form = {
        server_uri: p.server_uri, domaine: p.domaine, base_dn: p.base_dn,
        bind_dn: p.bind_dn, bind_password: '',
      };
      this.chargement.set(false);
    });
  }

  tester(): void {
    this.message.set('');
    this.test_en_cours.set(true);
    this.api.testerLDAP(this.form).subscribe({
      next: (r) => {
        this.test_en_cours.set(false);
        this.messageOk.set(true);
        this.message.set(r.detail);
      },
      error: (e) => {
        this.test_en_cours.set(false);
        this.messageOk.set(false);
        this.message.set(e?.error?.detail || 'Échec du test de connexion.');
      },
    });
  }

  enregistrer(): void {
    this.message.set('');
    this.enregistrement_en_cours.set(true);
    this.api.majParametresLDAP(this.form).subscribe({
      next: (p) => {
        this.enregistrement_en_cours.set(false);
        this.parametres.set(p);
        this.form.bind_password = '';
        this.messageOk.set(true);
        this.message.set('Configuration enregistrée.');
      },
      error: (e) => {
        this.enregistrement_en_cours.set(false);
        this.messageOk.set(false);
        this.message.set(
          Object.values(e?.error || { x: ['Erreur.'] }).flat().join(' '),
        );
      },
    });
  }
}
