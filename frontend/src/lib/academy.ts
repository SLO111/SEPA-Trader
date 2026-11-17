export type Lesson = {
  slug: string;
  minutes: number;
  title: string;
  body: string[];
  takeaways: string[];
  tryHref: string;
  tryLabel: string;
};

/** SEPA Academy: short lessons, each tied to the feature that applies it. Educational content, not investment advice. */
export const LESSONS: Lesson[] = [
  {
    slug: "stages",
    minutes: 4,
    title: "1. The four stages of a stock",
    body: [
        "Stocks move in cycles. Stage analysis splits a cycle into four parts, read from the 30-week moving average and the price around it.",
        "Stage 1 (accumulation): the price goes sideways around a flat 30-week average after a decline. Stage 2 (markup): the price is above a rising average, with higher highs and higher lows. Stage 3 (distribution): the advance stalls and the average flattens. Stage 4 (markdown): the price falls below a declining average.",
        "Almost all big winners make their biggest gains in Stage 2. Buying in Stage 4 because a stock 'looks cheap' is the most common beginner mistake.",
      ],
    takeaways: ["Own stocks in Stage 2", "Avoid Stage 4, however cheap it looks", "Watch Stage 1 bases for the next Stage 2"],
    tryHref: "/chart",
    tryLabel: "Add the 'Market Cycle Stage' indicator on a chart",
  },
  {
    slug: "trend-template",
    minutes: 4,
    title: "2. The Trend Template",
    body: [
        "The Trend Template is a checklist that confirms a stock is in a healthy Stage 2 uptrend before you even look at a setup.",
        "The price is above its 50, 150 and 200-day averages; the 50 is above the 150 and the 200; the 200-day is rising; the price is at least 30% above its 52-week low and within 25% of its 52-week high; and its relative strength is high.",
        "It doesn't tell you when to buy: it tells you which stocks are worth watching. Passing all criteria filters out most of the market.",
      ],
    takeaways: ["A filter, not a buy signal", "All criteria = a confirmed uptrend", "Rising 200-day average is non-negotiable"],
    tryHref: "/markets?tab=screener",
    tryLabel: "See which stocks pass it in the Screener",
  },
  {
    slug: "relative-strength",
    minutes: 3,
    title: "3. Relative strength and the RS line",
    body: [
        "Relative strength compares a stock with the market. An RS Rating of 90 means the stock did better than 90% of the stocks we track over the past year.",
        "The RS line is the stock's price divided by the S&P 500. When it rises, the stock beats the market. A powerful clue: the RS line making a new high before the price does, often during a market pullback.",
        "Leaders hold up best in corrections and are the first to break out when the market turns up.",
      ],
    takeaways: ["Prefer RS 80+", "RS line new high before price = leader", "Strength in a weak market is the best sign"],
    tryHref: "/chart",
    tryLabel: "Add the 'RS line vs S&P 500' indicator",
  },
  {
    slug: "vcp",
    minutes: 5,
    title: "4. Volatility contraction and the pivot",
    body: [
        "Before a big move, strong stocks often 'tighten up': each pullback inside the base is smaller than the one before (for example −25%, −12%, −6%) and volume dries up. This is a volatility contraction pattern (VCP).",
        "The pivot is the top of the last, tightest contraction. A move through it on rising volume is the classic buy point; the low of the last contraction is a logical stop, often only 5-8% away.",
        "Tight bases mean small risk. Wide, loose, sloppy bases are where traders get shaken out.",
      ],
    takeaways: ["Contractions get smaller", "Volume dries up near the pivot", "Buy the pivot breakout, stop under the last low"],
    tryHref: "/chart",
    tryLabel: "Turn on 'VCP + pivot' and 'Squeeze Momentum'",
  },
  {
    slug: "entries-risk",
    minutes: 5,
    title: "5. Entries, stops and position size",
    body: [
        "Decide where you're wrong before you buy. The stop goes where the setup fails (under the pivot's last low, or 1-2 ATR away), not at a random percentage.",
        "Size the position from the risk: account × risk per trade ÷ (entry − stop). With $10,000, 1% risk and a $5 stop distance, that's 20 shares. Small losses keep you in the game.",
        "Look for at least 2-3 times as much reward as risk. A strategy that wins only 40% of the time still makes money when the winners are three times the losers.",
      ],
    takeaways: ["Stop first, then size", "Risk 0.5-2% of the account per trade", "Reward at least 2× the risk"],
    tryHref: "/chart",
    tryLabel: "Open the Buy ticket's position-size calculator",
  },
  {
    slug: "selling",
    minutes: 4,
    title: "6. Selling: trim, target and trailing",
    body: [
        "Buying is half the job. A simple plan: sell half at the first target (the trim, around 1.5-2R), move the stop on the rest to break-even, and let the remainder run to the target or a trailing stop.",
        "Sell into strength when a stock is extended far above its 50-day average; sell on weakness when it breaks a key average on heavy volume.",
        "Never let a good gain turn into a loss. TradeGrader shows whether you tend to sell too early or too late.",
      ],
    takeaways: ["Trim half at ~2R", "Stop to break-even after the trim", "Trail the rest"],
    tryHref: "/backtest?tab=grader",
    tryLabel: "Grade your exits in TradeGrader",
  },
  {
    slug: "exposure",
    minutes: 3,
    title: "7. Reading the market: how much to invest",
    body: [
        "Three out of four stocks follow the market. Even the best setup struggles when the indexes are in a downtrend.",
        "Watch the index stages, breadth (the share of stocks above their 50-day average), new highs vs new lows, and distribution days: index declines on higher volume. Five or more in a month warn of institutional selling.",
        "Raise your exposure when conditions improve and cut it when they deteriorate: being in cash is a position too.",
      ],
    takeaways: ["Trade with the market, not against it", "Count distribution days", "Cash is a position"],
    tryHref: "/markets",
    tryLabel: "Check today's Market exposure meter",
  },
  {
    slug: "review",
    minutes: 3,
    title: "8. Reviewing your trades",
    body: [
        "The fastest way to improve is to study your own trades. Write down the setup and how you felt, attach the chart, and review every month.",
        "Look for patterns: which setups make money, whether FOMO or revenge trades lose, whether you buy late (extended) or sell early.",
        "Fix one mistake at a time. A small improvement in your average loss or win changes your results more than any new indicator.",
      ],
    takeaways: ["Journal every trade", "Find your best setup", "Fix one mistake at a time"],
    tryHref: "/backtest?tab=analytics",
    tryLabel: "See your results by setup and emotion",
  },
];
