"""The most traded stocks of Europe and Asia (Yahoo Finance symbols), kept apart from the US universe by `region`.

Prices are in each market's own currency (EUR, GBp = pence, CHF, JPY, HKD, KRW, TWD, INR...). Scores, RS ratings and
ideas are computed within each region against its own benchmark. A symbol Yahoo doesn't know simply gets no prices.
"""

from __future__ import annotations

REGIONS = ("US", "EU", "ASIA")
REGION_NAMES = {"US": "United States", "EU": "Europe", "ASIA": "Asia"}
# Benchmarks for RS / relative strength within each region (downloaded with the universe)
BENCHMARKS = {"US": "SPY", "EU": "^STOXX50E", "ASIA": "AAXJ"}
BENCH_META = {
    "^STOXX50E": {"name": "Euro Stoxx 50", "sector": "Index", "exchange": "STOXX", "region": "EU", "currency": "EUR"},
    "AAXJ": {"name": "iShares MSCI All Country Asia ex Japan ETF", "sector": "ETF", "exchange": "NASDAQ", "region": "ASIA", "currency": "USD"},
}

_EX = {".AS": ("Netherlands", "EUR", "Euronext Amsterdam"), ".DE": ("Germany", "EUR", "Xetra"), ".PA": ("France", "EUR", "Euronext Paris"),
       ".L": ("United Kingdom", "GBp", "London"), ".SW": ("Switzerland", "CHF", "SIX Swiss"), ".MC": ("Spain", "EUR", "Madrid"),
       ".MI": ("Italy", "EUR", "Borsa Italiana"), ".CO": ("Denmark", "DKK", "Copenhagen"), ".ST": ("Sweden", "SEK", "Stockholm"),
       ".OL": ("Norway", "NOK", "Oslo"), ".HE": ("Finland", "EUR", "Helsinki"), ".BR": ("Belgium", "EUR", "Euronext Brussels"),
       ".T": ("Japan", "JPY", "Tokyo"), ".HK": ("Hong Kong", "HKD", "Hong Kong"), ".KS": ("South Korea", "KRW", "Korea"),
       ".TW": ("Taiwan", "TWD", "Taiwan"), ".NS": ("India", "INR", "NSE India")}

T, F, H, C, S, I, E, M, U, R = ("Technology", "Financials", "Health Care", "Consumer Discretionary", "Consumer Staples", "Industrials",
                                "Energy", "Materials", "Utilities", "Real Estate")
CM = "Communication Services"

