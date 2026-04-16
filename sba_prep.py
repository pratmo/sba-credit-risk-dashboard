# =============================================================================
#  SBA 7(a) Credit Risk Dashboard - Data Preparation Script
#  Input : FOIA - 7(a) (FY2020-Present) asof 251231.csv   (from data.sba.gov)
#  Output: sba_dashboard_ready.csv   (connect directly to Tableau)
#
#  What this script does:
#    1. Loads only the 25 columns needed - keeps memory low on any laptop
#    2. Cleans numeric fields stored as text in the raw file
#    3. Creates DEFAULT_FLAG so Tableau can calculate Default Rate
#    4. Engineers 15 readable category columns for Tableau segmentation
#    5. Prints a full summary so you can verify everything looks correct
#    6. Exports one clean CSV - one row per loan, ready for Tableau
# =============================================================================

import pandas as pd
import os

# -----------------------------------------------------------------------------
# STEP 1: CONFIGURATION
# Change INPUT_FILE to match the exact filename you downloaded
# -----------------------------------------------------------------------------

INPUT_FILE  = r"C:\Users\prathikm\Documents\Project_Credit_Risk\foia-7a-fy2020-present-as-of-251231.csv"
OUTPUT_FILE = "sba_dashboard_ready.csv"

# These are the only 25 columns we need - loading all 43 wastes memory
COLS_TO_LOAD = [
    "approvalfiscalyear",       # Vintage year — origination year of the loan
    "approvaldate",             # Exact approval date
    "borrstate",                # Borrower's registered state
    "borrzip",                  # Borrower ZIP (for potential geo drill-down)
    "bankname",                 # Lending institution name
    "bankstate",                # Bank's home state
    "grossapproval",            # Original loan amount ($) — EAD proxy
    "sbaguaranteedapproval",    # Government-guaranteed portion ($)
    "grosschargeoffamount",     # Actual net loss after all recovery ($)
    "initialinterestrate",      # Interest rate at origination (%)
    "fixedorvariableinterestind",  # F = Fixed, V = Variable
    "terminmonths",             # Loan term in months (e.g. 120 = 10 years)
    "naicscode",                # 6-digit industry classification code
    "naicsdescription",         # Readable industry description
    "businesstype",             # Corporation, LLC, Sole Proprietorship, etc.
    "businessage",              # Startup (<2 yrs) or Existing (2+ yrs)
    "loanstatus",               # PIF / CHGOFF / CANCLD / EXEMPT / DISBURSED
    "chargeoffdate",            # Date of charge-off (blank if not defaulted)
    "paidinfulldate",           # Date paid in full (blank if not yet closed)
    "processingmethod",         # SBA lender channel (Preferred / Express / etc.)
    "subprogram",               # SBA sub-programme type
    "projectstate",             # State where loan funds are deployed
    "revolverstatus",           # 1 = revolving line of credit, 0 = term loan
    "collateralind",            # Y = collateralised, N = no collateral
    "jobssupported",            # Reported jobs supported/created by loan
]

# =============================================================================
# STEP 2: LOAD DATA
# =============================================================================

print("=" * 65)
print("  SBA 7(a) Credit Risk — Data Preparation Script")
print("=" * 65)

if not os.path.exists(INPUT_FILE):
    print(f"\n  ERROR: File not found — '{INPUT_FILE}'")
    print("  Make sure the CSV is in the same folder as this script.")
    print("  Rename the file if needed to match INPUT_FILE above.\n")
    raise SystemExit(1)

print(f"\n[1/6] Loading '{INPUT_FILE}' ...")
print("      (Using usecols — only 25 of 43 columns loaded for memory efficiency)")

df = pd.read_csv(
    INPUT_FILE,
    usecols=COLS_TO_LOAD,
    low_memory=False,
    dtype=str              # Load everything as text first - we convert below
)

