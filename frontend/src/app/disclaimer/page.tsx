import LegalPage, { Bilingual } from "@/components/legal/LegalPage";

export const metadata = { title: "Risk Disclaimer · Vnicorn Investments" };

export default function DisclaimerPage() {
  return (
    <LegalPage title="Risk Disclaimer" titleRo="Avertisment de risc">
      <Bilingual
        en={
          <>
      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3"><b>Vnicorn is an educational simulation.</b> It does not place real orders and does not give investment advice.</p>
      <h2>Simulated, educational content</h2>
      <ul>
        <li>Trade ideas, vnicornAI picks and probabilities, Move Detector scores, vnicorn Pulse, alerts, letters, backtests and the leaderboard are <b>generated automatically</b> from public market data with rules and statistical models. They are examples for learning, not recommendations for you.</li>
        <li>They do not consider your financial situation, goals or risk tolerance.</li>
        <li>Simulated trades assume fills at the stated prices, without slippage, commissions, taxes or liquidity limits. Real results differ.</li>
        <li>Backtests and track records describe the past. <b>Past performance, real or simulated, does not guarantee future results.</b></li>
      </ul>
      <h2>Risk of trading</h2>
      <ul>
        <li>Investing in stocks involves risk, including the loss of all the money invested. Short selling and leverage can lose more than the amount invested.</li>
        <li>Only invest money you can afford to lose, and consider advice from a licensed, independent financial adviser.</li>
      </ul>
      <h2>Data</h2>
      <p>Prices, fundamentals, earnings dates and news come from third-party sources, may be delayed (usually 15 minutes or end-of-day), incomplete or wrong, and may change without notice.</p>
      <h2>No relationship</h2>
      <p>Vnicorn is not affiliated with the companies, exchanges, brokers or investors mentioned. Methods inspired by published approaches (such as stage analysis or trend templates) are our own implementations.</p>
          </>
        }
        ro={
          <>
      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3"><b>Vnicorn este o simulare educațională.</b> Nu plasează ordine reale și nu oferă sfaturi de investiții.</p>
      <h2>Conținut simulat și educațional</h2>
      <ul>
        <li>Ideile de tranzacționare, vnicornAI picks și probabilitățile, scorurile Move Detector, vnicorn Pulse, alertele, scrisorile, backtesturile și clasamentul sunt <b>generate automat</b> din date publice de piață, cu reguli și modele statistice. Sunt exemple pentru învățare, nu recomandări pentru tine.</li>
        <li>Nu țin cont de situația ta financiară, obiectivele sau toleranța ta la risc.</li>
        <li>Tranzacțiile simulate presupun executarea la prețurile indicate, fără alunecare de preț, comisioane, taxe sau limite de lichiditate. Rezultatele reale diferă.</li>
        <li>Backtesturile și istoricul rezultatelor descriu trecutul. <b>Performanțele trecute, reale sau simulate, nu garantează rezultatele viitoare.</b></li>
      </ul>
      <h2>Riscul tranzacționării</h2>
      <ul>
        <li>Investițiile în acțiuni implică riscuri, inclusiv pierderea întregii sume investite. Vânzarea în lipsă (short) și efectul de levier pot duce la pierderi mai mari decât suma investită.</li>
        <li>Investește doar bani pe care îți permiți să-i pierzi și ia în considerare sfatul unui consultant financiar independent și autorizat.</li>
      </ul>
      <h2>Date</h2>
      <p>Prețurile, datele fundamentale, datele raportărilor și știrile provin din surse terțe, pot fi întârziate (de obicei 15 minute sau la închidere), incomplete sau greșite și se pot schimba fără notificare.</p>
      <h2>Nicio afiliere</h2>
      <p>Vnicorn nu este afiliat companiilor, burselor, brokerilor sau investitorilor menționați. Metodele inspirate din abordări publicate (precum analiza pe etape sau trend template) sunt implementări proprii.</p>
          </>
        }
      />
    </LegalPage>
  );
}
