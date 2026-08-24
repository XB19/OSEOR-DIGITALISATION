import { Injectable, signal } from '@angular/core';

export interface DemandeMotif {
  titre: string;
  message?: string;
  placeholder?: string;
  obligatoire?: boolean;
  libelleConfirmer?: string;
  dangereux?: boolean;
  sansTexte?: boolean;
}

/**
 * Remplace window.prompt() par une boîte de dialogue stylée cohérente avec
 * le reste de l'app. Rendue une seule fois globalement (voir DialogueComponent
 * dans ShellComponent), pilotée depuis n'importe quel composant via ce service.
 */
@Injectable({ providedIn: 'root' })
export class DialogueService {
  readonly demande = signal<DemandeMotif | null>(null);
  private resoudre: ((valeur: string | null) => void) | null = null;

  /** Retourne le texte saisi, ou null si l'utilisateur annule. */
  demanderMotif(d: DemandeMotif): Promise<string | null> {
    this.demande.set(d);
    return new Promise((resolve) => { this.resoudre = resolve; });
  }

  /** Confirmation simple (remplace window.confirm()), sans zone de texte. */
  async demanderConfirmation(d: Omit<DemandeMotif, 'sansTexte' | 'obligatoire'>): Promise<boolean> {
    const valeur = await this.demanderMotif({ ...d, sansTexte: true });
    return valeur !== null;
  }

  confirmer(valeur: string): void {
    this.resoudre?.(valeur);
    this.resoudre = null;
    this.demande.set(null);
  }

  annuler(): void {
    this.resoudre?.(null);
    this.resoudre = null;
    this.demande.set(null);
  }
}
