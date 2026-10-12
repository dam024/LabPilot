from __future__ import annotations
from typing import Iterable, List
import time

# Add this code in your file if you want the logs to appear in the log area in the window
import labtools

logger = labtools.getLogger(__name__)

import labtools.plots.plot_backend as pb
import labtools.plots.plots_implementation as plots
import labtools.GUI.objects as gui_obj
from labtools.GUI.binding import Binding
import labtools.analysis as ana
import labtools.measurement_procedure as mp

from src.analysis import ExampleAnalysis


### TODO: Declare your views. Note: with the given configuration, all views must be declared in this file.
class TestView(ana.View):
    ### TODO: Give a name to the view. It will be displayed on the interface
    name: str = "Example View"

    def get_analysis(self) -> List[ana.DataAnalysis]:
        """This method defines which `DataAnalysis` are shown and which plots are shown"""
        analysis = ExampleAnalysis()

        ### TODO: Indicate which plots are visible
        analysis.plot_raw.show = True
        analysis.plot_processed.show = True

        return [analysis]