print(f"      Loaded: {len(df):,} rows  x  {len(df.columns)} columns")
print(f"\n      Raw loanstatus distribution:")
for status, count in df["loanstatus"].value_counts().items():
    pct = count / len(df) * 100
    print(f"        {str(status):20s}  {count:>8,}  ({pct:.1f}%)")

# =============================================================================
# STEP 3: NUMERIC CONVERSIONS
# =============================================================================

print("\n[2/6] Converting numeric columns ...")

# Financial amounts - stored as plain integers or decimals in the raw file
# errors="coerce" means any blank or malformed value becomes NaN (not a crash)
df["grossapproval"]         = pd.to_numeric(df["grossapproval"],         errors="coerce")
df["sbaguaranteedapproval"] = pd.to_numeric(df["sbaguaranteedapproval"], errors="coerce")
df["grosschargeoffamount"]  = pd.to_numeric(df["grosschargeoffamount"],  errors="coerce").fillna(0)
df["initialinterestrate"]   = pd.to_numeric(df["initialinterestrate"],   errors="coerce")
df["terminmonths"]          = pd.to_numeric(df["terminmonths"],          errors="coerce")
df["jobssupported"]         = pd.to_numeric(df["jobssupported"],         errors="coerce")
df["approvalfiscalyear"]    = pd.to_numeric(df["approvalfiscalyear"],    errors="coerce")

print(f"      grossapproval     : min=${df['grossapproval'].min():,.0f}  "
      f"max=${df['grossapproval'].max():,.0f}  "
      f"mean=${df['grossapproval'].mean():,.0f}")
print(f"      initialinterestrate: min={df['initialinterestrate'].min():.2f}%  "
      f"max={df['initialinterestrate'].max():.2f}%  "
      f"mean={df['initialinterestrate'].mean():.2f}%")
print(f"      terminmonths       : min={df['terminmonths'].min():.0f}  "
      f"max={df['terminmonths'].max():.0f}")

# =============================================================================
# STEP 4: DEFAULT FLAG  (the most important engineered column)
# =============================================================================

print("\n[3/6] Creating DEFAULT_FLAG ...")

# CHGOFF     = Charged Off — lender has written this loan off as a loss
# ADMIN CHGOFF = Administratively Charged Off - same outcome, different process
# Both = defaulted. All others (PIF, CANCLD, EXEMPT, DISBURSED) = not defaulted.

DEFAULT_STATUSES = {"CHGOFF", "ADMIN CHGOFF"}

df["DEFAULT_FLAG"] = df["loanstatus"].apply(
    lambda x: 1 if str(x).strip().upper() in DEFAULT_STATUSES else 0
)

total_loans    = len(df)
total_defaults = df["DEFAULT_FLAG"].sum()
default_rate   = total_defaults / total_loans * 100

print(f"      Total loans   : {total_loans:,}")
print(f"      Defaulted     : {total_defaults:,}")
print(f"      Default rate  : {default_rate:.2f}%")

# =============================================================================
# STEP 5: ENGINEERED CATEGORY COLUMNS
# =============================================================================

print("\n[4/6] Engineering category columns ...")

# ── 5a. Loan Status Label ─────────────────────────────────────────────────────
STATUS_MAP = {
    "PIF":          "Paid in Full",
    "CHGOFF":       "Charged Off (Default)",
    "ADMIN CHGOFF": "Charged Off (Default)",
    "CANCLD":       "Cancelled",
    "EXEMPT":       "Exempt",
    "DISBURSED":    "Active / Disbursed",
    "COMMIT":       "Committed",
}
df["STATUS_LABEL"] = df["loanstatus"].apply(
    lambda x: STATUS_MAP.get(str(x).strip().upper(), str(x).strip().title())
)

# ── 5b. Vintage Year ──────────────────────────────────────────────────────────
# Clean 4-digit fiscal year as text (Tableau treats it as a category, not a number)
df["VINTAGE_YEAR"] = df["approvalfiscalyear"].apply(
    lambda x: str(int(x)) if pd.notna(x) else "Unknown"
)

