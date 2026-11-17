import LegalPage from "@/components/legal/LegalPage";

export const metadata = { title: "Privacy Policy · Vnicorn Investments" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
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
    </LegalPage>
  );
}