EUROPE: dict[str, tuple[str, str]] = {
    # Netherlands
    "ASML.AS": ("ASML Holding", T), "PRX.AS": ("Prosus", CM), "INGA.AS": ("ING Group", F), "AD.AS": ("Ahold Delhaize", S),
    "HEIA.AS": ("Heineken", S), "PHIA.AS": ("Philips", H), "WKL.AS": ("Wolters Kluwer", I), "ADYEN.AS": ("Adyen", T),
    "ASM.AS": ("ASM International", T), "BESI.AS": ("BE Semiconductor", T), "RAND.AS": ("Randstad", I), "KPN.AS": ("KPN", CM),
    "NN.AS": ("NN Group", F), "ABN.AS": ("ABN AMRO", F), "MT.AS": ("ArcelorMittal", M), "IMCD.AS": ("IMCD", M),
    # Germany
    "SAP.DE": ("SAP", T), "SIE.DE": ("Siemens", I), "ALV.DE": ("Allianz", F), "DTE.DE": ("Deutsche Telekom", CM),
    "MUV2.DE": ("Munich Re", F), "MBG.DE": ("Mercedes-Benz Group", C), "BMW.DE": ("BMW", C), "VOW3.DE": ("Volkswagen", C),
    "BAS.DE": ("BASF", M), "BAYN.DE": ("Bayer", H), "IFX.DE": ("Infineon", T), "ADS.DE": ("Adidas", C), "DBK.DE": ("Deutsche Bank", F),
    "DB1.DE": ("Deutsche Börse", F), "RWE.DE": ("RWE", U), "EOAN.DE": ("E.ON", U), "HEN3.DE": ("Henkel", S), "MRK.DE": ("Merck KGaA", H),
    "RHM.DE": ("Rheinmetall", I), "ENR.DE": ("Siemens Energy", I), "SHL.DE": ("Siemens Healthineers", H), "DHL.DE": ("DHL Group", I),
    "VNA.DE": ("Vonovia", R), "CBK.DE": ("Commerzbank", F), "MTX.DE": ("MTU Aero Engines", I), "HNR1.DE": ("Hannover Re", F),
    "BEI.DE": ("Beiersdorf", S), "P911.DE": ("Porsche AG", C), "ZAL.DE": ("Zalando", C),
    # France
    "MC.PA": ("LVMH", C), "OR.PA": ("L'Oréal", S), "RMS.PA": ("Hermès", C), "TTE.PA": ("TotalEnergies", E), "SAN.PA": ("Sanofi", H),
    "AIR.PA": ("Airbus", I), "SU.PA": ("Schneider Electric", I), "AI.PA": ("Air Liquide", M), "BNP.PA": ("BNP Paribas", F),
    "CS.PA": ("AXA", F), "SAF.PA": ("Safran", I), "EL.PA": ("EssilorLuxottica", H), "DG.PA": ("Vinci", I), "KER.PA": ("Kering", C),
    "BN.PA": ("Danone", S), "GLE.PA": ("Société Générale", F), "CAP.PA": ("Capgemini", T), "ORA.PA": ("Orange", CM),
    "RI.PA": ("Pernod Ricard", S), "ACA.PA": ("Crédit Agricole", F), "ENGI.PA": ("Engie", U), "DSY.PA": ("Dassault Systèmes", T),
    "HO.PA": ("Thales", I), "SGO.PA": ("Saint-Gobain", I), "LR.PA": ("Legrand", I), "ML.PA": ("Michelin", C), "VIE.PA": ("Veolia", U),
    "PUB.PA": ("Publicis", CM), "STLAP.PA": ("Stellantis", C),
    # United Kingdom (prices in pence)
    "AZN.L": ("AstraZeneca", H), "SHEL.L": ("Shell", E), "HSBA.L": ("HSBC", F), "ULVR.L": ("Unilever", S), "BP.L": ("BP", E),
    "RIO.L": ("Rio Tinto", M), "GSK.L": ("GSK", H), "BATS.L": ("British American Tobacco", S), "DGE.L": ("Diageo", S),
    "REL.L": ("RELX", I), "LSEG.L": ("London Stock Exchange Group", F), "AAL.L": ("Anglo American", M), "GLEN.L": ("Glencore", M),
    "BARC.L": ("Barclays", F), "LLOY.L": ("Lloyds Banking Group", F), "NWG.L": ("NatWest Group", F), "RR.L": ("Rolls-Royce", I),
    "BA.L": ("BAE Systems", I), "NG.L": ("National Grid", U), "VOD.L": ("Vodafone", CM), "PRU.L": ("Prudential", F),
    "CPG.L": ("Compass Group", C), "TSCO.L": ("Tesco", S), "EXPN.L": ("Experian", I), "LGEN.L": ("Legal & General", F),
    "IMB.L": ("Imperial Brands", S), "SSE.L": ("SSE", U), "HLN.L": ("Haleon", H), "III.L": ("3i Group", F),
    # Switzerland
    "NESN.SW": ("Nestlé", S), "NOVN.SW": ("Novartis", H), "ROG.SW": ("Roche", H), "UBSG.SW": ("UBS", F), "ZURN.SW": ("Zurich Insurance", F),
    "ABBN.SW": ("ABB", I), "CFR.SW": ("Richemont", C), "SIKA.SW": ("Sika", M), "LONN.SW": ("Lonza", H), "HOLN.SW": ("Holcim", M),
    "GIVN.SW": ("Givaudan", M), "ALC.SW": ("Alcon", H), "SREN.SW": ("Swiss Re", F), "PGHN.SW": ("Partners Group", F),
    # Spain and Italy
    "SAN.MC": ("Banco Santander", F), "IBE.MC": ("Iberdrola", U), "ITX.MC": ("Inditex", C), "BBVA.MC": ("BBVA", F),
    "TEF.MC": ("Telefónica", CM), "CABK.MC": ("CaixaBank", F), "AMS.MC": ("Amadeus", T), "REP.MC": ("Repsol", E), "AENA.MC": ("Aena", I),
    "ENEL.MI": ("Enel", U), "ISP.MI": ("Intesa Sanpaolo", F), "UCG.MI": ("UniCredit", F), "ENI.MI": ("Eni", E), "RACE.MI": ("Ferrari", C),
    "G.MI": ("Generali", F), "PRY.MI": ("Prysmian", I), "LDO.MI": ("Leonardo", I), "MONC.MI": ("Moncler", C),
    # Nordics and Belgium
    "NOVO-B.CO": ("Novo Nordisk", H), "DSV.CO": ("DSV", I), "MAERSK-B.CO": ("A.P. Møller-Mærsk", I), "ORSTED.CO": ("Ørsted", U),
    "VWS.CO": ("Vestas Wind Systems", I), "CARL-B.CO": ("Carlsberg", S), "ATCO-A.ST": ("Atlas Copco", I), "INVE-B.ST": ("Investor AB", F),
    "VOLV-B.ST": ("Volvo", I), "ERIC-B.ST": ("Ericsson", T), "HM-B.ST": ("H&M", C), "SEB-A.ST": ("SEB", F), "SAND.ST": ("Sandvik", I),
    "ASSA-B.ST": ("Assa Abloy", I), "EVO.ST": ("Evolution", C), "EQNR.OL": ("Equinor", E), "DNB.OL": ("DNB Bank", F),
    "NHY.OL": ("Norsk Hydro", M), "NOKIA.HE": ("Nokia", T), "NDA-FI.HE": ("Nordea", F), "KNEBV.HE": ("Kone", I), "SAMPO.HE": ("Sampo", F),
    "ABI.BR": ("AB InBev", S), "UCB.BR": ("UCB", H), "KBC.BR": ("KBC Group", F),
}

