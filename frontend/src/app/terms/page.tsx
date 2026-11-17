import LegalPage from "@/components/legal/LegalPage";

export const metadata = { title: "Terms of Service · Vnicorn Investments" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
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
    </LegalPage>
  );
}
