import { Routes } from '@angular/router';
import { authGuard, roleGuard } from './core/auth.guard';
import { ShellComponent } from './layout/shell.component';
import { LoginComponent } from './pages/login/login.component';
import { MODULES_MOYENS_GENERAUX, CHEMIN_PAR_TYPE_DOCUMENT } from './core/modules-metier';

// Inverse de CHEMIN_PAR_TYPE_DOCUMENT : chemin -> type de document.
const TYPES_DOCUMENT_IMPLEMENTES: Record<string, string> = Object.fromEntries(
  Object.entries(CHEMIN_PAR_TYPE_DOCUMENT).map(([type, chemin]) => [chemin, type]),
);

// Routes générées depuis le registre des modules « Moyens Généraux ». Les
// modules non encore implémentés pointent vers EnConstructionComponent en
// attendant leur tour, sans toucher à la navigation ni aux permissions.
const routesModulesMetier: Routes = MODULES_MOYENS_GENERAUX.map((m) => {
  const typeDocument = TYPES_DOCUMENT_IMPLEMENTES[m.lien];
  return {
    path: m.lien.replace(/^\//, ''),
    ...(m.roles ? { canActivate: [roleGuard(...m.roles)] } : {}),
    data: { titre: m.libelle, type: typeDocument },
    loadComponent: typeDocument
      ? () => import('./pages/documents/documents.component').then((c) => c.DocumentsComponent)
      : () => import('./pages/en-construction/en-construction.component').then((c) => c.EnConstructionComponent),
  };
});

export const routes: Routes = [
  { path: 'connexion', component: LoginComponent },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'tableau-de-bord', pathMatch: 'full' },
      {
        path: 'tableau-de-bord',
        loadComponent: () =>
          import('./pages/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'calendrier',
        loadComponent: () =>
          import('./pages/calendrier/calendrier.component').then((m) => m.CalendrierComponent),
      },
      {
        path: 'reserver',
        loadComponent: () =>
          import('./pages/reservation-form/reservation-form.component').then((m) => m.ReservationFormComponent),
      },
      {
        path: 'recurrence',
        loadComponent: () =>
          import('./pages/recurrence/recurrence.component').then((m) => m.RecurrenceComponent),
      },
      {
        path: 'mes-reservations',
        loadComponent: () =>
          import('./pages/mes-reservations/mes-reservations.component').then((m) => m.MesReservationsComponent),
      },
      {
        path: 'validation',
        canActivate: [roleGuard('SECRETAIRE', 'ADMINISTRATEUR')],
        loadComponent: () =>
          import('./pages/validation/validation.component').then((m) => m.ValidationComponent),
      },
      {
        path: 'salles',
        canActivate: [roleGuard('SECRETAIRE', 'ADMINISTRATEUR')],
        loadComponent: () =>
          import('./pages/salles/salles.component').then((m) => m.SallesComponent),
      },
      {
        path: 'audiences',
        loadComponent: () =>
          import('./pages/audiences/audiences.component').then((m) => m.AudiencesComponent),
      },
      {
        path: 'utilisateurs',
        canActivate: [roleGuard('ADMINISTRATEUR')],
        loadComponent: () =>
          import('./pages/utilisateurs/utilisateurs.component').then((m) => m.UtilisateursComponent),
      },
      {
        path: 'journal',
        canActivate: [roleGuard('ADMINISTRATEUR')],
        loadComponent: () =>
          import('./pages/journal/journal.component').then((m) => m.JournalComponent),
      },
      {
        path: 'administration',
        canActivate: [roleGuard('ADMINISTRATEUR')],
        loadComponent: () =>
          import('./pages/administration/administration.component').then((m) => m.AdministrationComponent),
      },
      ...routesModulesMetier,
    ],
  },
  { path: '**', redirectTo: '' },
];