# ── 5c. Loan Size Band ────────────────────────────────────────────────────────
# Groups grossapproval into 5 risk-relevant brackets
# Micro loans (<$50K) are often Express/community loans; Very Large (>$1M) are major commercial
def loan_size_band(x):
    if pd.isna(x):  return "Unknown"
    if x < 50000:   return "1 - Micro (<$50K)"
    if x < 150000:  return "2 - Small ($50K-$150K)"
    if x < 500000:  return "3 - Mid ($150K-$500K)"
    if x < 1000000: return "4 - Large ($500K-$1M)"
    return              "5 - Very Large (>$1M)"

df["LOAN_SIZE_BAND"] = df["grossapproval"].apply(loan_size_band)

# ── 5d. Term Band ─────────────────────────────────────────────────────────────
# Groups terminmonths into duration buckets
# Longer terms = more time for economic shocks to cause default
def term_band(x):
    if pd.isna(x): return "Unknown"
    if x <= 60:    return "1 - Short (<=5 Yrs)"
    if x <= 120:   return "2 - Medium (6-10 Yrs)"
    if x <= 180:   return "3 - Long (11-15 Yrs)"
    if x <= 240:   return "4 - Very Long (16-20 Yrs)"
    return             "5 - Ultra Long (>20 Yrs)"

df["TERM_BAND"] = df["terminmonths"].apply(term_band)

# ── 5e. Interest Rate Band ────────────────────────────────────────────────────
# Tests whether higher-rate loans (often riskier borrowers) have higher default rates
# Also shows the impact of the 2022-2023 Fed rate hike cycle on origination rates
def rate_band(x):
    if pd.isna(x): return "Unknown"
    if x < 5:      return "1 - Low (<5%)"
    if x < 7:      return "2 - Moderate (5-7%)"
    if x < 9:      return "3 - High (7-9%)"
    return             "4 - Very High (>=9%)"

df["RATE_BAND"] = df["initialinterestrate"].apply(rate_band)

# ── 5f. Interest Type Label ───────────────────────────────────────────────────
# Variable rate borrowers suffered directly as the Fed raised rates 500 bps in 2022-2023
INTEREST_TYPE_MAP = {
    "F": "Fixed Rate",
    "V": "Variable Rate",
}
df["INTEREST_TYPE"] = df["fixedorvariableinterestind"].apply(
    lambda x: INTEREST_TYPE_MAP.get(str(x).strip().upper(), "Unknown")
)

# ── 5g. Business Age Label ────────────────────────────────────────────────────
# One of the strongest default predictors in SME lending
# Startups default significantly more than established businesses
def business_age_label(x):
    x = str(x).strip().lower()
    if "startup" in x or "new" in x or "open" in x:
        return "Startup / New (<2 Years)"
    if "existing" in x or "2 years" in x or "more than" in x:
        return "Established (2+ Years)"
    return "Unknown"

df["BUSINESS_AGE_LABEL"] = df["businessage"].apply(business_age_label)

# ── 5h. Business Type Label ───────────────────────────────────────────────────
# Corporation / LLC tend to have lower default rates than sole proprietorships
# because of better separation of personal and business finances
df["BUSINESS_TYPE_LABEL"] = df["businesstype"].apply(
    lambda x: str(x).strip().title() if pd.notna(x) and str(x).strip() != "" else "Unknown"
)

# ── 5i. Collateral Label ──────────────────────────────────────────────────────
# Uncollateralised loans are riskier — nothing to recover in default
COLLATERAL_MAP = {"Y": "Collateralised", "N": "Uncollateralised"}
df["COLLATERAL_LABEL"] = df["collateralind"].apply(
    lambda x: COLLATERAL_MAP.get(str(x).strip().upper(), "Unknown")
)

