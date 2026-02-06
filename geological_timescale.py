"""
Fossil Journey Tracker - Geological Timescale Database
Based on GT_Data.xlsx - International Chronostratigraphic Chart

This module provides the complete geological timescale with:
- Periods, Epochs, and Ages
- Official ICS colors (RGB and HEX)
- Start and end times in Ma (millions of years ago)
- Acronyms for chart display

Author: ITT Oceaneon / UNISINOS
Version: 1.0
"""

from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class GeologicalUnit:
    """Represents a geological time unit (Eon, Era, Period, Epoch, or Age)."""
    name: str
    name_pt: str  # Portuguese name
    category: str  # 'Eon', 'Era', 'Period', 'Epoch', 'Age'
    start_ma: float  # Start time in Ma
    end_ma: float  # End time in Ma
    color_hex: str  # ICS official color
    color_rgb: tuple  # RGB tuple (R, G, B)
    acronym: str  # Short acronym for charts
    parent: Optional[str] = None  # Parent unit name

# =============================================================================
# EONS
# =============================================================================
EONS = {
    'Phanerozoic': GeologicalUnit(
        name='Phanerozoic', name_pt='Fanerozoico', category='Eon',
        start_ma=538.8, end_ma=0, color_hex='#9AD9DD', color_rgb=(154, 217, 221),
        acronym='Ph'
    ),
    'Proterozoic': GeologicalUnit(
        name='Proterozoic', name_pt='Proterozoico', category='Eon',
        start_ma=2500, end_ma=538.8, color_hex='#F73563', color_rgb=(247, 53, 99),
        acronym='Pt'
    ),
    'Archean': GeologicalUnit(
        name='Archean', name_pt='Arqueano', category='Eon',
        start_ma=4031, end_ma=2500, color_hex='#F0047F', color_rgb=(240, 4, 127),
        acronym='A'
    ),
    'Hadean': GeologicalUnit(
        name='Hadean', name_pt='Hadeano', category='Eon',
        start_ma=4567, end_ma=4031, color_hex='#AE027E', color_rgb=(174, 2, 126),
        acronym='H'
    ),
}

# =============================================================================
# ERAS
# =============================================================================
ERAS = {
    'Cenozoic': GeologicalUnit(
        name='Cenozoic', name_pt='Cenozoico', category='Era',
        start_ma=66.0, end_ma=0, color_hex='#F2F91D', color_rgb=(242, 249, 29),
        acronym='Cz', parent='Phanerozoic'
    ),
    'Mesozoic': GeologicalUnit(
        name='Mesozoic', name_pt='Mesozoico', category='Era',
        start_ma=251.9, end_ma=66.0, color_hex='#67C5CA', color_rgb=(103, 197, 202),
        acronym='Mz', parent='Phanerozoic'
    ),
    'Paleozoic': GeologicalUnit(
        name='Paleozoic', name_pt='Paleozoico', category='Era',
        start_ma=538.8, end_ma=251.9, color_hex='#99C08D', color_rgb=(153, 192, 141),
        acronym='Pz', parent='Phanerozoic'
    ),
    'Neoproterozoic': GeologicalUnit(
        name='Neoproterozoic', name_pt='Neoproterozoico', category='Era',
        start_ma=1000, end_ma=538.8, color_hex='#FEB342', color_rgb=(254, 179, 66),
        acronym='Np', parent='Proterozoic'
    ),
    'Mesoproterozoic': GeologicalUnit(
        name='Mesoproterozoic', name_pt='Mesoproterozoico', category='Era',
        start_ma=1600, end_ma=1000, color_hex='#FDB462', color_rgb=(253, 180, 98),
        acronym='Mp', parent='Proterozoic'
    ),
    'Paleoproterozoic': GeologicalUnit(
        name='Paleoproterozoic', name_pt='Paleoproterozoico', category='Era',
        start_ma=2500, end_ma=1600, color_hex='#F74370', color_rgb=(247, 67, 112),
        acronym='Pp', parent='Proterozoic'
    ),
    'Neoarchean': GeologicalUnit(
        name='Neoarchean', name_pt='Neoarqueano', category='Era',
        start_ma=2800, end_ma=2500, color_hex='#FAA7C8', color_rgb=(250, 167, 200),
        acronym='Na', parent='Archean'
    ),
    'Mesoarchean': GeologicalUnit(
        name='Mesoarchean', name_pt='Mesoarqueano', category='Era',
        start_ma=3200, end_ma=2800, color_hex='#F881B5', color_rgb=(248, 129, 181),
        acronym='Ma', parent='Archean'
    ),
    'Paleoarchean': GeologicalUnit(
        name='Paleoarchean', name_pt='Paleoarqueano', category='Era',
        start_ma=3600, end_ma=3200, color_hex='#F668B2', color_rgb=(246, 104, 178),
        acronym='Pa', parent='Archean'
    ),
    'Eoarchean': GeologicalUnit(
        name='Eoarchean', name_pt='Eoarqueano', category='Era',
        start_ma=4031, end_ma=3600, color_hex='#E61D8C', color_rgb=(230, 29, 140),
        acronym='Ea', parent='Archean'
    ),
}

