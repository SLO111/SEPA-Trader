import LegalPage, { Bilingual } from "@/components/legal/LegalPage";

export const metadata = { title: "Terms of Service · Vnicorn Investments" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" titleRo="Termeni și condiții">
      <Bilingual
        en={
          <>
      <p>These terms govern your use of Vnicorn Investments (&quot;Vnicorn&quot;, &quot;we&quot;), a website and application for learning about stock market analysis. By creating an account or using the service you agree to them.</p>
      <h2>1. What Vnicorn is</h2>
      <ul>
        <li>Vnicorn is an <b>educational and simulation platform</b>. It shows charts, statistics, screens, rule-based and machine-learning analyses, and lets you record <b>simulated</b> trades and your own portfolio records.</li>
        <li>Vnicorn is <b>not a broker</b>, does not hold money or securities, does not connect to brokerage accounts and <b>never places orders</b>. Buy / Sell / Short buttons only create records inside the app.</li>
        <li>Vnicorn is <b>not an investment adviser</b>. Nothing on the platform, including trade ideas, vnicornAI picks, scores, alerts, letters or the academy, is a personal recommendation or an offer to buy or sell any security.</li>
      </ul>
      <h2>2. Your responsibility</h2>
      <ul>
        <li>You decide on your own investments. Before acting on anything you read here, do your own research and, if needed, talk to a licensed financial adviser.</li>
        <li>You are responsible for the accuracy of the data you enter or import (transactions, positions) and for keeping your password safe.</li>
        <li>You must be at least 18 years old.</li>
      </ul>
      <h2>3. Data and availability</h2>
      <ul>
        <li>Market data comes from third parties, may be delayed, incomplete or wrong, and is provided &quot;as is&quot;. Simulated results and past performance do not predict future results.</li>
        <li>We may change, suspend or discontinue features, and we don&apos;t guarantee uninterrupted service.</li>
      </ul>
      <h2>4. Subscriptions</h2>
      <ul>
        <li>Paid plans renew automatically each month or year until canceled. You can cancel at any time in Settings; access continues until the end of the paid period.</li>
        <li>New accounts may receive a free Premium trial. When it ends, the account returns to Free unless you subscribe. Prices may change with notice before your next renewal.</li>
        <li>Payments are processed by Stripe. EU consumers have the statutory right of withdrawal within 14 days, which ends once the digital service has started with your consent.</li>
      </ul>
      <h2>5. Acceptable use</h2>
      <ul>
        <li>Don&apos;t copy, resell or redistribute the data or content, scrape the service, share accounts, or try to break its security.</li>
        <li>Content you share publicly (shared watchlists, leaderboard name) must be lawful and not misleading; we may remove it.</li>
      </ul>
      <h2>6. Liability</h2>
      <p>To the maximum extent permitted by law, Vnicorn is not liable for any trading or investment losses, lost profits, or indirect damages arising from the use of the service. Our total liability is limited to the amount you paid us in the last 12 months. Nothing in these terms limits liability that cannot be limited by law.</p>
      <h2>7. Changes and contact</h2>
      <p>We may update these terms; we will tell you about material changes in the app. Continued use means you accept the new terms. Questions: use the contact address shown on the website.</p>
          </>
        }
        ro={
          <>
      <p>Acești termeni reglementează folosirea Vnicorn Investments („Vnicorn”, „noi”), un site și o aplicație pentru învățarea analizei pieței de acțiuni. Prin crearea unui cont sau folosirea serviciului îi accepți.</p>
      <h2>1. Ce este Vnicorn</h2>
      <ul>
        <li>Vnicorn este o <b>platformă educațională și de simulare</b>. Afișează grafice, statistici, filtre, analize bazate pe reguli și pe învățare automată și îți permite să înregistrezi tranzacții <b>simulate</b> și propriile evidențe de portofoliu.</li>
        <li>Vnicorn <b>nu este broker</b>, nu păstrează bani sau titluri, nu se conectează la conturi de brokeraj și <b>nu plasează niciodată ordine</b>. Butoanele Buy / Sell / Short doar creează înregistrări în aplicație.</li>
        <li>Vnicorn <b>nu este consultant de investiții</b>. Nimic de pe platformă, inclusiv ideile de tranzacționare, vnicornAI picks, scorurile, alertele, scrisorile sau academia, nu este o recomandare personală sau o ofertă de a cumpăra ori vinde vreun titlu.</li>
      </ul>
      <h2>2. Responsabilitatea ta</h2>
      <ul>
        <li>Tu decizi asupra propriilor investiții. Înainte să acționezi pe baza a ceea ce citești aici, fă-ți propria analiză și, la nevoie, discută cu un consultant financiar autorizat.</li>
        <li>Răspunzi de corectitudinea datelor pe care le introduci sau importi și de păstrarea parolei în siguranță.</li>
        <li>Trebuie să ai cel puțin 18 ani.</li>
      </ul>
      <h2>3. Date și disponibilitate</h2>
      <ul>
        <li>Datele de piață provin de la terți, pot fi întârziate, incomplete sau greșite și sunt oferite „ca atare”. Rezultatele simulate și performanțele trecute nu prezic rezultatele viitoare.</li>
        <li>Putem modifica, suspenda sau întrerupe funcții și nu garantăm funcționarea neîntreruptă.</li>
      </ul>
      <h2>4. Abonamente</h2>
      <ul>
        <li>Planurile plătite se reînnoiesc automat lunar sau anual până la anulare. Poți anula oricând din Setări; accesul continuă până la finalul perioadei plătite.</li>
        <li>Conturile noi pot primi o perioadă gratuită de Premium. La final, contul revine la Free dacă nu te abonezi. Prețurile se pot schimba cu notificare înainte de următoarea reînnoire.</li>
        <li>Plățile sunt procesate de Stripe. Consumatorii din UE au dreptul legal de retragere în 14 zile, care încetează odată ce serviciul digital a început cu acordul tău.</li>
      </ul>
      <h2>5. Utilizare acceptabilă</h2>
      <ul>
        <li>Nu copia, revinde sau redistribui datele ori conținutul, nu extrage automat date din serviciu, nu împărți conturi și nu încerca să-i compromiți securitatea.</li>
        <li>Conținutul pe care îl faci public (watchlist-uri partajate, numele din clasament) trebuie să fie legal și să nu inducă în eroare; îl putem elimina.</li>
      </ul>
      <h2>6. Răspundere</h2>
      <p>În limita maximă permisă de lege, Vnicorn nu răspunde pentru pierderi din tranzacționare sau investiții, profituri nerealizate ori daune indirecte rezultate din folosirea serviciului. Răspunderea noastră totală este limitată la suma plătită nouă în ultimele 12 luni. Nimic din acești termeni nu limitează răspunderea care nu poate fi limitată prin lege.</p>
      <h2>7. Modificări și contact</h2>
      <p>Putem actualiza acești termeni; te vom anunța în aplicație despre schimbările importante. Folosirea în continuare înseamnă acceptarea noilor termeni. Întrebări: folosește adresa de contact de pe site.</p>
          </>
        }
      />
    </LegalPage>
  );
}
