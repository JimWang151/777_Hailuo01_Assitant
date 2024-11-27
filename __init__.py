# Made by Jim.Wang V1 for ComfyUI
import os
import subprocess
import importlib.util
import sys
import filecmp
import shutil

import __main__

python = sys.executable




from .ImageBridge import ImageBridge,ImageStitcher,PromptRefine

NODE_CLASS_MAPPINGS = {
    "BaseSetting": ImageBridge,
    "ImageStitcher": ImageStitcher,
    "PromptRefine": PromptRefine,
}


print('\033[34mHailuo Assistant Nodes: \033[92mLoaded\033[0m')