# =============================================================================
# PERIODS (Phanerozoic)
# =============================================================================
PERIODS = {
    # Cenozoic
    'Quaternary': GeologicalUnit(
        name='Quaternary', name_pt='Quaternario', category='Period',
        start_ma=2.58, end_ma=0, color_hex='#F9F97F', color_rgb=(249, 249, 127),
        acronym='Q', parent='Cenozoic'
    ),
    'Neogene': GeologicalUnit(
        name='Neogene', name_pt='Neogeno', category='Period',
        start_ma=23.03, end_ma=2.58, color_hex='#FFE619', color_rgb=(255, 230, 25),
        acronym='Ng', parent='Cenozoic'
    ),
    'Paleogene': GeologicalUnit(
        name='Paleogene', name_pt='Paleogeno', category='Period',
        start_ma=66.0, end_ma=23.03, color_hex='#FD9A52', color_rgb=(253, 154, 82),
        acronym='Pg', parent='Cenozoic'
    ),
    # Mesozoic
    'Cretaceous': GeologicalUnit(
        name='Cretaceous', name_pt='Cretaceo', category='Period',
        start_ma=145.0, end_ma=66.0, color_hex='#7FC64E', color_rgb=(127, 198, 78),
        acronym='K', parent='Mesozoic'
    ),
    'Jurassic': GeologicalUnit(
        name='Jurassic', name_pt='Jurassico', category='Period',
        start_ma=201.4, end_ma=145.0, color_hex='#34B2C9', color_rgb=(52, 178, 201),
        acronym='J', parent='Mesozoic'
    ),
    'Triassic': GeologicalUnit(
        name='Triassic', name_pt='Triassico', category='Period',
        start_ma=251.9, end_ma=201.4, color_hex='#812B92', color_rgb=(129, 43, 146),
        acronym='Tr', parent='Mesozoic'
    ),
    # Paleozoic
    'Permian': GeologicalUnit(
        name='Permian', name_pt='Permiano', category='Period',
        start_ma=298.9, end_ma=251.9, color_hex='#F04028', color_rgb=(240, 64, 40),
        acronym='P', parent='Paleozoic'
    ),
    'Carboniferous': GeologicalUnit(
        name='Carboniferous', name_pt='Carbonifero', category='Period',
        start_ma=358.9, end_ma=298.9, color_hex='#67A599', color_rgb=(103, 165, 153),
        acronym='C', parent='Paleozoic'
    ),
    'Devonian': GeologicalUnit(
        name='Devonian', name_pt='Devoniano', category='Period',
        start_ma=419.2, end_ma=358.9, color_hex='#CB8C37', color_rgb=(203, 140, 55),
        acronym='D', parent='Paleozoic'
    ),
    'Silurian': GeologicalUnit(
        name='Silurian', name_pt='Siluriano', category='Period',
        start_ma=443.8, end_ma=419.2, color_hex='#B3E1B6', color_rgb=(179, 225, 182),
        acronym='S', parent='Paleozoic'
    ),
    'Ordovician': GeologicalUnit(
        name='Ordovician', name_pt='Ordoviciano', category='Period',
        start_ma=485.4, end_ma=443.8, color_hex='#009270', color_rgb=(0, 146, 112),
        acronym='O', parent='Paleozoic'
    ),
    'Cambrian': GeologicalUnit(
        name='Cambrian', name_pt='Cambriano', category='Period',
        start_ma=538.8, end_ma=485.4, color_hex='#7FA056', color_rgb=(127, 160, 86),
        acronym='Cm', parent='Paleozoic'
    ),
    # Neoproterozoic
    'Ediacaran': GeologicalUnit(
        name='Ediacaran', name_pt='Ediacarano', category='Period',
        start_ma=635.0, end_ma=538.8, color_hex='#FED96A', color_rgb=(254, 217, 106),
        acronym='E', parent='Neoproterozoic'
    ),
    'Cryogenian': GeologicalUnit(
        name='Cryogenian', name_pt='Criogeniano', category='Period',
        start_ma=720.0, end_ma=635.0, color_hex='#FECC5C', color_rgb=(254, 204, 92),
        acronym='Cr', parent='Neoproterozoic'
    ),
    'Tonian': GeologicalUnit(
        name='Tonian', name_pt='Toniano', category='Period',
        start_ma=1000.0, end_ma=720.0, color_hex='#FEBF4E', color_rgb=(254, 191, 78),
        acronym='To', parent='Neoproterozoic'
    ),
}