# ── 5j. NAICS Sector ─────────────────────────────────────────────────────────
# Maps 6-digit NAICS code to one of 16 major industry sectors
# Uses first 2 digits — the top-level sector code in the NAICS hierarchy
# Without this, Tableau shows hundreds of unique industries — too many to analyse
def naics_sector(code):
    try:
        c = int(str(code).strip()[:2])
    except (ValueError, TypeError):
        return "Unknown"
    if 11 <= c <= 21:  return "Agri. & Mining"
    if c == 22:        return "Utilities"
    if c == 23:        return "Construction"
    if 31 <= c <= 33:  return "Manufacturing"
    if c == 42:        return "Wholesale Trade"
    if 44 <= c <= 45:  return "Retail Trade"
    if 48 <= c <= 49:  return "Transport & Warehousing"
    if c == 51:        return "Info. & Media"
    if c == 52:        return "Fin. & Insurance"
    if c == 53:        return "Real Estate"
    if 54 <= c <= 55:  return "Professional Services"
    if 56 <= c <= 56:  return "Admin & Support"
    if 61 <= c <= 62:  return "Education & Health"
    if 71 <= c <= 72:  return "Food & Hospitality"
    if c == 81:        return "Other Services"
    if c == 92:        return "Public Admin."
    return "Other"

df["NAICS_SECTOR"] = df["naicscode"].apply(naics_sector)

# ── 5k. Lender Type (from processingmethod) ───────────────────────────────────
# Preferred Lenders have more autonomy — less SBA oversight of underwriting
# Express loans are faster but historically show higher default rates
LENDER_MAP = {
    "preferred lenders program":         "Preferred Lender",
    "sba express program":               "SBA Express",
    "standard":                          "Standard",
    "certified lenders program":         "Certified Lender",
    "community advantage":               "Community Advantage",
    "rural lenders advantage":           "Rural Advantage",
    "veterans advantage":                "Veterans Advantage",
    "export working capital":            "Export Working Capital",
    "international trade":               "International Trade",
}
df["LENDER_TYPE"] = df["processingmethod"].apply(
    lambda x: LENDER_MAP.get(str(x).strip().lower(), str(x).strip()) if pd.notna(x) else "Unknown"
)

# ── 5l. Sub-Programme Label ───────────────────────────────────────────────────
df["SUBPROGRAM_LABEL"] = df["subprogram"].apply(
    lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else "Unknown"
)

# ── 5m. Revolving Loan Label ──────────────────────────────────────────────────
REVOLVING_MAP = {"1": "Revolving Credit Line", "0": "Term Loan"}
df["REVOLVING_LABEL"] = df["revolverstatus"].apply(
    lambda x: REVOLVING_MAP.get(str(x).strip(), "Unknown")
)

# ── 5n. Geography — project state with fallback ───────────────────────────────
# projectstate = where the money is actually used (preferred)
# borrstate    = where the borrower is legally registered (fallback)
df["STATE"] = df["projectstate"].apply(
    lambda x: str(x).strip().upper() if pd.notna(x) and str(x).strip() not in ["", "nan"] else None
)
df["STATE"] = df["STATE"].fillna(
    df["borrstate"].apply(
        lambda x: str(x).strip().upper() if pd.notna(x) else "Unknown"
    )
)

# ── 5o. Derived Financial Metrics ─────────────────────────────────────────────

# GUARANTEE_RATE: what % of each loan is covered by the government
# Higher = less bank risk but more government exposure to that segment
df["GUARANTEE_RATE_PCT"] = (
    df["sbaguaranteedapproval"] / df["grossapproval"] * 100
).round(1)

# CHARGEOFF_RATE: actual loss as % of original loan — your LGD proxy
# For non-defaulted loans this will be 0
# For defaulted loans this shows how severe the loss was
df["CHARGEOFF_RATE_PCT"] = (
    df["grosschargeoffamount"] / df["grossapproval"] * 100
).fillna(0).round(2)

