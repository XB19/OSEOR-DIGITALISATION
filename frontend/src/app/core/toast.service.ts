import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  titre: string;
  message: string;
  type: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
}

/** Notifications « toast » éphémères affichées à l'écran (coin haut-droit). */
@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<Toast[]>([]);
  private seq = 0;

  afficher(t: { titre: string; message: string; type?: string }): void {
    const id = ++this.seq;
    const toast: Toast = {
      id,
      titre: t.titre,
      message: t.message,
      type: (t.type as Toast['type']) || 'INFO',
    };
    this.toasts.update((l) => [...l, toast]);
    setTimeout(() => this.retirer(id), 6000);
  }

  retirer(id: number): void {
    this.toasts.update((l) => l.filter((x) => x.id !== id));
  }

  /** Raccourcis : la grande majorité des appels sont un succès ou une erreur. */
  succes(message: string, titre = 'Succès'): void {
    this.afficher({ titre, message, type: 'SUCCESS' });
  }

  erreur(message: string, titre = 'Erreur'): void {
    this.afficher({ titre, message, type: 'ERROR' });
  }

  info(message: string, titre = 'Information'): void {
    this.afficher({ titre, message, type: 'INFO' });
  }
}
