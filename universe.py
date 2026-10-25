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
    "ETF UCITS": {
        "SWDA.MI": "iShares Core MSCI World", "VWCE.DE": "Vanguard FTSE All-World",
        "CSSPX.MI": "iShares Core S&P 500", "CSNDX.MI": "iShares Nasdaq 100",
        "SMEA.MI": "iShares Core MSCI Europe", "EIMI.MI": "iShares Core MSCI EM IMI",
        "XDWT.DE": "Xtrackers MSCI World IT",
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
    return t.startswith("^") or t in INDICES


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


# Pagina Wikipedia per l'attenzione degli investitori: nella lingua del mercato di casa
# (chi compra ENI.MI legge it.wikipedia), in inglese per USA e ADR.
WIKI = {
    "AAPL": ("en", "Apple_Inc."), "MSFT": ("en", "Microsoft"), "NVDA": ("en", "Nvidia"),
    "AMZN": ("en", "Amazon_(company)"), "GOOGL": ("en", "Alphabet_Inc."), "META": ("en", "Meta_Platforms"),
    "AVGO": ("en", "Broadcom"), "TSLA": ("en", "Tesla,_Inc."), "JPM": ("en", "JPMorgan_Chase"),
    "V": ("en", "Visa_Inc."), "LLY": ("en", "Eli_Lilly_and_Company"), "UNH": ("en", "UnitedHealth_Group"),
    "XOM": ("en", "ExxonMobil"), "JNJ": ("en", "Johnson_&_Johnson"), "PG": ("en", "Procter_&_Gamble"),
    "LMT": ("en", "Lockheed_Martin"), "RTX": ("en", "RTX_Corporation"), "NOC": ("en", "Northrop_Grumman"),
    "AMD": ("en", "AMD"), "ASML": ("en", "ASML_Holding"), "COST": ("en", "Costco"),
    "KO": ("en", "The_Coca-Cola_Company"),
    "ENI.MI": ("it", "Eni"), "ENEL.MI": ("it", "Enel"), "ISP.MI": ("it", "Intesa_Sanpaolo"),
    "UCG.MI": ("it", "UniCredit"), "RACE.MI": ("it", "Ferrari_(azienda)"), "STLAM.MI": ("it", "Stellantis"),
    "G.MI": ("it", "Assicurazioni_Generali"), "LDO.MI": ("it", "Leonardo_(azienda)"), "PRY.MI": ("it", "Prysmian"),
    "MONC.MI": ("it", "Moncler"), "STMMI.MI": ("it", "STMicroelectronics"), "TIT.MI": ("it", "TIM_(azienda)"),
    "MB.MI": ("it", "Mediobanca"), "BMED.MI": ("it", "Banca_Mediolanum"), "FBK.MI": ("it", "FinecoBank"),
    "SRG.MI": ("it", "Snam"), "TRN.MI": ("it", "Terna_(azienda)"), "PST.MI": ("it", "Poste_italiane"),
    "ASML.AS": ("nl", "ASML"), "MC.PA": ("fr", "LVMH"), "SAP.DE": ("de", "SAP"), "SIE.DE": ("de", "Siemens"),
    "TTE.PA": ("fr", "TotalEnergies"), "AIR.PA": ("fr", "Airbus"), "RMS.PA": ("fr", "Hermès_International"),
    "OR.PA": ("fr", "L'Oréal"), "NOVO-B.CO": ("da", "Novo_Nordisk"), "NESN.SW": ("de", "Nestlé"),
    "ROG.SW": ("de", "Roche_Holding"), "RHM.DE": ("de", "Rheinmetall"), "SAF.PA": ("fr", "Safran"),
    "ALV.DE": ("de", "Allianz"), "BNP.PA": ("fr", "BNP_Paribas"), "SAN.MC": ("es", "Banco_Santander"),
    "SHEL.L": ("en", "Shell_plc"), "AZN.L": ("en", "AstraZeneca"), "BA.L": ("en", "BAE_Systems"),
    "BABA": ("en", "Alibaba_Group"), "0700.HK": ("zh", "腾讯"), "PDD": ("en", "PDD_Holdings"),
    "JD": ("en", "JD.com"), "TSM": ("en", "TSMC"), "7203.T": ("ja", "トヨタ自動車"), "6758.T": ("ja", "ソニー"),
    "9984.T": ("ja", "ソフトバンクグループ"), "005930.KS": ("ko", "삼성전자"), "INFY": ("en", "Infosys"),
    "HDB": ("en", "HDFC_Bank"), "MELI": ("es", "Mercado_Libre"), "VALE": ("en", "Vale_(company)"),
    "BIDU": ("en", "Baidu"),
}