# BANK_RISK_AMOUNT: the unguaranteed portion — what the bank truly risks losing
# = grossapproval minus sbaguaranteedapproval
df["BANK_RISK_AMOUNT"] = (
    df["grossapproval"] - df["sbaguaranteedapproval"]
).round(2)

# =============================================================================
# STEP 6: CLEAN UP AND FINAL EXPORT
# =============================================================================

print("\n[5/6] Cleaning up and preparing final dataset ...")

# Drop raw columns that are now fully replaced by cleaner engineered versions
# Keep naicsdescription for tooltips; keep bankname and borrstate for drill-down
COLS_TO_DROP = [
    "businessage",                  # replaced by BUSINESS_AGE_LABEL
    "businesstype",                 # replaced by BUSINESS_TYPE_LABEL
    "fixedorvariableinterestind",   # replaced by INTEREST_TYPE
    "collateralind",                # replaced by COLLATERAL_LABEL
    "revolverstatus",               # replaced by REVOLVING_LABEL
    "processingmethod",             # replaced by LENDER_TYPE
    "congressionaldistrict",        # too granular for dashboard
    "franchisecode",                # low fill rate, not needed
    "franchisename",                # low fill rate, not needed
    "sbadistrictoffice",            # replaced by STATE
    "borrzip",                      # too granular for dashboard
    "borrstreet",                   # PII — not needed for analysis
    "borrname",                     # PII — not needed for analysis
    "bankstreet",                   # not needed
    "bankncuanumber",               # mostly blank
    "l2locid",                      # internal SBA ID — not needed
    "asofdate",                     # static across all rows (12/31/2025)
    "program",                      # all rows are 7A — no variation
    "projectcounty",                # state is sufficient for geography
]

# Only drop columns that actually exist in the dataframe
cols_to_drop_actual = [c for c in COLS_TO_DROP if c in df.columns]
df = df.drop(columns=cols_to_drop_actual)

# Final column order - logical grouping for easy navigation in Tableau
FINAL_ORDER = [
    # ── Loan identifiers
    "approvalfiscalyear", "approvaldate", "VINTAGE_YEAR",
    # ── Loan financials
    "grossapproval", "sbaguaranteedapproval", "grosschargeoffamount",
    "BANK_RISK_AMOUNT", "GUARANTEE_RATE_PCT", "CHARGEOFF_RATE_PCT",
    # ── Loan structure
    "initialinterestrate", "terminmonths", "INTEREST_TYPE",
    "RATE_BAND", "LOAN_SIZE_BAND", "TERM_BAND",
    "REVOLVING_LABEL", "SUBPROGRAM_LABEL",
    # ── Default / performance
    "loanstatus", "STATUS_LABEL", "DEFAULT_FLAG",
    "chargeoffdate", "paidinfulldate",
    # ── Borrower characteristics
    "BUSINESS_AGE_LABEL", "BUSINESS_TYPE_LABEL", "COLLATERAL_LABEL",
    "jobssupported",
    # ── Industry
    "naicscode", "naicsdescription", "NAICS_SECTOR",
    # ── Geography
    "STATE", "borrstate", "projectstate",
    # ── Lender
    "bankname", "bankstate", "bankfdicnumber", "LENDER_TYPE",
    "soldsecmrktind", "firstdisbursementdate",
]

# Only include columns that exist after all the transformations
final_cols = [c for c in FINAL_ORDER if c in df.columns]
# Add any remaining columns not in our order list
remaining = [c for c in df.columns if c not in final_cols]
df = df[final_cols + remaining]

# =============================================================================
# STEP 7: SUMMARY REPORT
# =============================================================================

print("\n[6/6] Generating summary report ...")
print("\n" + "=" * 65)
print("  PIPELINE COMPLETE — SUMMARY")
print("=" * 65)