# =============================================================================
# EPOCHS (Main ones for Phanerozoic)
# =============================================================================
EPOCHS = {
    # Quaternary
    'Holocene': GeologicalUnit(
        name='Holocene', name_pt='Holoceno', category='Epoch',
        start_ma=0.0117, end_ma=0, color_hex='#FEECDB', color_rgb=(254, 236, 219),
        acronym='Hol', parent='Quaternary'
    ),
    'Pleistocene': GeologicalUnit(
        name='Pleistocene', name_pt='Pleistoceno', category='Epoch',
        start_ma=2.58, end_ma=0.0117, color_hex='#FFEFAF', color_rgb=(255, 239, 175),
        acronym='Ple', parent='Quaternary'
    ),
    # Neogene
    'Pliocene': GeologicalUnit(
        name='Pliocene', name_pt='Plioceno', category='Epoch',
        start_ma=5.333, end_ma=2.58, color_hex='#FFFF99', color_rgb=(255, 255, 153),
        acronym='Pli', parent='Neogene'
    ),
    'Miocene': GeologicalUnit(
        name='Miocene', name_pt='Mioceno', category='Epoch',
        start_ma=23.03, end_ma=5.333, color_hex='#FFFF00', color_rgb=(255, 255, 0),
        acronym='Mio', parent='Neogene'
    ),
    # Paleogene
    'Oligocene': GeologicalUnit(
        name='Oligocene', name_pt='Oligoceno', category='Epoch',
        start_ma=33.9, end_ma=23.03, color_hex='#FEC07A', color_rgb=(254, 192, 122),
        acronym='Oli', parent='Paleogene'
    ),
    'Eocene': GeologicalUnit(
        name='Eocene', name_pt='Eoceno', category='Epoch',
        start_ma=56.0, end_ma=33.9, color_hex='#FDB46C', color_rgb=(253, 180, 108),
        acronym='Eoc', parent='Paleogene'
    ),
    'Paleocene': GeologicalUnit(
        name='Paleocene', name_pt='Paleoceno', category='Epoch',
        start_ma=66.0, end_ma=56.0, color_hex='#FDA75F', color_rgb=(253, 167, 95),
        acronym='Pal', parent='Paleogene'
    ),
    # Cretaceous
    'Upper Cretaceous': GeologicalUnit(
        name='Upper Cretaceous', name_pt='Cretaceo Superior', category='Epoch',
        start_ma=100.5, end_ma=66.0, color_hex='#A6D84A', color_rgb=(166, 216, 74),
        acronym='K2', parent='Cretaceous'
    ),
    'Lower Cretaceous': GeologicalUnit(
        name='Lower Cretaceous', name_pt='Cretaceo Inferior', category='Epoch',
        start_ma=145.0, end_ma=100.5, color_hex='#8CCD57', color_rgb=(140, 205, 87),
        acronym='K1', parent='Cretaceous'
    ),
    # Jurassic
    'Upper Jurassic': GeologicalUnit(
        name='Upper Jurassic', name_pt='Jurassico Superior', category='Epoch',
        start_ma=161.5, end_ma=145.0, color_hex='#B3E3EE', color_rgb=(179, 227, 238),
        acronym='J3', parent='Jurassic'
    ),
    'Middle Jurassic': GeologicalUnit(
        name='Middle Jurassic', name_pt='Jurassico Medio', category='Epoch',
        start_ma=174.7, end_ma=161.5, color_hex='#80CFD8', color_rgb=(128, 207, 216),
        acronym='J2', parent='Jurassic'
    ),
    'Lower Jurassic': GeologicalUnit(
        name='Lower Jurassic', name_pt='Jurassico Inferior', category='Epoch',
        start_ma=201.4, end_ma=174.7, color_hex='#42AED0', color_rgb=(66, 174, 208),
        acronym='J1', parent='Jurassic'
    ),
    # Triassic
    'Upper Triassic': GeologicalUnit(
        name='Upper Triassic', name_pt='Triassico Superior', category='Epoch',
        start_ma=237.0, end_ma=201.4, color_hex='#BD8CC3', color_rgb=(189, 140, 195),
        acronym='T3', parent='Triassic'
    ),
    'Middle Triassic': GeologicalUnit(
        name='Middle Triassic', name_pt='Triassico Medio', category='Epoch',
        start_ma=247.2, end_ma=237.0, color_hex='#B168B1', color_rgb=(177, 104, 177),
        acronym='T2', parent='Triassic'
    ),
    'Lower Triassic': GeologicalUnit(
        name='Lower Triassic', name_pt='Triassico Inferior', category='Epoch',
        start_ma=251.9, end_ma=247.2, color_hex='#983999', color_rgb=(152, 57, 153),
        acronym='T1', parent='Triassic'
    ),
}

