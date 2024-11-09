from dataclasses import dataclass
from colour import Color
from .utils import *

# Signature Plastics color codes
# Taken from https://spkeyboards.com/collections/pbt-colors
# Note from the manufacturers website: these colors can't be entirely trusted, and should
# therefore mostly be used for reference

__all__ = [
    "SPColor"
]

_sp_color_table = {
    # Blue
    "BCT": "#007DB7",
    "BDJ": "#4A93C6",
    "BDO": "#28A1CF",
    "BFC": "#AAD0DB",
    "BFE": "#9FC4EF",
    "BFG": "#7DB3E9",
    "BFH": "#488AAF",
    "BFV": "#7FD2DF",
    "BFW": "#4DA9BE",
    
    # Brown
    "TGJ": "#76432B",
    "TGL": "#CDB399",
    "TGM": "#C8A680",
    "TT":  "#C2A986",
    
    # Gray/Black
    "GAH": "#73736F",
    "GCA": "#B1B0A8",
    "GDE": "#8F9395",
    "GDM": "#CAC8BC",
    "GEC": "#969694",
    "GJW": "#8B847C",
    "GKK": "#C3C7C2",
    "GMC": "#A7A9A8",
    "GQC": "#9F9B8F",
    "GQJ": "#B9BBBA",
    "GQN": "#C5BBAB",
    "GQP": "#A39D97",
    "GQT": "#5A5D5F",
    "GRZ": "#B0B1B1",
    "GSE": "#7C7A75",
    "GSF": "#3E4045",
    "GSH": "#D7D6D0",
    "GSJ": "#BFBFC0",
    "GSN": "#B7B6AC",
    "GSQ": "#848788",
    "GTK": "#C7C2B0",
    "GTW": "#707884",
    "NEM": "#282A2E",
    
    # Green
    "VAL": "#619490",
    "VAZ": "#008C56",
    "VCC": "#34B764",
    "VCD": "#00725D",
    "VCE": "#76E1C0",
    "VCH": "#009C69",
    "VCR": "#008B45",
    "VDH": "#00763A",
    "VDJ": "#ADDC77",
    "VS":  "#255546",
    
    # Orange
    "OAX": "#FF7A24",
    "OAY": "#FFB67F",
    "OAZ": "#EF7144",
    "OBB": "#FF7C21",
    "OT":  "#F3791F",
    "OW":  "#BA4C36",
    
    # Red/Pink/Purple
    "RAA": "#BC3331",
    "RAG": "#E76C5E",
    "RAR": "#C11C06",
    "RBH": "#BC252F",
    "RCA": "#D792BA",
    "RCB": "#8981B2",
    "RCE": "#837C9A",
    "RCF": "#C94854",
    "RCG": "#FFB8DE",
    "RCL": "#F79CB2",
    "RCM": "#A16687",
    "RCP": "#D22F2F",
    "RDP": "#7F4A8B",
    
    # White
    "UP":  "#F0F0EF",
    "WAN": "#EBEBE9",
    "WAS": "#DFDBD1",
    "WAT": "#C9C6B9",
    "WBK": "#E3DECE",
    "WFJ": "#E6E4EE",
    "WFN": "#CCCBBB",
    "WGB": "#F0EEE9",
    "WGD": "#F4E7CE",
    
    # Yellow
    "YAF": "#FFE384",
    "YAM": "#FDD80F",
    "YBT": "#F6E49F",
    "YBX": "#FFE149",
    "YBZ": "#CD8317",
    "YCJ": "#E2AB00",
    "YCR": "#FFC037",
    "YR":  "#FFC700",
}

@dataclass
class SPColor:
    code: str
    
    def __init__(self, code: str) -> None:
        if code not in _sp_color_table:
            panic(f"Invalid Signature Plastics color code '{code}'")
        self.code = code
    
    def to_color(self) -> Color:
        return Color(_sp_color_table[self.code])
