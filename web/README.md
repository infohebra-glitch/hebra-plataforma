# Web de Hebra

Astro 5 + GSAP (ScrollTrigger) + Lenis. Tipografías Fraunces y Hanken Grotesk servidas desde la propia web (sin Google Fonts, sin cookies).

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # genera dist/
```

- Páginas: `src/pages/` (inicio, probador, origen, como-funciona, piloto, nosotros, contacto, privacidad, aviso-legal, gracias, `p/demo` = ficha NFC de ejemplo).
- Paleta y tipografía: `src/styles/global.css`.
- Animaciones: `src/scripts/motion.js` (hilo, revelados, cabecera) y `src/scripts/modules.js` (calculadora, recorrido, ficha, formulario).
- Formulario de contacto: Netlify Forms (`data-netlify`).

Antes de lanzar con dominio: cambiar `site` en `astro.config.mjs`, quitar `noindex` en `src/layouts/Base.astro`, abrir `public/robots.txt` y rellenar los `[pendiente]` de privacidad y aviso legal.