# =============================================================================
# AGES (Selected important ones)
# =============================================================================
AGES = {
    # Cretaceous Ages
    'Maastrichtian': GeologicalUnit(
        name='Maastrichtian', name_pt='Maastrichtiano', category='Age',
        start_ma=72.1, end_ma=66.0, color_hex='#F2FA8C', color_rgb=(242, 250, 140),
        acronym='Maa', parent='Upper Cretaceous'
    ),
    'Campanian': GeologicalUnit(
        name='Campanian', name_pt='Campaniano', category='Age',
        start_ma=83.6, end_ma=72.1, color_hex='#E6F47F', color_rgb=(230, 244, 127),
        acronym='Cam', parent='Upper Cretaceous'
    ),
    'Santonian': GeologicalUnit(
        name='Santonian', name_pt='Santoniano', category='Age',
        start_ma=86.3, end_ma=83.6, color_hex='#D9EF74', color_rgb=(217, 239, 116),
        acronym='San', parent='Upper Cretaceous'
    ),
    'Coniacian': GeologicalUnit(
        name='Coniacian', name_pt='Coniaciano', category='Age',
        start_ma=89.8, end_ma=86.3, color_hex='#CCE968', color_rgb=(204, 233, 104),
        acronym='Con', parent='Upper Cretaceous'
    ),
    'Turonian': GeologicalUnit(
        name='Turonian', name_pt='Turoniano', category='Age',
        start_ma=93.9, end_ma=89.8, color_hex='#BFE35D', color_rgb=(191, 227, 93),
        acronym='Tur', parent='Upper Cretaceous'
    ),
    'Cenomanian': GeologicalUnit(
        name='Cenomanian', name_pt='Cenomaniano', category='Age',
        start_ma=100.5, end_ma=93.9, color_hex='#B3DE53', color_rgb=(179, 222, 83),
        acronym='Cen', parent='Upper Cretaceous'
    ),
    'Albian': GeologicalUnit(
        name='Albian', name_pt='Albiano', category='Age',
        start_ma=113.0, end_ma=100.5, color_hex='#CCEA97', color_rgb=(204, 234, 151),
        acronym='Alb', parent='Lower Cretaceous'
    ),
    'Aptian': GeologicalUnit(
        name='Aptian', name_pt='Aptiano', category='Age',
        start_ma=121.4, end_ma=113.0, color_hex='#BFE48A', color_rgb=(191, 228, 138),
        acronym='Apt', parent='Lower Cretaceous'
    ),
    'Barremian': GeologicalUnit(
        name='Barremian', name_pt='Barremiano', category='Age',
        start_ma=125.77, end_ma=121.4, color_hex='#B3DF7F', color_rgb=(179, 223, 127),
        acronym='Bar', parent='Lower Cretaceous'
    ),
    'Hauterivian': GeologicalUnit(
        name='Hauterivian', name_pt='Hauteriviano', category='Age',
        start_ma=132.6, end_ma=125.77, color_hex='#A6D975', color_rgb=(166, 217, 117),
        acronym='Hau', parent='Lower Cretaceous'
    ),
    'Valanginian': GeologicalUnit(
        name='Valanginian', name_pt='Valanginiano', category='Age',
        start_ma=139.8, end_ma=132.6, color_hex='#99D36A', color_rgb=(153, 211, 106),
        acronym='Val', parent='Lower Cretaceous'
    ),
    'Berriasian': GeologicalUnit(
        name='Berriasian', name_pt='Berriasiano', category='Age',
        start_ma=145.0, end_ma=139.8, color_hex='#8CCD60', color_rgb=(140, 205, 96),
        acronym='Ber', parent='Lower Cretaceous'
    ),
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_period_for_age(age_ma: float) -> Optional[GeologicalUnit]:
    """Get the geological period for a given age in Ma."""
    for period in PERIODS.values():
        if period.end_ma <= age_ma <= period.start_ma:
            return period
    return None

def get_epoch_for_age(age_ma: float) -> Optional[GeologicalUnit]:
    """Get the geological epoch for a given age in Ma."""
    for epoch in EPOCHS.values():
        if epoch.end_ma <= age_ma <= epoch.start_ma:
            return epoch
    return None

def get_era_for_age(age_ma: float) -> Optional[GeologicalUnit]:
    """Get the geological era for a given age in Ma."""
    for era in ERAS.values():
        if era.end_ma <= age_ma <= era.start_ma:
            return era
    return None

def get_color_for_age(age_ma: float) -> str:
    """Get the ICS color (HEX) for a given geological age."""
    period = get_period_for_age(age_ma)
    if period:
        return period.color_hex
    era = get_era_for_age(age_ma)
    if era:
        return era.color_hex
    return '#808080'  # Gray for unknown

def get_period_name(age_ma: float, language: str = 'en') -> str:
    """Get the period name for a given age."""
    period = get_period_for_age(age_ma)
    if period:
        return period.name if language == 'en' else period.name_pt
    return 'Unknown'

def get_all_periods_for_timeline() -> List[Dict]:
    """Get all periods sorted for timeline display."""
    result = []
    for period in PERIODS.values():
        if period.parent in ['Cenozoic', 'Mesozoic', 'Paleozoic']:
            result.append({
                'name': period.name,
                'acronym': period.acronym,
                'start_ma': period.start_ma,
                'end_ma': period.end_ma,
                'color': period.color_hex,
                'era': period.parent
            })
    return sorted(result, key=lambda x: x['end_ma'])

# =============================================================================
# JAVASCRIPT EXPORT
# =============================================================================

def generate_js_timescale() -> str:
    """Generate JavaScript code with the timescale data."""
    js_lines = ["const GEOLOGICAL_TIMESCALE = {"]
    js_lines.append("    periods: {")

    for name, period in PERIODS.items():
        if period.parent in ['Cenozoic', 'Mesozoic', 'Paleozoic']:
            js_lines.append(f"        '{name}': {{")
            js_lines.append(f"            name: '{period.name}',")
            js_lines.append(f"            name_pt: '{period.name_pt}',")
            js_lines.append(f"            acronym: '{period.acronym}',")
            js_lines.append(f"            start_ma: {period.start_ma},")
            js_lines.append(f"            end_ma: {period.end_ma},")
            js_lines.append(f"            color: '{period.color_hex}',")
            js_lines.append(f"            era: '{period.parent}'")
            js_lines.append("        },")

    js_lines.append("    },")
    js_lines.append("    epochs: {")

    for name, epoch in EPOCHS.items():
        js_lines.append(f"        '{name}': {{")
        js_lines.append(f"            name: '{epoch.name}',")
        js_lines.append(f"            name_pt: '{epoch.name_pt}',")
        js_lines.append(f"            acronym: '{epoch.acronym}',")
        js_lines.append(f"            start_ma: {epoch.start_ma},")
        js_lines.append(f"            end_ma: {epoch.end_ma},")
        js_lines.append(f"            color: '{epoch.color_hex}',")
        js_lines.append(f"            period: '{epoch.parent}'")
        js_lines.append("        },")

    js_lines.append("    }")
    js_lines.append("};")

    return "\n".join(js_lines)


if __name__ == "__main__":
    # Test the module
    print("Geological Timescale Database")
    print("=" * 50)

    # Test age lookup
    test_ages = [0, 10, 66, 145, 252, 485]
    for age in test_ages:
        period = get_period_for_age(age)
        era = get_era_for_age(age)
        color = get_color_for_age(age)
        print(f"{age} Ma: {period.name if period else 'N/A'} ({era.name if era else 'N/A'}) - {color}")

    print()
    print("Periods for timeline:")
    for p in get_all_periods_for_timeline():
        print(f"  {p['acronym']}: {p['name']} ({p['start_ma']}-{p['end_ma']} Ma) {p['color']}")
