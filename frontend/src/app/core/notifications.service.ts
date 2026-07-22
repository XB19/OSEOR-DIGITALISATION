import { Injectable, signal } from '@angular/core';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';
import { ApiService } from './api.service';
import { ToastService } from './toast.service';
import { NotificationItem } from './models';

/**
 * Notifications temps réel via WebSocket (EF-18) + état non-lues.
 * À l'arrivée d'une notif : compteur cloche + toast à l'écran + bulle navigateur.
 */
@Injectable({ providedIn: 'root' })
export class NotificationsService {
  private socket?: WebSocket;
  readonly nonLues = signal(0);
  readonly dernieres = signal<NotificationItem[]>([]);

  constructor(
    private auth: AuthService,
    private api: ApiService,
    private toasts: ToastService,
  ) {}

  demarrer(): void {
    this.rafraichirCompteur();
    this.demanderPermissionNavigateur();
    this.connecterWebSocket();
  }

  private demanderPermissionNavigateur(): void {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
  }

  private notifierNavigateur(n: NotificationItem): void {
    try {
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(n.titre, { body: n.message, tag: 'oseor-' + n.id });
      }
    } catch { /* ignore */ }
  }

  arreter(): void {
    this.socket?.close();
    this.socket = undefined;
  }

  private connecterWebSocket(): void {
    const token = this.auth.accessToken;
    if (!token) return;
    this.socket = new WebSocket(`${environment.wsUrl}/notifications/?token=${token}`);

    this.socket.onmessage = (event) => {
      const notif: NotificationItem = JSON.parse(event.data);
      this.dernieres.update((l) => [notif, ...l].slice(0, 20));
      this.nonLues.update((n) => n + 1);
      // Affichage visible : toast à l'écran + bulle navigateur
      this.toasts.afficher({ titre: notif.titre, message: notif.message, type: notif.type });
      this.notifierNavigateur(notif);
    };

    this.socket.onclose = () => {
      // reconnexion simple après 5s tant que connecté
      if (this.auth.accessToken) setTimeout(() => this.connecterWebSocket(), 5000);
    };
  }

  rafraichirCompteur(): void {
    this.api.notificationsNonLues().subscribe((r) => this.nonLues.set(r.count));
  }

  chargerListe(): void {
    this.api.notifications().subscribe((p) => this.dernieres.set(p.results));
  }

  marquerLue(id: number): void {
    this.api.marquerNotifLue(id).subscribe(() => {
      this.dernieres.update((l) => l.map((n) => (n.id === id ? { ...n, lu: true } : n)));
      this.nonLues.update((n) => Math.max(0, n - 1));
    });
  }

  toutMarquerLu(): void {
    this.api.toutMarquerLu().subscribe(() => {
      this.dernieres.update((l) => l.map((n) => ({ ...n, lu: true })));
      this.nonLues.set(0);
    });
  }
}
