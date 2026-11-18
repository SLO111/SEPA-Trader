# Vnicorn pe Oracle Cloud (gratuit) — ghid pas cu pas

Rezultatul: aplicația rulează pe un server Oracle **gratuit și permanent**, cu ~12 GB RAM, la o adresă de forma
`https://141-147-12-34.sslip.io`. Baza de date stă pe același server, cu **backup zilnic**. Când se face push pe GitHub,
serverul **se actualizează singur** în câteva minute, ca pe Render.

Site-ul de pe Render rămâne pornit până verifici că totul merge aici.

> **Bani:** alege contul **Free Tier** și **nu face niciodată „Upgrade to Pay As You Go”**. Atunci Oracle nu îți poate
> lua bani de pe card. Cardul se folosește doar la înscriere, pentru verificare.

---

## Pasul 1 — Contul Oracle (10 minute)

1. Intră pe <https://www.oracle.com/cloud/free/> → **Start for free**.
2. Completează datele.
   - La **Home Region** alege o regiune apropiată (de exemplu *Germany Central (Frankfurt)* sau *Netherlands Northwest (Amsterdam)*).
   - Regiunea nu se mai poate schimba după aceea.
3. Adaugă cardul doar pentru verificare.
4. Când contul e gata, intri în **Oracle Cloud Console**.

## Pasul 2 — Serverul (10 minute)

1. Meniu ☰ → **Compute** → **Instances** → **Create instance**.
2. **Name:** `vnicorn`.
3. **Image and shape** → **Edit**:
   - **Image:** *Canonical Ubuntu 24.04*;
   - **Shape:** *Ampere* → **VM.Standard.A1.Flex**, cu **2 OCPU** și **12 GB** memorie. Trebuie să apară eticheta *Always Free-eligible*.
4. **Networking:** lasă setările implicite, cu *Assign a public IPv4 address* bifat.
5. **Add SSH keys:** alege **Generate a key pair for me** și apasă **Save private key**. Păstrează fișierul (de exemplu `ssh-key.key`).
6. **Create**. După 1–2 minute, instanța e *Running*. Notează **Public IP address**.

> Dacă apare *Out of capacity*, încearcă alt *Availability domain* sau reîncearcă peste câteva ore. Se întâmplă des la serverele gratuite ARM.

## Pasul 3 — Deschide porturile site-ului (3 minute)

1. Pe pagina instanței → **Virtual cloud network** → **Security Lists** → *Default Security List…*.
2. **Add Ingress Rules**, de două ori:
   - *Source CIDR* `0.0.0.0/0`, *IP Protocol* TCP, *Destination Port* `80`;
   - la fel pentru portul `443`.

(Firewall-ul din serverul propriu-zis îl deschide scriptul de la pasul 5.)

## Pasul 4 — Conectează-te la server

Pe Windows, deschide **PowerShell** în folderul unde ai salvat cheia:

```bash
ssh -i ssh-key.key ubuntu@IP_UL_TĂU
```

La prima conectare răspunde `yes`. Dacă primești o eroare de permisiuni pentru cheie, rulează o dată
`icacls ssh-key.key /inheritance:r /grant:r "$($env:USERNAME):R"` și reîncearcă.

## Pasul 5 — Instalarea (o comandă, ~10–15 minute prima dată)

Pe server:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/SLO111/SEPA-Trader.git
cd SEPA-Trader/deploy/oracle
bash setup.sh
```

> Dacă repository-ul e **privat**, `git clone` cere autentificare. Cea mai simplă cale e o *deploy key*, cheie doar de citire:
> 1. `ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 && cat ~/.ssh/id_ed25519.pub`;
> 2. copiezi rândul afișat în GitHub → repository → **Settings → Deploy keys → Add deploy key**, fără *write access*;
> 3. clonezi cu `git clone git@github.com:SLO111/SEPA-Trader.git`.

Scriptul te întreabă:
- **adresa site-ului:** apeși Enter pentru varianta `…sslip.io`;
- **e-mailul de administrator:** același ca pe Render;
- **cheia Finnhub:** o găsești în Render → Environment → `FINNHUB_API_KEY`, sau Enter ca să o adaugi mai târziu în `.env`.

Apoi instalează Docker, deschide firewall-ul, generează parolele, construiește aplicația și pornește totul. La final
îți arată adresa.

## Pasul 6 — Mută datele de pe Render (5 minute)

1. În Render → baza de date `sepa-trader-db` → **Connect** → copiază **External Database URL**. E o parolă: nu o trimite nimănui.
2. Pe server, în `SEPA-Trader/deploy/oracle`:

```bash
./migrate-from-render.sh
```

Lipește adresa când ți-o cere (nu se afișează). La final scrie câți utilizatori s-au copiat. Te autentifici pe noua adresă
cu același e-mail și aceeași parolă.

> Fă pasul ăsta **înainte să expire baza gratuită de pe Render**. Data expirării o vezi în Render, la baza de date.

## Pasul 7 — Verifică

- Deschide `https://ADRESA_TA`. Prima dată, certificatul poate dura un minut.
- **Admin → Server status:** memoria ar trebui să arate ~12 000 MB limită.
- **Admin → Regenerate signals:** pe acest server, vnicornAI se antrenează pe toate acțiunile.

## Pasul 8 — Plasa de siguranță pentru bani (2 minute)

Oracle Console → ☰ → **Billing & Cost Management** → **Budgets** → **Create Budget**:
- suma `$1`;
- alertă la 100 %, pe e-mailul tău.

Pe un cont Free Tier nu ar trebui să se declanșeze niciodată.

---

## Comenzi utile (pe server, în `SEPA-Trader/deploy/oracle`)

| Ce | Comandă |
|---|---|
| Stare | `sudo docker compose ps` |
| Loguri aplicație | `sudo docker compose logs -f app` |
| Repornire | `sudo docker compose restart app` |
| Actualizare imediată | `./update.sh --force` |
| Backup acum | `./backup.sh` (fișierele sunt în `backups/`) |
| Restaurare | `./restore.sh backups/vnicorn-AAAA-LL-ZZ.sql.gz` |
| Setări | `nano .env`, apoi `sudo docker compose up -d` |

Actualizările automate rulează la 5 minute (`update.log`), backup-ul zilnic la 03:30 UTC (`backup.log`).

## Opțional — backup și în afara serverului (Oracle Object Storage, gratuit)

Ca backup-urile să supraviețuiască chiar dacă serverul ar fi șters:

1. Oracle Console:
   - **Storage → Buckets → Create Bucket** `vnicorn-backups`;
   - profilul tău → **Customer Secret Keys** → **Generate Secret Key**. Păstrează *Access Key* și *Secret*.
2. Pe server: `sudo apt-get install -y rclone`, apoi `rclone config`, cu un remote nou `oci`:
   - tip **s3**, provider **Other**;
   - endpoint `https://NAMESPACE.compat.objectstorage.REGIUNE.oraclecloud.com`. *Namespace* îl găsești pe pagina bucket-ului.
3. Adaugă în `.env` rândul `RCLONE_REMOTE=oci:vnicorn-backups`.

De acum, fiecare backup zilnic se copiază și acolo.

## Când totul merge pe Oracle

- **Stripe** (dacă îl folosești): actualizează adresa webhook-ului la noua adresă.
- **Render:** poți opri serviciul de pe Render sau îl poți lăsa ca rezervă, fără să-l mai folosești.
