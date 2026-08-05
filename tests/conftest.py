import sys
import os

# Testleri çalıştırırken asistan kök dizinini PYTHONPATH'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
