import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Blog: un fichero por idioma en src/content/blog/<idioma>/<slug>.md. El slug es el mismo en los tres idiomas.
const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    kicker: z.string(),
    minutes: z.number(),
    // Foto real de portada (opcional): ruta dentro de public/, p. ej. /img/blog/probador.webp. Sin foto, la tarjeta es solo tipográfica.
    seoTitle: z.string().optional(),        // título para Google si el de la página pasa de 60 caracteres
    metaDescription: z.string().optional(), // descripción para Google (≤155) si la de la página es más larga
    image: z.string().optional(),
    imageAlt: z.string().optional(),
  }),
});

export const collections = { blog };
