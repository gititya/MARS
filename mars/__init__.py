__version__ = "0.1.0"

import os
os.environ["LITELLM_LOG"] = "ERROR"

import litellm
litellm.suppress_debug_info = True
