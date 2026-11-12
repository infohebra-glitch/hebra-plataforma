# Vídeo de demostración (40 s)

`video.html?lang=es|ca|en` dibuja cada fotograma con `render(t)`. Para regenerarlo:

1. Copia aquí `fonts/fraunces.woff2`, `fonts/hanken.woff2` (de `dist/_astro/`) y `camiseta-render.png`, `logo-blanc.png`, `logo-blau.png` (de `public/img/`).
2. `node cap.cjs es all ./fr_es` (1200 fotogramas a 30 fps).
3. `ffmpeg -framerate 30 -i fr_es/f%05d.jpg -c:v libx264 -pix_fmt yuv420p -crf 23 -movflags +faststart ../public/video/hebra-demo-es.mp4`
