"""SEC Insider Transactions Data Sets (Form 3/4/5 strutturati, gratuiti, senza chiave), dal 2006.

Si tengono solo gli acquisti sul mercato aperto (Form 4, codice P, acquisizione A, prezzo >= 2 $) di
Director/Officer. Per ogni trimestre si salva un CSV compatto in data/sec_insider/ e si cancella lo zip.
"""
import io
import os
import zipfile

import pandas as pd

import config

from .common import get

URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
DIR = os.path.join(config.DATA_DIR, "sec_insider")
COLS = ["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK", "ISSUERTRADINGSYMBOL", "RPTOWNERCIK",
        "RPTOWNER_RELATIONSHIP", "TRANS_DATE", "TRANS_SHARES", "TRANS_PRICEPERSHARE"]


def quarters(first=(2006, 1), last=(2026, 1)):
    y, q = first
    while (y, q) <= last:
        yield f"{y}q{q}"
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)


def _tsv(z, name, usecols):
    with z.open(name) as f:
        return pd.read_csv(f, sep="\t", dtype=str, usecols=usecols, quoting=3,
                           on_bad_lines="skip", encoding_errors="replace")


def parse_zip(blob: bytes) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(blob))
    sub = _tsv(z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK",
                                     "ISSUERTRADINGSYMBOL"])
    sub = sub[sub["DOCUMENT_TYPE"] == "4"]
    own = _tsv(z, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
    rel = own["RPTOWNER_RELATIONSHIP"].fillna("")
    own = own[rel.str.contains("Director|Officer", case=False)]
    tr = _tsv(z, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                                        "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    tr = tr[(tr["TRANS_CODE"] == "P") & (tr["TRANS_ACQUIRED_DISP_CD"] == "A")]
    tr["TRANS_PRICEPERSHARE"] = pd.to_numeric(tr["TRANS_PRICEPERSHARE"], errors="coerce")
    tr = tr[tr["TRANS_PRICEPERSHARE"] >= 2]
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
    for c in ("FILING_DATE", "TRANS_DATE"):
        df[c] = pd.to_datetime(df[c], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    df["ISSUERTRADINGSYMBOL"] = df["ISSUERTRADINGSYMBOL"].fillna("").str.upper().str.strip()
    return df[COLS].dropna(subset=["FILING_DATE"])


def load(refresh=False) -> pd.DataFrame:
    os.makedirs(DIR, exist_ok=True)
    frames = []
    for q in quarters():
        path = os.path.join(DIR, f"{q}_P.csv")
        if refresh or not os.path.exists(path):
            df = parse_zip(get(URL.format(q=q), host_gap=0.2, timeout=180).content)
            df.to_csv(path, index=False)
        frames.append(pd.read_csv(path, dtype=str))
    out = pd.concat(frames, ignore_index=True)
    out["TRANS_PRICEPERSHARE"] = pd.to_numeric(out["TRANS_PRICEPERSHARE"], errors="coerce")
    out["TRANS_SHARES"] = pd.to_numeric(out["TRANS_SHARES"], errors="coerce")
    return out
