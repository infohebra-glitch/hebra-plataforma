import type { Lang } from '../i18n';
// Los nueve datos que la marca obtiene. Los usan las tarjetas de «Cómo funciona» y el abanico de la portada.
export type Card = { k: string; v: string; d: string; back: string; viz: string };
export const cards: Record<Lang, { hint: string; turn: string; cards: Card[] }> = {
  es: {
    hint: 'Toca una tarjeta para ver qué decides con ese dato.', turn: 'Qué decides',
    cards: [
      { viz: 'bars', k: 'Pruebas por prenda', v: '412', d: 'Por modelo, color y talla, cada día.', back: 'Qué prendas despiertan interés de verdad, más allá de lo que se vende.' },
      { viz: 'donut', k: 'Del probador a la caja', v: '27 %', d: 'Qué parte de lo probado acaba comprado.', back: 'Detectas lo muy probado y poco vendido antes de que llegue a rebajas.' },
      { viz: 'clock', k: 'Tiempo en cabina', v: '6 min', d: 'Cuánto dura cada prueba, por prenda.', back: 'Mucho tiempo y ninguna venta suele ser un problema de talla o de patrón.' },
      { viz: 'chips', k: 'Tallas pedidas', v: '9', d: 'Lo que se pide desde la cabina, haya o no en tienda.', back: 'Repones la talla que falta y ajustas la curva del próximo pedido.' },
      { viz: 'reasons', k: 'Por qué no se la lleva', v: '5', d: 'Talla, corte, precio, color o calidad.', back: 'Sabes si cambiar el precio, el patrón o el proveedor, sin adivinar.' },
      { viz: 'pairs', k: 'Prendas que entran juntas', v: '3', d: 'Qué se prueba a la vez en la misma cabina.', back: 'Montas el escaparate y el «combina con» con datos, no con intuición.' },
      { viz: 'heat', k: 'Horas punta del probador', v: '18 h', d: 'Cuándo se llenan las cabinas, cada día.', back: 'Pones a la persona en el probador en la hora que importa.' },
      { viz: 'origin', k: 'Interés por el origen', v: '41 %', d: 'Quién abre la cadena de la prenda en la ficha.', back: 'Compruebas si contar de dónde viene hace vender, con grupo de control.' },
      { viz: 'ab', k: 'Efecto de un cambio', v: '+6 pts', d: 'Antes y después, frente a un grupo de control.', back: 'Sabes si el cambio ha funcionado o si ha sido el tiempo o la campaña.' },
    ],
  },
  ca: {
    hint: 'Toca una targeta per veure què decideixes amb aquesta dada.', turn: 'Què decideixes',
    cards: [
      { viz: 'bars', k: 'Proves per peça', v: '412', d: 'Per model, color i talla, cada dia.', back: 'Quines peces desperten interès de debò, més enllà del que es ven.' },
      { viz: 'donut', k: 'De l’emprovador a la caixa', v: '27 %', d: 'Quina part del que s’emprova acaba comprat.', back: 'Detectes el que s’emprova molt i es ven poc abans que arribi a rebaixes.' },
      { viz: 'clock', k: 'Temps a la cabina', v: '6 min', d: 'Quant dura cada prova, per peça.', back: 'Molt de temps i cap venda sol ser un problema de talla o de patró.' },
      { viz: 'chips', k: 'Talles demanades', v: '9', d: 'El que es demana des de la cabina, n’hi hagi o no a la botiga.', back: 'Reposes la talla que falta i ajustes la corba de la propera comanda.' },
      { viz: 'reasons', k: 'Per què no se l’endú', v: '5', d: 'Talla, tall, preu, color o qualitat.', back: 'Saps si cal canviar el preu, el patró o el proveïdor, sense endevinar.' },
      { viz: 'pairs', k: 'Peces que entren juntes', v: '3', d: 'Què s’emprova alhora a la mateixa cabina.', back: 'Muntes l’aparador i el «combina amb» amb dades, no amb intuïció.' },
      { viz: 'heat', k: 'Hores punta de l’emprovador', v: '18 h', d: 'Quan s’omplen les cabines, cada dia.', back: 'Poses la persona a l’emprovador a l’hora que compta.' },
      { viz: 'origin', k: 'Interès per l’origen', v: '41 %', d: 'Qui obre la cadena de la peça a la fitxa.', back: 'Comproves si explicar d’on ve fa vendre, amb grup de control.' },
      { viz: 'ab', k: 'Efecte d’un canvi', v: '+6 pts', d: 'Abans i després, davant d’un grup de control.', back: 'Saps si el canvi ha funcionat o si ha estat el temps o la campanya.' },
    ],
  },
  en: {
    hint: 'Tap a card to see what you decide with that data.', turn: 'What you decide',
    cards: [
      { viz: 'bars', k: 'Try-ons per garment', v: '412', d: 'By style, colour and size, every day.', back: 'Which garments spark real interest, beyond what sells.' },
      { viz: 'donut', k: 'Fitting room to till', v: '27 %', d: 'How much of what’s tried on gets bought.', back: 'You spot what’s tried a lot and sold little before it hits the sales.' },
      { viz: 'clock', k: 'Time in the room', v: '6 min', d: 'How long each try-on lasts, per garment.', back: 'Lots of time and no sale usually means a size or pattern problem.' },
      { viz: 'chips', k: 'Sizes requested', v: '9', d: 'What’s asked for from the room, in stock or not.', back: 'You restock the missing size and adjust the curve of the next order.' },
      { viz: 'reasons', k: 'Why they don’t buy it', v: '5', d: 'Size, fit, price, colour or quality.', back: 'You know whether to change the price, the pattern or the supplier, without guessing.' },
      { viz: 'pairs', k: 'Garments tried together', v: '3', d: 'What goes into the same room at the same time.', back: 'You build the window and the “goes with” on data, not hunches.' },
      { viz: 'heat', k: 'Fitting room peak hours', v: '6 pm', d: 'When the rooms fill up, every day.', back: 'You put staff in the fitting room at the hour that counts.' },
      { viz: 'origin', k: 'Interest in origin', v: '41 %', d: 'Who opens the garment’s supply chain on its page.', back: 'You test whether telling where it comes from sells, against a control group.' },
      { viz: 'ab', k: 'Effect of a change', v: '+6 pts', d: 'Before and after, against a control group.', back: 'You know whether the change worked, or whether it was the weather or the campaign.' },
    ],
  },
};
