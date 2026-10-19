"""Phase-0 allowlist v0 — public EN editorial/official hosts only.

Online-only OSINT. No social dumps, anonymous channels, or conflict-zone
field-collection sources. Categories align with mvp-backlog-v1 §6.
Apex hosts only; www./apex matching is handled at evaluation time.
"""

from typing import List, Tuple

# (host, category)
ALLOWLIST_V0: List[Tuple[str, str]] = [
    # US national / wire (EN)
    ("reuters.com", "us_wire_national"),
    ("apnews.com", "us_wire_national"),
    ("nytimes.com", "us_wire_national"),
    ("washingtonpost.com", "us_wire_national"),
    ("wsj.com", "us_wire_national"),
    ("bloomberg.com", "us_wire_national"),
    ("usatoday.com", "us_wire_national"),
    # US defense / security outlets (EN)
    ("defenseone.com", "us_defense_outlet"),
    ("defensenews.com", "us_defense_outlet"),
    ("militarytimes.com", "us_defense_outlet"),
    ("breakingdefense.com", "us_defense_outlet"),
    ("airandspaceforces.com", "us_defense_outlet"),
    # US government / military public hosts
    ("defense.gov", "us_gov_military"),
    ("navy.mil", "us_gov_military"),
    ("army.mil", "us_gov_military"),
    ("af.mil", "us_gov_military"),
    ("marines.mil", "us_gov_military"),
    ("state.gov", "us_gov_military"),
    ("whitehouse.gov", "us_gov_military"),
    # Selected Asia EN outlets
    ("straitstimes.com", "asia_en_outlet"),
    ("scmp.com", "asia_en_outlet"),
    ("japantimes.co.jp", "asia_en_outlet"),
    ("koreaherald.com", "asia_en_outlet"),
    ("channelnewsasia.com", "asia_en_outlet"),
    ("thejakartapost.com", "asia_en_outlet"),
    ("bangkokpost.com", "asia_en_outlet"),
    # Broader EN wire useful for OSINT density
    ("bbc.com", "en_international"),
    ("theguardian.com", "en_international"),
    # Public satellite / Earth observation (license-clear archives)
    ("earthobservatory.nasa.gov", "public_eo_archive"),
    ("usgs.gov", "public_eo_archive"),
]

CATEGORIES = {
    "us_wire_national": "US national / wire EN reporting",
    "us_defense_outlet": "US defense & security outlets",
    "us_gov_military": "US government / military public sites",
    "asia_en_outlet": "Selected Asia English outlets",
    "en_international": "Broader EN international reporting",
    "public_eo_archive": "Public EO / satellite archives",
    "admin_added": "Added by Admin",
}