ASIA: dict[str, tuple[str, str]] = {
    # Japan
    "7203.T": ("Toyota Motor", C), "6758.T": ("Sony Group", T), "8306.T": ("Mitsubishi UFJ Financial", F), "6861.T": ("Keyence", T),
    "9984.T": ("SoftBank Group", CM), "8035.T": ("Tokyo Electron", T), "9432.T": ("NTT", CM), "6501.T": ("Hitachi", I),
    "9983.T": ("Fast Retailing", C), "8058.T": ("Mitsubishi Corp", I), "8316.T": ("Sumitomo Mitsui Financial", F),
    "4063.T": ("Shin-Etsu Chemical", M), "6098.T": ("Recruit Holdings", I), "8001.T": ("Itochu", I), "7974.T": ("Nintendo", CM),
    "4502.T": ("Takeda Pharmaceutical", H), "6367.T": ("Daikin Industries", I), "7267.T": ("Honda Motor", C), "8411.T": ("Mizuho Financial", F),
    "6902.T": ("Denso", C), "4568.T": ("Daiichi Sankyo", H), "6981.T": ("Murata Manufacturing", T), "8031.T": ("Mitsui & Co", I),
    "9433.T": ("KDDI", CM), "6857.T": ("Advantest", T), "7741.T": ("Hoya", H), "6273.T": ("SMC", I), "4519.T": ("Chugai Pharmaceutical", H),
    "7011.T": ("Mitsubishi Heavy Industries", I), "6702.T": ("Fujitsu", T), "6503.T": ("Mitsubishi Electric", I),
    "4661.T": ("Oriental Land", C), "8766.T": ("Tokio Marine", F), "6146.T": ("Disco", T), "6723.T": ("Renesas Electronics", T),
    "7751.T": ("Canon", T), "5108.T": ("Bridgestone", C), "2914.T": ("Japan Tobacco", S), "9434.T": ("SoftBank Corp", CM),
    # Hong Kong / China
    "0700.HK": ("Tencent", CM), "9988.HK": ("Alibaba Group", C), "3690.HK": ("Meituan", C), "1299.HK": ("AIA Group", F),
    "0939.HK": ("China Construction Bank", F), "1398.HK": ("ICBC", F), "3988.HK": ("Bank of China", F), "0941.HK": ("China Mobile", CM),
    "1810.HK": ("Xiaomi", T), "9618.HK": ("JD.com", C), "1211.HK": ("BYD", C), "2318.HK": ("Ping An Insurance", F),
    "0388.HK": ("Hong Kong Exchanges", F), "9999.HK": ("NetEase", CM), "1024.HK": ("Kuaishou", CM), "0883.HK": ("CNOOC", E),
    "0857.HK": ("PetroChina", E), "2020.HK": ("Anta Sports", C), "9888.HK": ("Baidu", CM), "9868.HK": ("XPeng", C),
    "2015.HK": ("Li Auto", C), "9961.HK": ("Trip.com", C), "0981.HK": ("SMIC", T), "0016.HK": ("Sun Hung Kai Properties", R),
    "0001.HK": ("CK Hutchison", I), "0002.HK": ("CLP Holdings", U), "0011.HK": ("Hang Seng Bank", F), "0027.HK": ("Galaxy Entertainment", C),
    "1928.HK": ("Sands China", C), "2331.HK": ("Li Ning", C), "0386.HK": ("Sinopec", E), "2628.HK": ("China Life Insurance", F),
    "1876.HK": ("Budweiser APAC", S),
    # South Korea
    "005930.KS": ("Samsung Electronics", T), "000660.KS": ("SK Hynix", T), "373220.KS": ("LG Energy Solution", I),
    "207940.KS": ("Samsung Biologics", H), "005380.KS": ("Hyundai Motor", C), "000270.KS": ("Kia", C), "068270.KS": ("Celltrion", H),
    "005490.KS": ("POSCO Holdings", M), "035420.KS": ("Naver", CM), "035720.KS": ("Kakao", CM), "051910.KS": ("LG Chem", M),
    "006400.KS": ("Samsung SDI", T), "105560.KS": ("KB Financial", F), "055550.KS": ("Shinhan Financial", F), "012330.KS": ("Hyundai Mobis", C),
    "028260.KS": ("Samsung C&T", I), "066570.KS": ("LG Electronics", C), "012450.KS": ("Hanwha Aerospace", I),
    "329180.KS": ("HD Hyundai Heavy Industries", I),
    # Taiwan
    "2330.TW": ("TSMC", T), "2317.TW": ("Hon Hai (Foxconn)", T), "2454.TW": ("MediaTek", T), "2308.TW": ("Delta Electronics", T),
    "2382.TW": ("Quanta Computer", T), "2881.TW": ("Fubon Financial", F), "2882.TW": ("Cathay Financial", F), "2303.TW": ("UMC", T),
    "3711.TW": ("ASE Technology", T), "2891.TW": ("CTBC Financial", F), "2412.TW": ("Chunghwa Telecom", CM), "2886.TW": ("Mega Financial", F),
    "3008.TW": ("Largan Precision", T), "2357.TW": ("Asustek", T), "2379.TW": ("Realtek", T), "3034.TW": ("Novatek", T),
    "2345.TW": ("Accton Technology", T), "3231.TW": ("Wistron", T), "6669.TW": ("Wiwynn", T),
    # India
    "RELIANCE.NS": ("Reliance Industries", E), "TCS.NS": ("Tata Consultancy Services", T), "HDFCBANK.NS": ("HDFC Bank", F),
    "ICICIBANK.NS": ("ICICI Bank", F), "INFY.NS": ("Infosys", T), "BHARTIARTL.NS": ("Bharti Airtel", CM), "SBIN.NS": ("State Bank of India", F),
    "HINDUNILVR.NS": ("Hindustan Unilever", S), "ITC.NS": ("ITC", S), "LT.NS": ("Larsen & Toubro", I), "KOTAKBANK.NS": ("Kotak Mahindra Bank", F),
    "AXISBANK.NS": ("Axis Bank", F), "BAJFINANCE.NS": ("Bajaj Finance", F), "MARUTI.NS": ("Maruti Suzuki", C), "SUNPHARMA.NS": ("Sun Pharma", H),
    "HCLTECH.NS": ("HCLTech", T), "TITAN.NS": ("Titan Company", C), "ASIANPAINT.NS": ("Asian Paints", M), "ULTRACEMCO.NS": ("UltraTech Cement", M),
    "NTPC.NS": ("NTPC", U), "WIPRO.NS": ("Wipro", T), "POWERGRID.NS": ("Power Grid", U), "ONGC.NS": ("ONGC", E),
    "ADANIENT.NS": ("Adani Enterprises", I), "ADANIPORTS.NS": ("Adani Ports", I), "NESTLEIND.NS": ("Nestlé India", S),
    "JSWSTEEL.NS": ("JSW Steel", M), "TATASTEEL.NS": ("Tata Steel", M), "COALINDIA.NS": ("Coal India", E), "BAJAJFINSV.NS": ("Bajaj Finserv", F),
    "TECHM.NS": ("Tech Mahindra", T), "HAL.NS": ("Hindustan Aeronautics", I),
}


def _meta(sym: str, name: str, sector: str, region: str) -> dict:
    suffix = "." + sym.rsplit(".", 1)[1] if "." in sym else ""
    country, currency, exchange = _EX.get(suffix, ("", "USD", ""))
    return {"name": name, "sector": sector, "exchange": exchange, "country": country, "currency": currency, "region": region}


def entries(markets: str) -> dict[str, dict]:
    """Universe entries for the configured markets, e.g. "EU,ASIA" (empty: none), plus their benchmarks."""
    want = {m.strip().upper() for m in (markets or "").split(",") if m.strip()}
    out: dict[str, dict] = {}
    if "EU" in want:
        out.update({s: _meta(s, n, sec, "EU") for s, (n, sec) in EUROPE.items()})
    if "ASIA" in want:
        out.update({s: _meta(s, n, sec, "ASIA") for s, (n, sec) in ASIA.items()})
    for region in ("EU", "ASIA"):
        if region in want:
            b = BENCHMARKS[region]
            out[b] = BENCH_META[b]
    return out


def enabled_regions(markets: str) -> list[str]:
    want = {m.strip().upper() for m in (markets or "").split(",") if m.strip()}
    return ["US"] + [r for r in ("EU", "ASIA") if r in want]
