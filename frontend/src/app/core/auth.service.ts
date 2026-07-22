import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { Utilisateur } from './models';

const ACCESS = 'oseor_access';
const REFRESH = 'oseor_refresh';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = environment.apiUrl;

  readonly utilisateur = signal<Utilisateur | null>(null);
  readonly estConnecte = computed(() => this.utilisateur() !== null);
  readonly role = computed(() => this.utilisateur()?.role ?? null);

  constructor(private http: HttpClient) {}

  get accessToken(): string | null {
    return localStorage.getItem(ACCESS);
  }
  get refreshToken(): string | null {
    return localStorage.getItem(REFRESH);
  }

  connexion(username: string, password: string): Observable<any> {
    return this.http.post<any>(`${this.api}/auth/token/`, { username, password }).pipe(
      tap((r) => {
        localStorage.setItem(ACCESS, r.access);
        localStorage.setItem(REFRESH, r.refresh);
      })
    );
  }

  /** Stocke une paire de tokens reçus via SSO (ex. callback Azure AD). */
  stockerTokens(access: string, refresh: string): void {
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
  }

  rafraichir(): Observable<any> {
    return this.http
      .post<any>(`${this.api}/auth/refresh/`, { refresh: this.refreshToken })
      .pipe(tap((r) => localStorage.setItem(ACCESS, r.access)));
  }

  chargerProfil(): Observable<Utilisateur> {
    return this.http
      .get<Utilisateur>(`${this.api}/auth/me/`)
      .pipe(tap((u) => this.utilisateur.set(u)));
  }

  deconnexion(): void {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    this.utilisateur.set(null);
  }

  aRole(...roles: string[]): boolean {
    const r = this.role();
    return r !== null && roles.includes(r);
  }
}
