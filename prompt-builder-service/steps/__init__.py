# Pipeline steps — each module exports a ``create_step()`` function
# that returns a Step instance wired to the real implementations.

from .product_analysis import create_step as _product_analysis
from .vision_analysis import create_step as _vision_analysis
from .gender_fallback import create_step as _gender_fallback
from .persona_inject import create_step as _persona_inject
from .model_cast import create_step as _model_cast
from .age_normalize import create_step as _age_normalize
from .image_prompt import create_step as _image_prompt
from .video_prompt import create_step as _video_prompt
from .negative_prompt import create_step as _negative_prompt
from .timing_validation import create_step as _timing_validation

ALL_STEPS = [
    _product_analysis(),
    _vision_analysis(),
    _gender_fallback(),
    _persona_inject(),
    _model_cast(),
    _age_normalize(),
    _image_prompt(),
    _video_prompt(),
    _negative_prompt(),
    _timing_validation(),
]
