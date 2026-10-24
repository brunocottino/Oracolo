"""Universo di titoli e indici per mercato (modificabile liberamente)."""

INDICES = {
    "^GSPC": "S&P 500",
    "^NDX": "Nasdaq 100",
    "^DJI": "Dow Jones",
    "^RUT": "Russell 2000",
    "FTSEMIB.MI": "FTSE MIB",
    "^STOXX50E": "Euro Stoxx 50",
    "^GDAXI": "DAX",
    "^FCHI": "CAC 40",
    "^FTSE": "FTSE 100",
    "^SSMI": "SMI (Svizzera)",
    "^N225": "Nikkei 225",
    "^HSI": "Hang Seng",
    "000300.SS": "CSI 300 (Cina)",
    "EEM": "ETF Mercati Emergenti",
    "^BSESN": "Sensex (India)",
}

MARKETS = {
    "USA": {
        "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon",
        "GOOGL": "Alphabet", "META": "Meta", "AVGO": "Broadcom", "TSLA": "Tesla",
        "JPM": "JPMorgan", "V": "Visa", "LLY": "Eli Lilly", "UNH": "UnitedHealth",
        "XOM": "Exxon Mobil", "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble",
        "LMT": "Lockheed Martin", "RTX": "RTX", "NOC": "Northrop Grumman",
        "AMD": "AMD", "ASML": "ASML (ADR)", "COST": "Costco", "KO": "Coca-Cola",
    },
    "Italia": {
        "ENI.MI": "Eni", "ENEL.MI": "Enel", "ISP.MI": "Intesa Sanpaolo",
        "UCG.MI": "UniCredit", "RACE.MI": "Ferrari", "STLAM.MI": "Stellantis",
        "G.MI": "Generali", "LDO.MI": "Leonardo", "PRY.MI": "Prysmian",
        "MONC.MI": "Moncler", "STMMI.MI": "STMicroelectronics", "TIT.MI": "Telecom Italia",
        "MB.MI": "Mediobanca", "BMED.MI": "Banca Mediolanum", "FBK.MI": "FinecoBank",
        "SRG.MI": "Snam", "TRN.MI": "Terna", "PST.MI": "Poste Italiane",
    },
    "Europa": {
        "ASML.AS": "ASML", "MC.PA": "LVMH", "SAP.DE": "SAP", "SIE.DE": "Siemens",
        "TTE.PA": "TotalEnergies", "AIR.PA": "Airbus", "RMS.PA": "Hermès",
        "OR.PA": "L'Oréal", "NOVO-B.CO": "Novo Nordisk", "NESN.SW": "Nestlé",
        "ROG.SW": "Roche", "RHM.DE": "Rheinmetall", "SAF.PA": "Safran",
        "ALV.DE": "Allianz", "BNP.PA": "BNP Paribas", "SAN.MC": "Santander",
        "SHEL.L": "Shell", "AZN.L": "AstraZeneca", "BA.L": "BAE Systems",
    },
    "Asia/Emergenti": {
        "BABA": "Alibaba (ADR)", "0700.HK": "Tencent", "PDD": "PDD Holdings",
        "JD": "JD.com (ADR)", "TSM": "TSMC (ADR)", "7203.T": "Toyota",
        "6758.T": "Sony", "9984.T": "SoftBank", "005930.KS": "Samsung Electronics",
        "INFY": "Infosys (ADR)", "HDB": "HDFC Bank (ADR)", "MELI": "MercadoLibre",
        "VALE": "Vale (ADR)", "BIDU": "Baidu (ADR)",
    },
}


def is_index(ticker: str) -> bool:
    t = ticker.upper()
    return t.startswith("^") or t in INDICES or t in {"EEM", "SPY", "QQQ", "VGK", "EWJ", "FXI", "MCHI"}


def name_of(ticker: str) -> str:
    t = ticker.upper()
    if t in INDICES:
        return INDICES[t]
    for m in MARKETS.values():
        if t in m:
            return m[t]
    return t


def market_of(ticker: str) -> str:
    t = ticker.upper()
    if t in INDICES:
        return "Indici"
    for k, m in MARKETS.items():
        if t in m:
            return k
    return "Altro"


def all_tickers():
    out = list(INDICES.keys())
    for m in MARKETS.values():
        out += list(m.keys())
    return out
