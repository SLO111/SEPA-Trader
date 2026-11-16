import LegalPage, { Bilingual } from "@/components/legal/LegalPage";

export const metadata = { title: "Privacy Policy · Vnicorn Investments" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" titleRo="Politica de confidențialitate">
      <Bilingual
        en={
          <>
      <p>This policy explains what personal data Vnicorn collects, why, and your rights under the EU General Data Protection Regulation (GDPR).</p>
      <h2>Data we collect</h2>
      <ul>
        <li><b>Account</b>: email, name, password (stored only as a secure hash), plan and subscription status.</li>
        <li><b>Your content</b>: watchlists, portfolios and transactions you enter or import, simulated trades, journal notes and screenshots, alerts and preferences.</li>
        <li><b>Payments</b>: handled by Stripe; we receive the subscription status and invoices, never your card number.</li>
        <li><b>Technical</b>: basic server logs (IP address, time, errors) for security and debugging.</li>
      </ul>
      <h2>Why we use it (legal basis)</h2>
      <ul>
        <li>To provide the service you signed up for (contract).</li>
        <li>To send the emails you turned on: alerts, daily summary, weekly letter (consent, which you can withdraw in Settings).</li>
        <li>To keep the service secure and meet legal obligations (legitimate interest / legal obligation).</li>
      </ul>
      <h2>Sharing</h2>
      <p>We don&apos;t sell personal data. We use processors only to run the service: hosting and database (Render), payments (Stripe), email delivery (your SMTP provider) and market-data providers (who receive ticker requests, not your identity). Public features (shared watchlists, leaderboard) show only what you choose to share.</p>
      <h2>Retention</h2>
      <p>We keep your data while your account exists. Deleting your account in Settings removes your data, except invoices we must keep by law.</p>
      <h2>Your rights</h2>
      <p>You can access, correct, export or delete your data, object to or restrict processing, and complain to your data protection authority (in Romania: ANSPDCP). Most of it you can do directly in Settings; for the rest, contact us.</p>
      <h2>Cookies</h2>
      <p>Vnicorn uses only the browser storage needed to keep you logged in and remember preferences (theme, chart settings). No advertising trackers.</p>
          </>
        }
        ro={
          <>
      <p>Această politică explică ce date personale colectează Vnicorn, de ce și care sunt drepturile tale conform Regulamentului General privind Protecția Datelor (GDPR).</p>
      <h2>Ce date colectăm</h2>
      <ul>
        <li><b>Cont</b>: email, nume, parolă (păstrată doar ca hash securizat), planul și starea abonamentului.</li>
        <li><b>Conținutul tău</b>: watchlist-uri, portofolii și tranzacții introduse sau importate, tranzacții simulate, note de jurnal și capturi, alerte și preferințe.</li>
        <li><b>Plăți</b>: gestionate de Stripe; primim starea abonamentului și facturile, niciodată numărul cardului.</li>
        <li><b>Tehnice</b>: jurnale de server de bază (adresă IP, oră, erori) pentru securitate și depanare.</li>
      </ul>
      <h2>De ce le folosim (temei legal)</h2>
      <ul>
        <li>Pentru a furniza serviciul la care te-ai înscris (contract).</li>
        <li>Pentru a trimite emailurile pe care le-ai activat: alerte, rezumatul zilnic, scrisoarea săptămânală (consimțământ, pe care îl poți retrage din Setări).</li>
        <li>Pentru securitatea serviciului și obligațiile legale (interes legitim / obligație legală).</li>
      </ul>
      <h2>Partajare</h2>
      <p>Nu vindem date personale. Folosim împuterniciți doar pentru funcționarea serviciului: găzduire și bază de date (Render), plăți (Stripe), trimiterea emailurilor (furnizorul SMTP) și furnizori de date de piață (care primesc simboluri, nu identitatea ta). Funcțiile publice (watchlist-uri partajate, clasament) arată doar ce alegi să faci public.</p>
      <h2>Păstrare</h2>
      <p>Păstrăm datele cât timp contul există. Ștergerea contului din Setări îți elimină datele, cu excepția facturilor pe care legea ne obligă să le păstrăm.</p>
      <h2>Drepturile tale</h2>
      <p>Poți accesa, corecta, exporta sau șterge datele, te poți opune prelucrării sau o poți restricționa și poți depune plângere la autoritatea de protecție a datelor (în România: ANSPDCP). Majoritatea le poți face direct din Setări; pentru rest, contactează-ne.</p>
      <h2>Cookie-uri</h2>
      <p>Vnicorn folosește doar stocarea din browser necesară pentru a te menține autentificat și pentru preferințe (temă, setări grafic). Fără trackere publicitare.</p>
          </>
        }
      />
    </LegalPage>
  );
}
