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
  }),
});

export const collections = { blog };
