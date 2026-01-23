"""
Basic Image Editor
Copyright (C) 2026 Héctor Álvarez López hectoralvarez.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.utils.background_remover import BackgroundRemoverWorker
from PIL import Image

def test_worker_success(sample_image, qtbot):
    # Mock rembg.remove
    with patch('src.utils.background_remover.rembg.remove') as mock_remove:
        mock_remove.return_value = sample_image.copy() # Return same image as result
        
        worker = BackgroundRemoverWorker(sample_image)
        with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
            worker.start()
            
        assert mock_remove.called
        assert isinstance(blocker.args[0], Image.Image)

def test_worker_failure(sample_image, qtbot):
    # Mock exception
    with patch('src.utils.background_remover.rembg.remove') as mock_remove:
        mock_remove.side_effect = Exception("Mock Error")
        
        worker = BackgroundRemoverWorker(sample_image)
        with qtbot.waitSignal(worker.error, timeout=1000) as blocker:
            worker.start()
            
        assert blocker.args[0] == "Mock Error"