print(f"\n  Total loans              : {len(df):>10,}")
print(f"  Total columns            : {len(df.columns):>10,}")
print(f"  Default Rate             : {df['DEFAULT_FLAG'].mean()*100:>9.2f}%")
print(f"  Total Exposure           : ${df['grossapproval'].sum()/1e9:>9.2f}B")
print(f"  Total Charge-Offs        : ${df['grosschargeoffamount'].sum()/1e6:>9.1f}M")
print(f"  Avg Loan Amount          : ${df['grossapproval'].mean():>10,.0f}")
print(f"  Avg Interest Rate        : {df['initialinterestrate'].mean():>9.2f}%")
print(f"  Avg Guarantee Rate       : {df['GUARANTEE_RATE_PCT'].mean():>9.1f}%")

print("\n  --- Loan Status ---")
for s, n in df["STATUS_LABEL"].value_counts().items():
    print(f"    {str(s):30s}: {n:>8,}  ({n/len(df)*100:.1f}%)")

print("\n  --- Vintage Year ---")
for v, n in df["VINTAGE_YEAR"].value_counts().sort_index().items():
    pct = n / len(df) * 100
    dr  = df[df["VINTAGE_YEAR"] == v]["DEFAULT_FLAG"].mean() * 100
    print(f"    FY{v}  {n:>8,} loans  ({pct:.1f}%)  Default Rate: {dr:.2f}%")

print("\n  --- NAICS Sector (Top 10 by count) ---")
sector_stats = (
    df.groupby("NAICS_SECTOR")
    .agg(count=("DEFAULT_FLAG", "count"), default_rate=("DEFAULT_FLAG", "mean"))
    .sort_values("count", ascending=False)
    .head(10)
)
for sec, row in sector_stats.iterrows():
    print(f"    {str(sec):42s}: {int(row['count']):>7,}  DR={row['default_rate']*100:.1f}%")

print("\n  --- Loan Size Band ---")
for b, n in df["LOAN_SIZE_BAND"].value_counts().sort_index().items():
    dr = df[df["LOAN_SIZE_BAND"] == b]["DEFAULT_FLAG"].mean() * 100
    print(f"    {str(b):35s}: {n:>8,}  Default Rate: {dr:.2f}%")

print("\n  --- Business Age ---")
for b, n in df["BUSINESS_AGE_LABEL"].value_counts().items():
    dr = df[df["BUSINESS_AGE_LABEL"] == b]["DEFAULT_FLAG"].mean() * 100
    print(f"    {str(b):35s}: {n:>8,}  Default Rate: {dr:.2f}%")

print("\n  --- Interest Type ---")
for t, n in df["INTEREST_TYPE"].value_counts().items():
    dr = df[df["INTEREST_TYPE"] == t]["DEFAULT_FLAG"].mean() * 100
    print(f"    {str(t):25s}: {n:>8,}  Default Rate: {dr:.2f}%")

print("\n  --- Top 10 States by Loan Count ---")
state_stats = (
    df.groupby("STATE")
    .agg(count=("DEFAULT_FLAG", "count"), default_rate=("DEFAULT_FLAG", "mean"))
    .sort_values("count", ascending=False)
    .head(10)
)
for state, row in state_stats.iterrows():
    print(f"    {str(state):6s}: {int(row['count']):>7,} loans  DR={row['default_rate']*100:.1f}%")

print(f"\n  Final columns in output:")
for i, col in enumerate(df.columns, 1):
    print(f"    {i:>2}. {col}")

# =============================================================================
# EXPORT
# =============================================================================

df.to_csv(OUTPUT_FILE, index=False)

print(f"\n{'=' * 65}")
print(f"  Output saved: {OUTPUT_FILE}")
print(f"  File size   : {os.path.getsize(OUTPUT_FILE) / 1e6:.1f} MB")
print(f"  Rows        : {len(df):,}")
print(f"  Columns     : {len(df.columns)}")
print(f"\n  NEXT STEP: Open Tableau Desktop")
print(f"             Connect > To a File > Text File")
print(f"             Select: {OUTPUT_FILE}")
print(f"{'=' * 65}\n")
