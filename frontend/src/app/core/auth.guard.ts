import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.accessToken) {
    return true;
  }
  router.navigate(['/connexion']);
  return false;
};

export const roleGuard = (...roles: string[]): CanActivateFn => {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (auth.aRole(...roles)) {
      return true;
    }
    router.navigate(['/tableau-de-bord']);
    return false;
  };
};
