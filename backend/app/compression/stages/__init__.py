from app.compression.stages.session_dedup import SessionDedupStage
from app.compression.stages.ccr import CcrStage
from app.compression.stages.lite import LiteStage
from app.compression.stages.rtk import RtkStage
from app.compression.stages.responses_tool import ResponsesToolStage
from app.compression.stages.headroom import HeadroomStage
from app.compression.stages.relevance import RelevanceStage
from app.compression.stages.caveman import CavemanStage
from app.compression.stages.aggressive import AggressiveStage
from app.compression.stages.llmlingua import LlmLinguaStage
from app.compression.stages.ultra import UltraStage
from app.compression.stages.omniglyph import OmniGlyphStage
from app.compression.stages.custom_regex import CustomRegexStage

BUILTIN_STAGES = [
    SessionDedupStage,
    CcrStage,
    LiteStage,
    RtkStage,
    ResponsesToolStage,
    HeadroomStage,
    RelevanceStage,
    CavemanStage,
    AggressiveStage,
    LlmLinguaStage,
    UltraStage,
    OmniGlyphStage,
]
