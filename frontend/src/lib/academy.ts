import type { Lang } from "./i18n";

export type Lesson = {
  slug: string;
  minutes: number;
  title: Record<Lang, string>;
  body: Record<Lang, string[]>;
  takeaways: Record<Lang, string[]>;
  tryHref: string;
  tryLabel: Record<Lang, string>;
};

/** SEPA Academy: short lessons, each tied to the feature that applies it. Educational content, not investment advice. */
export const LESSONS: Lesson[] = [
  {
    slug: "stages",
    minutes: 4,
    title: { en: "1. The four stages of a stock", ro: "1. Cele patru etape ale unei acțiuni" },
    body: {
      en: [
        "Stocks move in cycles. Stage analysis splits a cycle into four parts, read from the 30-week moving average and the price around it.",
        "Stage 1 (accumulation): the price goes sideways around a flat 30-week average after a decline. Stage 2 (markup): the price is above a rising average, with higher highs and higher lows. Stage 3 (distribution): the advance stalls and the average flattens. Stage 4 (markdown): the price falls below a declining average.",
        "Almost all big winners make their biggest gains in Stage 2. Buying in Stage 4 because a stock 'looks cheap' is the most common beginner mistake.",
      ],
      ro: [
        "Acțiunile se mișcă în cicluri. Analiza pe etape împarte un ciclu în patru părți, citite din media mobilă de 30 de săptămâni și din prețul din jurul ei.",
        "Etapa 1 (acumulare): prețul merge lateral în jurul unei medii de 30 de săptămâni plate, după o scădere. Etapa 2 (creștere): prețul e peste o medie în urcare, cu maxime și minime tot mai sus. Etapa 3 (distribuție): urcarea se oprește și media se aplatizează. Etapa 4 (scădere): prețul coboară sub o medie în scădere.",
        "Aproape toți marii câștigători fac cele mai mari creșteri în Etapa 2. A cumpăra în Etapa 4 pentru că o acțiune „pare ieftină” e cea mai des întâlnită greșeală de începător.",
      ],
    },
    takeaways: {
      en: ["Own stocks in Stage 2", "Avoid Stage 4, however cheap it looks", "Watch Stage 1 bases for the next Stage 2"],
      ro: ["Deține acțiuni în Etapa 2", "Evită Etapa 4, oricât de ieftină pare", "Urmărește bazele din Etapa 1 pentru următoarea Etapă 2"],
    },
    tryHref: "/chart",
    tryLabel: { en: "Add the 'Market Cycle Stage' indicator on a chart", ro: "Adaugă indicatorul „Market Cycle Stage” pe un grafic" },
  },
  {
    slug: "trend-template",
    minutes: 4,
    title: { en: "2. The Trend Template", ro: "2. Trend Template" },
    body: {
      en: [
        "The Trend Template is a checklist that confirms a stock is in a healthy Stage 2 uptrend before you even look at a setup.",
        "The price is above its 50, 150 and 200-day averages; the 50 is above the 150 and the 200; the 200-day is rising; the price is at least 30% above its 52-week low and within 25% of its 52-week high; and its relative strength is high.",
        "It doesn't tell you when to buy: it tells you which stocks are worth watching. Passing all criteria filters out most of the market.",
      ],
      ro: [
        "Trend Template e o listă de verificare care confirmă că o acțiune e într-o tendință sănătoasă de Etapa 2, înainte să te uiți la vreun setup.",
        "Prețul e peste mediile de 50, 150 și 200 de zile; media de 50 e peste cele de 150 și 200; media de 200 de zile urcă; prețul e cu cel puțin 30% peste minimul pe 52 de săptămâni și la cel mult 25% sub maximul pe 52 de săptămâni; iar puterea relativă e mare.",
        "Nu îți spune când să cumperi, ci care acțiuni merită urmărite. Trecerea tuturor criteriilor elimină cea mai mare parte a pieței.",
      ],
    },
    takeaways: {
      en: ["A filter, not a buy signal", "All criteria = a confirmed uptrend", "Rising 200-day average is non-negotiable"],
      ro: ["Un filtru, nu un semnal de cumpărare", "Toate criteriile = tendință confirmată", "Media de 200 de zile în urcare e obligatorie"],
    },
    tryHref: "/markets?tab=screener",
    tryLabel: { en: "See which stocks pass it in the Screener", ro: "Vezi în Screener ce acțiuni îl trec" },
  },
  {
    slug: "relative-strength",
    minutes: 3,
    title: { en: "3. Relative strength and the RS line", ro: "3. Puterea relativă și linia RS" },
    body: {
      en: [
        "Relative strength compares a stock with the market. An RS Rating of 90 means the stock did better than 90% of the stocks we track over the past year.",
        "The RS line is the stock's price divided by the S&P 500. When it rises, the stock beats the market. A powerful clue: the RS line making a new high before the price does, often during a market pullback.",
        "Leaders hold up best in corrections and are the first to break out when the market turns up.",
      ],
      ro: [
        "Puterea relativă compară o acțiune cu piața. Un RS Rating de 90 înseamnă că acțiunea s-a descurcat mai bine decât 90% din acțiunile urmărite, în ultimul an.",
        "Linia RS e prețul acțiunii împărțit la S&P 500. Când urcă, acțiunea bate piața. Un indiciu puternic: linia RS face maxim nou înaintea prețului, adesea în timpul unei corecții a pieței.",
        "Liderii rezistă cel mai bine în corecții și sunt primii care ies din bază când piața se întoarce în sus.",
      ],
    },
    takeaways: {
      en: ["Prefer RS 80+", "RS line new high before price = leader", "Strength in a weak market is the best sign"],
      ro: ["Preferă RS 80+", "Linia RS la maxim înaintea prețului = lider", "Puterea într-o piață slabă e cel mai bun semn"],
    },
    tryHref: "/chart",
    tryLabel: { en: "Add the 'RS line vs S&P 500' indicator", ro: "Adaugă indicatorul „RS line vs S&P 500”" },
  },
  {
    slug: "vcp",
    minutes: 5,
    title: { en: "4. Volatility contraction and the pivot", ro: "4. Contracția volatilității și pivotul" },
    body: {
      en: [
        "Before a big move, strong stocks often 'tighten up': each pullback inside the base is smaller than the one before (for example −25%, −12%, −6%) and volume dries up. This is a volatility contraction pattern (VCP).",
        "The pivot is the top of the last, tightest contraction. A move through it on rising volume is the classic buy point; the low of the last contraction is a logical stop, often only 5-8% away.",
        "Tight bases mean small risk. Wide, loose, sloppy bases are where traders get shaken out.",
      ],
      ro: [
        "Înainte de o mișcare mare, acțiunile puternice se „strâng”: fiecare retragere din bază e mai mică decât cea dinainte (de exemplu −25%, −12%, −6%) și volumul scade. Acesta e un tipar de contracție a volatilității (VCP).",
        "Pivotul e vârful ultimei contracții, cea mai strânsă. Trecerea peste el pe volum în creștere e punctul clasic de cumpărare; minimul ultimei contracții e un stop logic, adesea la doar 5-8% distanță.",
        "Bazele strânse înseamnă risc mic. Bazele largi și dezordonate sunt cele în care traderii sunt scoși din poziții.",
      ],
    },
    takeaways: {
      en: ["Contractions get smaller", "Volume dries up near the pivot", "Buy the pivot breakout, stop under the last low"],
      ro: ["Contracțiile devin tot mai mici", "Volumul scade lângă pivot", "Cumperi la ieșirea peste pivot, stop sub ultimul minim"],
    },
    tryHref: "/chart",
    tryLabel: { en: "Turn on 'VCP + pivot' and 'Squeeze Momentum'", ro: "Activează „VCP + pivot” și „Squeeze Momentum”" },
  },
  {
    slug: "entries-risk",
    minutes: 5,
    title: { en: "5. Entries, stops and position size", ro: "5. Intrări, stopuri și mărimea poziției" },
    body: {
      en: [
        "Decide where you're wrong before you buy. The stop goes where the setup fails (under the pivot's last low, or 1-2 ATR away), not at a random percentage.",
        "Size the position from the risk: account × risk per trade ÷ (entry − stop). With $10,000, 1% risk and a $5 stop distance, that's 20 shares. Small losses keep you in the game.",
        "Look for at least 2-3 times as much reward as risk. A strategy that wins only 40% of the time still makes money when the winners are three times the losers.",
      ],
      ro: [
        "Decide unde greșești înainte să cumperi. Stopul se pune acolo unde setup-ul eșuează (sub ultimul minim din pivot sau la 1-2 ATR), nu la un procent oarecare.",
        "Mărimea poziției vine din risc: cont × risc pe tranzacție ÷ (intrare − stop). Cu 10.000 $, risc de 1% și 5 $ până la stop, ies 20 de acțiuni. Pierderile mici te țin în joc.",
        "Caută un câștig potențial de cel puțin 2-3 ori riscul. O strategie care câștigă doar 40% din timp tot face bani dacă tranzacțiile câștigătoare sunt de trei ori mai mari decât cele pierzătoare.",
      ],
    },
    takeaways: {
      en: ["Stop first, then size", "Risk 0.5-2% of the account per trade", "Reward at least 2× the risk"],
      ro: ["Întâi stopul, apoi mărimea", "Riscă 0,5-2% din cont pe tranzacție", "Câștig de cel puțin 2× riscul"],
    },
    tryHref: "/chart",
    tryLabel: { en: "Open the Buy ticket's position-size calculator", ro: "Deschide calculatorul de poziție din tichetul Buy" },
  },
  {
    slug: "selling",
    minutes: 4,
    title: { en: "6. Selling: trim, target and trailing", ro: "6. Vânzarea: trim, target și stop mobil" },
    body: {
      en: [
        "Buying is half the job. A simple plan: sell half at the first target (the trim, around 1.5-2R), move the stop on the rest to break-even, and let the remainder run to the target or a trailing stop.",
        "Sell into strength when a stock is extended far above its 50-day average; sell on weakness when it breaks a key average on heavy volume.",
        "Never let a good gain turn into a loss. TradeGrader shows whether you tend to sell too early or too late.",
      ],
      ro: [
        "Cumpărarea e doar jumătate din treabă. Un plan simplu: vinzi jumătate la primul target (trim, în jur de 1,5-2R), muți stopul pe restul la prețul de intrare și lași restul să meargă până la target sau la un stop mobil.",
        "Vinde pe putere când acțiunea e mult peste media de 50 de zile; vinde pe slăbiciune când rupe o medie importantă pe volum mare.",
        "Nu lăsa niciodată un câștig bun să devină pierdere. TradeGrader îți arată dacă tinzi să vinzi prea devreme sau prea târziu.",
      ],
    },
    takeaways: {
      en: ["Trim half at ~2R", "Stop to break-even after the trim", "Trail the rest"],
      ro: ["Vinde jumătate la ~2R", "Stopul la intrare după trim", "Stop mobil pentru rest"],
    },
    tryHref: "/backtest?tab=grader",
    tryLabel: { en: "Grade your exits in TradeGrader", ro: "Notează-ți ieșirile în TradeGrader" },
  },
  {
    slug: "exposure",
    minutes: 3,
    title: { en: "7. Reading the market: how much to invest", ro: "7. Citirea pieței: cât să investești" },
    body: {
      en: [
        "Three out of four stocks follow the market. Even the best setup struggles when the indexes are in a downtrend.",
        "Watch the index stages, breadth (the share of stocks above their 50-day average), new highs vs new lows, and distribution days: index declines on higher volume. Five or more in a month warn of institutional selling.",
        "Raise your exposure when conditions improve and cut it when they deteriorate: being in cash is a position too.",
      ],
      ro: [
        "Trei din patru acțiuni urmează piața. Chiar și cel mai bun setup are de suferit când indicii sunt în scădere.",
        "Urmărește etapele indicilor, lățimea pieței (procentul de acțiuni peste media de 50 de zile), maximele noi față de minimele noi și zilele de distribuție: scăderi ale indicelui pe volum mai mare. Cinci sau mai multe într-o lună semnalează vânzări instituționale.",
        "Mărește expunerea când condițiile se îmbunătățesc și redu-o când se strică: să stai pe lichidități e tot o poziție.",
      ],
    },
    takeaways: {
      en: ["Trade with the market, not against it", "Count distribution days", "Cash is a position"],
      ro: ["Tranzacționează cu piața, nu împotriva ei", "Numără zilele de distribuție", "Lichiditatea e tot o poziție"],
    },
    tryHref: "/markets",
    tryLabel: { en: "Check today's Market exposure meter", ro: "Vezi indicatorul de expunere de azi" },
  },
  {
    slug: "review",
    minutes: 3,
    title: { en: "8. Reviewing your trades", ro: "8. Analiza propriilor tranzacții" },
    body: {
      en: [
        "The fastest way to improve is to study your own trades. Write down the setup and how you felt, attach the chart, and review every month.",
        "Look for patterns: which setups make money, whether FOMO or revenge trades lose, whether you buy late (extended) or sell early.",
        "Fix one mistake at a time. A small improvement in your average loss or win changes your results more than any new indicator.",
      ],
      ro: [
        "Cel mai rapid mod de a progresa e să-ți studiezi propriile tranzacții. Notează setup-ul și ce ai simțit, atașează graficul și revizuiește lunar.",
        "Caută tipare: ce setup-uri aduc bani, dacă tranzacțiile din FOMO sau „răzbunare” pierd, dacă intri târziu (prea departe de bază) sau ieși prea devreme.",
        "Corectează câte o greșeală pe rând. O mică îmbunătățire a pierderii sau câștigului mediu schimbă rezultatele mai mult decât orice indicator nou.",
      ],
    },
    takeaways: {
      en: ["Journal every trade", "Find your best setup", "Fix one mistake at a time"],
      ro: ["Notează fiecare tranzacție", "Găsește-ți cel mai bun setup", "Corectează câte o greșeală"],
    },
    tryHref: "/backtest?tab=analytics",
    tryLabel: { en: "See your results by setup and emotion", ro: "Vezi rezultatele pe setup și emoție" },
  },
];
