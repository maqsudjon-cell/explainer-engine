"""explainer-engine — branded, narration-free explainer video generator."""

# Brand tokens (defaults; overridable per spec via brand{})
BG_DARK     = (6, 11, 10)
BG_SPACE    = (5, 8, 15)
MINT        = (56, 222, 158)
MINT_BRIGHT = (180, 255, 224)
WHITE       = (236, 244, 240)
DIM         = (150, 168, 182)
RED         = (232, 90, 82)
AMBER       = (255, 200, 120)
GRID        = (18, 46, 38)

RESOLUTIONS = {
    "landscape": (1920, 1080),
    "vertical":  (1080, 1920),
    "square":    (1080, 1080),
}
FPS = 24
