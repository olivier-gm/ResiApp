# Acceso con Google

La integración usa el flujo Authorization Code de OpenID Connect con Authlib, state, nonce y PKCE S256. Solicita únicamente identidad, correo y perfil. No guarda tokens de acceso ni refresh tokens: guarda una relación entre el identificador estable `sub` de Google y la cuenta Django.

## Configuración

1. En Google Cloud configura el consentimiento de Google Auth Platform y crea un cliente OAuth de tipo **Aplicación web**. Mientras la aplicación esté en pruebas, incorpora las cuentas de prueba permitidas.
2. Registra exactamente este URI de redirección local: `http://127.0.0.1:8000/cuenta/google/callback/`. Si prefieres localhost, usa `http://localhost:8000/cuenta/google/callback/` y cambia también PUBLIC_BASE_URL. No mezcles ambos hosts durante el acceso.
3. Define `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en `.env`, y PUBLIC_BASE_URL con el origen exacto. Reinicia Django. Las credenciales permanecen en el servidor.
4. Ejecuta `python manage.py migrate`. Aparece «Continuar con Google» en acceso y registro. En producción registra el URI equivalente con tu dominio HTTPS y configura proxy/cookies conforme a OPERACION.md.

Si faltan credenciales, el botón se oculta y el inicio directo devuelve un aviso de configuración pendiente. No se crean recursos en Google Cloud automáticamente.

## Cuentas existentes

Una identidad nueva con correo verificado crea una cuenta sin contraseña local y sin privilegios especiales. Si ese correo ya existe, no se vincula automáticamente: entra primero con la contraseña de ResiVe y usa «Vincular mi cuenta de Google» desde Mi cuenta. Puedes recuperar la contraseña si la olvidaste. La vinculación exige sesión original, CSRF y confirmación de Google.

Las cuentas creadas con Google pueden crear una contraseña mediante el correo de recuperación si su dirección actual está verificada. Cambiar el correo local obliga a verificarlo; volver a entrar con Google no verifica automáticamente la dirección nueva. Las cuentas suspendidas siguen bloqueadas.

Solo se mantiene un intento de Google pendiente por sesión: iniciar otro reemplaza el anterior. El usuario puede cancelar y volver a empezar. El salto a Google utiliza navegación completa para permitir el consentimiento externo; el resto de la interfaz conserva HTMX.

Fuentes: [Authlib para Django](https://docs.authlib.org/en/latest/oauth2/client/web/django.html), [OpenID Connect de Google](https://developers.google.com/identity/openid-connect/openid-connect).

Las pruebas locales simulan Google e incluyen tokens firmados de prueba. Falta comprobar consentimiento y credenciales contra Google real.
